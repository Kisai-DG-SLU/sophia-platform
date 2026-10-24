#!/usr/bin/env python3
"""Autorisation de Temporal par jetons Keycloak (realm « sophia »).

Lancé par l'administrateur depuis son poste (sous VPN), bibliothèque standard seulement :

    python3 deploy/okd/identity/temporal-keycloak.py --dry-run   # lecture seule, liste les actions
    python3 deploy/okd/identity/temporal-keycloak.py             # applique

Crée ce qui manque, ne modifie pas ce qui existe, sauf la désactivation ci-dessous (rejouable) :
  - client « temporal » : porte les rôles « namespace:rôle » lus par Temporal ;
  - client scope « temporal-permissions » : ces rôles dans le claim « permissions » des jetons ;
  - scope ajouté par défaut au client « temporal-ui » (interface, via oauth2-proxy) ;
  - groupe « admin » → temporal-system:admin ;
  - « temporal-repartiteur » (sophia:write : seul client Temporal applicatif) et
    « temporal-admin » (Jobs d'administration, temporal-system:admin) ;
  - les anciens clients par agent (« temporal-<agent> ») sont désactivés, jamais supprimés :
    les agents n'ont plus accès à Temporal (voir core/repartiteur/). Leurs Secrets sont à supprimer par l'administrateur.
Le secret de chaque client à compte de service est lu dans Keycloak et posé dans un Secret
Kubernetes par l'entrée standard d'« oc apply » : jamais affiché, jamais écrit dans un fichier.
Identifiant et mot de passe administrateur (realm master) demandés sans écho.
"""
import argparse
import getpass
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

REALM = "sophia"
PERM_CLIENT = "temporal"
SCOPE = "temporal-permissions"
UI_CLIENT = "temporal-ui"
ADMIN_GROUP = "admin"
ROLES = {
    "temporal-system:admin": "Temporal : administrateur de tout le cluster",
    "sophia:admin": "Temporal : administrateur du namespace sophia",
    "sophia:write": "Temporal : lancer et exécuter des workflows dans sophia (agents)",
    "sophia:read": "Temporal : lecture du namespace sophia",
}
# client Keycloak -> (rôle Temporal, namespace Kubernetes, nom du Secret)
SERVICE_CLIENTS = {
    "temporal-repartiteur": ("sophia:write", "sophia-core", "temporal-repartiteur"),
    "temporal-admin": ("temporal-system:admin", "sophia-core", "temporal-admin-client"),
}
# Anciens clients par agent, désactivés (Secrets temporal-agent-<agent> de hermes-system)
RETIRES = [f"temporal-{a}" for a in ["sophia", "athena", "hephaistos", "ouranos", "dionysos"]]


class Keycloak:
    def __init__(self, base, ctx, dry_run):
        self.base, self.ctx, self.dry_run = base.rstrip("/"), ctx, dry_run
        self.token = None

    def login(self, user, password):
        data = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                       "username": user, "password": password}).encode()
        req = urllib.request.Request(f"{self.base}/realms/master/protocol/openid-connect/token", data=data)
        with urllib.request.urlopen(req, context=self.ctx) as r:
            self.token = json.load(r)["access_token"]

    def call(self, method, path, body=None, write=False):
        if write and self.dry_run:
            return None
        req = urllib.request.Request(f"{self.base}/admin/realms/{REALM}{path}", method=method,
                                     data=None if body is None else json.dumps(body).encode())
        req.add_header("Authorization", f"Bearer {self.token}")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=self.ctx) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == "GET":
                return None
            sys.exit(f"Keycloak {method} {path} : HTTP {e.code} {e.read()[:300]!r}")

    def client(self, client_id):
        found = self.call("GET", "/clients?" + urllib.parse.urlencode({"clientId": client_id}))
        return found[0] if found else None


def step(dry_run, message):
    print(("[à faire] " if dry_run else "") + message)


def ensure_client(kc, rep):
    c = kc.client(rep["clientId"])
    if c:
        print(f"client {rep['clientId']} : existe")
        return c
    step(kc.dry_run, f"client {rep['clientId']} : création")
    kc.call("POST", "/clients", rep, write=True)
    return kc.client(rep["clientId"])


