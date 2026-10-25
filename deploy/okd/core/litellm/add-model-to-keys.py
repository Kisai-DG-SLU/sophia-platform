#!/usr/bin/env python3
"""Ajoute un alias de modèle aux clés virtuelles LiteLLM restreintes (garde-fou des clés restreintes).

Les clés virtuelles (interface, agents) sont limitées à une liste de modèles : un nouvel
alias (ex. sophia-local) y est invisible tant qu'il n'y est pas ajouté. Ne touche que les
clés dont la liste contient déjà le modèle de référence (sophia-think par défaut) ; une clé
sans liste (tous modèles) n'est pas modifiée.

Lancé DANS le pod LiteLLM, par l'entrée standard (aucun secret en argument, la clé maître
est lue dans l'environnement du pod, jamais affichée) :

  oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local < add-model-to-keys.py           # à blanc
  oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local --apply < add-model-to-keys.py   # applique

Affiche seulement l'alias de chaque clé et sa liste de modèles.
Modèle de référence (clés à compléter) : sophia-think par défaut, ou --reference=<alias>.
"""

import json
import os
import sys
import urllib.request

BASE = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
REFERENCE = os.environ.get("REFERENCE_MODEL", "sophia-think")


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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv[1:]
    reference = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--reference=")), REFERENCE)
    if len(args) != 1:
        sys.exit("usage : python3 - <alias> [--apply]")
    model = args[0]

    keys = call("GET", "/key/list?return_full_object=true&size=100").get("keys") or []
    changed = 0
    for k in keys:
        if not isinstance(k, dict):
            continue
        alias = k.get("key_alias") or "(sans alias)"
        models = list(k.get("models") or [])
        if not models or reference not in models:
            continue
        if model in models:
            print(f"✓ {alias} : déjà {models}")
            continue
        new = models + [model]
        if apply:
            call("POST", "/key/update", {"key": k["token"], "models": new})
            print(f"✓ {alias} : {models} → {new}")
        else:
            print(f"· {alias} : {models} → {new}   (à blanc)")
        changed += 1
    if not apply and changed:
        print("À blanc : relancer avec --apply pour appliquer.")
    if not changed:
        print("Aucune clé à modifier.")


if __name__ == "__main__":
    main()
