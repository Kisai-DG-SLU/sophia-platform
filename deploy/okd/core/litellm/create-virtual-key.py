#!/usr/bin/env python3
"""Crée une clé virtuelle LiteLLM sous un alias donné, avec la liste de modèles et les limites
(débit, budget) d'une clé existante (--comme ALIAS) : pour un pod de développement, au lieu de la clé maître.

Lancé DANS le pod LiteLLM, par l'entrée standard (la clé maître est lue dans l'environnement du pod,
jamais affichée). La clé créée ne sort que sous la forme NOM='…', pour un eval sur le poste d'administration :

  oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --comme <alias-de-référence> --dry-run < create-virtual-key.py
  eval "$(oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --comme <alias-de-référence> --eval NOM < create-virtual-key.py)"

--sans m1,m2 retire des modèles de la liste recopiée (moindre privilège). Il ne peut jamais en ajouter.

Sans clé de référence, --modeles m1,m2 --rpm N donne une liste explicite et un débit, sans budget
(par exemple la clé de la voix du chat). Chaque modèle doit exister dans LiteLLM.

--info <alias> affiche les modèles, les limites et les 12 premiers caractères de l'empreinte SHA-256
de la clé (champ token de LiteLLM), jamais la clé : comparée à l'empreinte de la valeur rangée dans
un Secret, elle prouve que c'est la bonne clé.

Refuse (code 1, rien sur la sortie standard) :
  - si l'alias existe déjà : ne modifie ni ne supprime jamais une clé ;
  - si la clé de référence est absente, ambiguë, ou sans liste de modèles ou en « * » (accès à
    tout) : on ne recopie pas un accès complet.
"""

import json
import os
import re
import sys
import urllib.request

BASE = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
ALIAS = re.compile(r"^[a-z][a-z0-9-]{1,40}$")


def call(method, path, body=None):
    key = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if not key:
        sys.exit("❌ LITELLM_MASTER_KEY absente de l'environnement")
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def option(argv, nom):
    if nom in argv and argv.index(nom) + 1 < len(argv):
        return argv[argv.index(nom) + 1]
    return None


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    var, comme, sans = option(argv, "--eval"), option(argv, "--comme"), option(argv, "--sans")
    liste, rpm, info = option(argv, "--modeles"), option(argv, "--rpm"), option(argv, "--info")
    keys = [k for k in call("GET", "/key/list?return_full_object=true&size=100").get("keys") or [] if isinstance(k, dict)]
    if info:
        trouvees = [k for k in keys if k.get("key_alias") == info]
        if len(trouvees) != 1:
            sys.exit(f"❌ clé {info} : {len(trouvees)} trouvée(s)")
        k = trouvees[0]
        print(f"{info} : modèles {k.get('models')}, rpm {k.get('rpm_limit')}, tpm {k.get('tpm_limit')}, "
              f"budget {k.get('max_budget')}, dépensé {k.get('spend')}, empreinte {str(k.get('token'))[:12]}")
        return
    args = [a for a in argv if not a.startswith("--") and a not in (var, comme, sans, liste, rpm)]
    if (len(args) != 1 or not ALIAS.match(args[0]) or (not dry and not var) or bool(comme) == bool(liste)
            or (liste and (sans or not rpm or not rpm.isdigit() or not 1 <= int(rpm) <= 10000))
            or (var and not re.fullmatch(r"[A-Z][A-Z0-9_]*", var))):
        sys.exit("usage : python3 - <alias> (--comme <alias-de-référence> [--sans m1,m2] | --modeles m1,m2 --rpm N)"
                 " --dry-run | --eval NOM_DE_VARIABLE ; ou python3 - --info <alias>")
    alias = args[0]
    if any(k.get("key_alias") == alias for k in keys):
        sys.exit(f"❌ la clé {alias} existe déjà : rien n'est créé")
    if liste:
        modeles = [m for m in liste.split(",") if m]
        connus = {m.get("id") for m in call("GET", "/v1/models").get("data") or []}
        inconnus = [m for m in modeles if m not in connus or m == "*"]
        if not modeles or inconnus:
            sys.exit(f"❌ --modeles : {inconnus or 'liste vide'} inconnus de LiteLLM")
        return creer(alias, modeles, {"rpm_limit": int(rpm)}, {"modeles": "explicites"}, var, dry)
    refs = [k for k in keys if k.get("key_alias") == comme]
    if len(refs) != 1:
        sys.exit(f"❌ clé de référence {comme} : {len(refs)} trouvée(s), il en faut une seule")
    modeles = list(refs[0].get("models") or [])
    if not modeles or "*" in modeles or "all-proxy-models" in modeles:
        sys.exit(f"❌ la clé {comme} donne accès à tous les modèles : on ne la recopie pas")
    retires = [m for m in (sans or "").split(",") if m]
    inconnus = [m for m in retires if m not in modeles]
    if inconnus:
        sys.exit(f"❌ --sans : {inconnus} absents de la clé {comme}")
    modeles = [m for m in modeles if m not in retires]
    if not modeles:
        sys.exit("❌ plus aucun modèle après --sans")
    limites = {k: refs[0][k] for k in ("rpm_limit", "tpm_limit", "max_parallel_requests", "max_budget",
                                       "budget_duration") if refs[0].get(k) is not None}
    creer(alias, modeles, limites, {"comme": comme}, var, dry)


def creer(alias, modeles, limites, origine, var, dry):
    if dry:
        print(f"· {alias} : à créer, modèles {modeles}, limites {limites} ({origine})   (à blanc)", file=sys.stderr)
        return
    cle = call("POST", "/key/generate", {"key_alias": alias, "models": modeles, **limites,
                                         "metadata": {**origine}}).get("key", "")
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{8,}", cle):
        sys.exit("❌ réponse inattendue de /key/generate : rien n'est exporté")
    print(f"✓ {alias} créée : modèles {modeles}, limites {limites} ({origine})", file=sys.stderr)
    print(f"{var}='{cle}'")


if __name__ == "__main__":
    main()