def put_secret(dry_run, namespace, name, client_id, secret):
    step(dry_run, f"Secret {namespace}/{name} : client-id={client_id}, client-secret (non affiché)")
    if dry_run:
        return
    manifest = {"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                "metadata": {"name": name, "namespace": namespace, "labels": {"app": "temporal-auth"}},
                "stringData": {"client-id": client_id, "client-secret": secret}}
    subprocess.run(["oc", "apply", "-f", "-"], input=json.dumps(manifest).encode(), check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="lecture seule : liste les actions")
    ap.add_argument("--base-url", default="https://auth.apps.example.org")
    ap.add_argument("--ca-file", help="autorités de certification (si Python ne trouve pas celles du système)")
    args = ap.parse_args()

    ctx = ssl.create_default_context(cafile=args.ca_file)
    kc = Keycloak(args.base_url, ctx, args.dry_run)
    user = input("Administrateur Keycloak (realm master) : ")
    try:
        kc.login(user, getpass.getpass("Mot de passe : "))
    except urllib.error.HTTPError as e:
        sys.exit(f"Connexion refusée (HTTP {e.code}) : identifiant, mot de passe, ou second facteur requis")
    except urllib.error.URLError as e:
        sys.exit(f"Keycloak injoignable ({e.reason}) — VPN ? Certificats : --ca-file")

    # 1. Client porteur des rôles et ses rôles
    perm = ensure_client(kc, {"clientId": PERM_CLIENT, "name": "Temporal (droits)",
                              "description": "Porte les rôles namespace:rôle lus par Temporal. Aucun flux de connexion.",
                              "enabled": True, "protocol": "openid-connect", "publicClient": False,
                              "standardFlowEnabled": False, "directAccessGrantsEnabled": False,
                              "implicitFlowEnabled": False, "serviceAccountsEnabled": False})
    roles = {}
    for name, desc in ROLES.items():
        r = kc.call("GET", f"/clients/{perm['id']}/roles/{urllib.parse.quote(name, safe='')}") if perm else None
        if r is None:
            step(kc.dry_run, f"rôle {PERM_CLIENT}/{name} : création")
            if perm:
                kc.call("POST", f"/clients/{perm['id']}/roles", {"name": name, "description": desc}, write=True)
                r = kc.call("GET", f"/clients/{perm['id']}/roles/{urllib.parse.quote(name, safe='')}")
        else:
            print(f"rôle {PERM_CLIENT}/{name} : existe")
        roles[name] = r

    # 2. Client scope : rôles du client « temporal » dans le claim « permissions »
    scopes = kc.call("GET", "/client-scopes") or []
    scope = next((s for s in scopes if s["name"] == SCOPE), None)
    if scope:
        print(f"client scope {SCOPE} : existe")
    else:
        step(kc.dry_run, f"client scope {SCOPE} : création (claim « permissions »)")
        kc.call("POST", "/client-scopes", {
            "name": SCOPE, "protocol": "openid-connect",
            "description": "Rôles Temporal (client temporal) dans le claim permissions",
            "attributes": {"include.in.token.scope": "false", "display.on.consent.screen": "false"},
            "protocolMappers": [{
                "name": "permissions", "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-client-role-mapper",
                "config": {"usermodel.clientRoleMapping.clientId": PERM_CLIENT, "claim.name": "permissions",
                           "multivalued": "true", "jsonType.label": "String",
                           "access.token.claim": "true", "id.token.claim": "true",
                           "userinfo.token.claim": "false"}}]}, write=True)
        scope = next((s for s in kc.call("GET", "/client-scopes") or [] if s["name"] == SCOPE), None)

    def add_scope(c):
        if not (c and scope):
            step(kc.dry_run, f"scope {SCOPE} par défaut sur {c['clientId'] if c else 'nouveau client'}")
            return
        current = kc.call("GET", f"/clients/{c['id']}/default-client-scopes") or []
        if any(s["name"] == SCOPE for s in current):
            print(f"scope {SCOPE} sur {c['clientId']} : déjà")
        else:
            step(kc.dry_run, f"scope {SCOPE} par défaut sur {c['clientId']}")
            kc.call("PUT", f"/clients/{c['id']}/default-client-scopes/{scope['id']}", write=True)

    def grant(path, label, role_name):
        if not (perm and roles.get(role_name)):
            step(kc.dry_run, f"{label} → {role_name}")
            return
        have = kc.call("GET", f"{path}/role-mappings/clients/{perm['id']}") or []
        if any(r["name"] == role_name for r in have):
            print(f"{label} → {role_name} : déjà")
        else:
            step(kc.dry_run, f"{label} → {role_name}")
            kc.call("POST", f"{path}/role-mappings/clients/{perm['id']}", [roles[role_name]], write=True)

    # 3. Interface Temporal et groupe admin
    ui = kc.client(UI_CLIENT)
    if not ui:
        sys.exit(f"client {UI_CLIENT} absent : l'importer d'abord (identity/clients/temporal-ui.json)")
    add_scope(ui)
    groups = kc.call("GET", "/groups?" + urllib.parse.urlencode({"search": ADMIN_GROUP, "exact": "true"})) or []
    group = next((g for g in groups if g["name"] == ADMIN_GROUP), None)
    if not group:
        sys.exit(f"groupe {ADMIN_GROUP} absent du realm {REALM}")
    grant(f"/groups/{group['id']}", f"groupe {ADMIN_GROUP}", "temporal-system:admin")

    # 4. Comptes de service et leurs Secrets
    for client_id, (role_name, namespace, secret_name) in SERVICE_CLIENTS.items():
        c = ensure_client(kc, {"clientId": client_id, "name": f"Temporal — {client_id}",
                               "description": "Compte de service Temporal, client credentials.",
                               "enabled": True, "protocol": "openid-connect", "publicClient": False,
                               "clientAuthenticatorType": "client-secret",
                               "standardFlowEnabled": False, "directAccessGrantsEnabled": False,
                               "implicitFlowEnabled": False, "serviceAccountsEnabled": True})
        add_scope(c)
        if c:
            sa = kc.call("GET", f"/clients/{c['id']}/service-account-user")
            grant(f"/users/{sa['id']}", f"compte de service {client_id}", role_name)
            secret = None if kc.dry_run else kc.call("GET", f"/clients/{c['id']}/client-secret")["value"]
        else:
            step(kc.dry_run, f"compte de service {client_id} → {role_name}")
            secret = None
        put_secret(kc.dry_run, namespace, secret_name, client_id, secret)

    # 5. Anciens clients par agent : désactivés (un jeton déjà émis expire seul, 5 min par défaut)
    for client_id in RETIRES:
        c = kc.client(client_id)
        if c is None:
            print(f"client {client_id} : absent")
        elif not c.get("enabled", True):
            print(f"client {client_id} : déjà désactivé")
        else:
            step(kc.dry_run, f"client {client_id} : désactivation")
            kc.call("PUT", f"/clients/{c['id']}", {**c, "enabled": False}, write=True)

    print("Terminé." if not kc.dry_run else "Lecture seule : rien n'a été modifié.")


if __name__ == "__main__":
    main()
