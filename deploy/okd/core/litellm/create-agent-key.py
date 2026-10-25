#!/usr/bin/env python3
"""Crée la clé virtuelle du routeur pour un agent : alias de fond et embedding seulement, débit
plafonné, alias agent-<nom>. Remplace, agent par agent, une clé commune (ou la clé maître) lue par
tous les agents.

Lancé DANS le pod LiteLLM, par l'entrée standard (la clé maître est lue dans l'environnement du pod,
jamais affichée). La clé créée ne sort que sous la forme NOM='…', pour un eval sur le poste de
l'administrateur, puis un Secret créé par l'entrée standard :

  oc exec -i -n sophia-core deploy/litellm -- python3 - <agent> --dry-run < create-agent-key.py
  eval "$(oc exec -i -n sophia-core deploy/litellm -- python3 - <agent> --eval CLE_AGENT < create-agent-key.py)"

Ne modifie ni ne supprime jamais une clé existante : si l'alias agent-<nom> existe déjà, refus
(code 1, rien sur la sortie standard). Une clé perdue se retire par /key/delete, puis on relance.
"""

import json
import os
import re
import sys
import urllib.request

BASE = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
AGENTS = ("sophia", "athena", "hephaistos", "ouranos", "dionysos")
MODELES = ["sophia-local-fond", "sophia-embedder"]
RPM = 120   # requêtes par minute : une boucle d'outils emballée s'arrête, une mission normale passe


def call(method, path, body=None):
    key = os.environ.get("LITELLM_MASTER_KEY", "").strip()
    if not key:
        sys.exit("❌ LITELLM_MASTER_KEY absente de l'environnement")
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def main():
    argv = sys.argv[1:]
    args = [a for a in argv if not a.startswith("--")]
    dry = "--dry-run" in argv
    var = argv[argv.index("--eval") + 1] if "--eval" in argv and argv.index("--eval") + 1 < len(argv) else None
    if var:
        args.remove(var)
    if len(args) != 1 or args[0] not in AGENTS or (not dry and not var) or (var and not re.fullmatch(r"[A-Z][A-Z0-9_]*", var)):
        sys.exit(f"usage : python3 - <{'|'.join(AGENTS)}> --dry-run | --eval NOM_DE_VARIABLE")
    agent = args[0]
    alias = f"agent-{agent}"
    keys = call("GET", "/key/list?return_full_object=true&size=100").get("keys") or []
    if any(isinstance(k, dict) and k.get("key_alias") == alias for k in keys):
        sys.exit(f"❌ la clé {alias} existe déjà : rien n'est créé")
    corps = {"key_alias": alias, "models": MODELES, "rpm_limit": RPM,
             "metadata": {"agent": agent}}
    if dry:
        print(f"· {alias} : à créer, modèles {MODELES}, {RPM} requêtes par minute   (à blanc)", file=sys.stderr)
        return
    cle = call("POST", "/key/generate", corps).get("key", "")
    if not re.fullmatch(r"sk-[A-Za-z0-9_-]{8,}", cle):
        sys.exit("❌ réponse inattendue de /key/generate : rien n'est exporté")
    print(f"✓ {alias} créée : modèles {MODELES}, {RPM} requêtes par minute", file=sys.stderr)
    print(f"{var}='{cle}'")


if __name__ == "__main__":
    main()
