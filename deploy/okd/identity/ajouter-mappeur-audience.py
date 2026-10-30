#!/usr/bin/env python3
"""Ajoute à un client existant du realm « sophia » un mappeur d'audience vers un autre client, s'il manque.

Usage : un service qui reçoit le jeton d'accès relayé par l'interface de discussion n'accepte que les
jetons qui portent son audience. Lancé par l'administrateur depuis son poste (sous VPN), bibliothèque
standard seulement :

    python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <client-du-service> --dry-run
    python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <client-du-service>

  - client du service existant (MCP qui échange le jeton, oauth2-proxy d'une application qui vérifie le
    jeton porteur avec --skip-jwt-bearer-tokens) : mappeur de client (included.client.audience) ;
  - service sans client Keycloak qui vérifie lui-même la signature du jeton, sans introspection ni échange
    (par exemple le module de résumé monté dans le serveur de messagerie) : --personnalisee
    (included.custom.audience). Refusé si un client du même nom existe, et inversement.

N'ajoute que le mappeur « audience-<audience> » ; ne modifie ni ne supprime rien d'autre. Rejouable :
s'il existe déjà, rien n'est fait. Relève aussi, en lecture, le mappeur de groupes direct du client :
--allowed-group d'oauth2-proxy compare la valeur exacte (« admin », pas « /admin »), d'où full.path false
et les groupes dans le jeton d'accès. Identifiants d'administration (realm master) demandés sans écho.
Les nouvelles audiences n'apparaissent qu'au renouvellement du jeton : un 403 juste après, avec un jeton
antérieur, est normal.
"""
import argparse
import getpass
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

REALM = "sophia"


def dire(m):
    print(m, file=sys.stderr)


class Keycloak:
    def __init__(self, base, ctx):
        self.base, self.ctx, self.token = base.rstrip("/"), ctx, None

    def login(self, user, password):
        data = urllib.parse.urlencode({"grant_type": "password", "client_id": "admin-cli",
                                       "username": user, "password": password}).encode()
        req = urllib.request.Request(f"{self.base}/realms/master/protocol/openid-connect/token", data=data)
        with urllib.request.urlopen(req, context=self.ctx) as r:
            self.token = json.load(r)["access_token"]

    def call(self, method, path, body=None):
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
            sys.exit(f"Keycloak {method} {path} : HTTP {e.code} {e.read()[:300]!r}")

    def client(self, client_id):
        found = self.call("GET", "/clients?" + urllib.parse.urlencode({"clientId": client_id}))
        return found[0] if found else None


def relever_groupes(client, mappeurs):
    """Le mappeur de groupes direct du client : nom du claim, chemin complet, présence dans le jeton d'accès."""
    g = [m for m in mappeurs if m.get("protocolMapper") == "oidc-group-membership-mapper"]
    if not g:
        dire(f"groupes sur {client} : aucun mappeur direct (vient peut-être d'une portée : à vérifier)")
        return None
    conformes = True
    for m in g:
        c = m.get("config") or {}
        ok = c.get("full.path") == "false" and c.get("access.token.claim") == "true"
        conformes = conformes and ok
        dire(f"groupes sur {client} : mappeur {m.get('name')}, claim {c.get('claim.name')}, "
             f"full.path {c.get('full.path')}, jeton d'accès {c.get('access.token.claim')} : "
             + ("conforme" if ok else "NON CONFORME (attendu full.path false, jeton d'accès true)"))
    return conformes


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("client", help="clientId qui reçoit le mappeur (ex. sophia-interface)")
    ap.add_argument("audience", help="audience ajoutée au jeton (clientId du service, ou nom libre avec --personnalisee)")
    ap.add_argument("--personnalisee", action="store_true",
                    help="audience libre (included.custom.audience), sans client du même nom : pour un service "
                         "qui vérifie la signature lui-même ; pas pour l'introspection ni l'échange de jetons")
    ap.add_argument("--dry-run", action="store_true", help="lecture seule")
    ap.add_argument("--base-url", default="https://auth.apps.example.org")
    ap.add_argument("--ca-file")
    args = ap.parse_args()
    kc = Keycloak(args.base_url, ssl.create_default_context(cafile=args.ca_file))
    sys.stderr.write("Administrateur Keycloak (realm master) : ")
    user = input()
    try:
        kc.login(user, getpass.getpass("Mot de passe : ", stream=sys.stderr))
    except urllib.error.HTTPError as e:
        sys.exit(f"Connexion refusée (HTTP {e.code})")
    except urllib.error.URLError as e:
        sys.exit(f"Keycloak injoignable ({e.reason}) — VPN ? Certificats : --ca-file")
    c = kc.client(args.client)
    if not c:
        sys.exit(f"client {args.client} : introuvable")
    existe = kc.client(args.audience)
    if args.personnalisee and existe:
        sys.exit(f"client {args.audience} : existe ; mappeur de client plutôt (sans --personnalisee)")
    if not args.personnalisee and not existe:
        sys.exit(f"client {args.audience} : introuvable (à créer d'abord, ou --personnalisee)")
    genre = "audience personnalisée" if args.personnalisee else "audience"
    nom = f"audience-{args.audience}"
    mappeurs = kc.call("GET", f"/clients/{c['id']}/protocol-mappers/models") or []
    if relever_groupes(args.client, mappeurs) is False:
        sys.exit("Mappeur de groupes non conforme : à corriger avant d'ajouter une audience.")
    if any(m.get("name") == nom for m in mappeurs):
        dire(f"mappeur {nom} sur {args.client} : existe, non modifié")
        return
    if args.dry_run:
        dire(f"[à faire] mappeur {nom} sur {args.client} ({genre} {args.audience}, jeton d'accès)")
        dire("Lecture seule : rien n'a été modifié.")
        return
    kc.call("POST", f"/clients/{c['id']}/protocol-mappers/models", {
        "name": nom, "protocol": "openid-connect", "protocolMapper": "oidc-audience-mapper",
        "config": {("included.custom.audience" if args.personnalisee else "included.client.audience"): args.audience,
                   "id.token.claim": "false", "access.token.claim": "true", "introspection.token.claim": "true"}})
    dire(f"mappeur {nom} sur {args.client} : ajouté")


if __name__ == "__main__":
    main()
