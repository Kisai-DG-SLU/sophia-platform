#!/usr/bin/env python3
"""Tarifs des modèles LiteLLM → pricing.json (gitignoré), servi au front.

LiteLLM ne renvoie pas le coût dans un flux SSE : le front le calcule à
partir des tokens et des tarifs. Ces tarifs sont ceux de LiteLLM
(`custom_cost_map.json`), lus ici côté pod via /v1/model/info avec
LITELLM_API_KEY. Le navigateur ne reçoit que pricing.json :
  {"sophia-think": {"inputPer1M": 0.55, "outputPer1M": 0.55}, ...}
/v1/model/info n'est pas exposé par nginx.

Règles :
- la clé n'est jamais affichée ni écrite ;
- best-effort : en cas d'échec, pricing.json existant conservé (ou `{}`
  s'il n'existe pas), code retour 0 — un tarif manquant ne bloque pas nginx ;
- un modèle sans tarif connu est omis : le front garde 0.

Usage : python3 deploy/render-pricing.py [--status]
  --status : code retour 1 si les tarifs n'ont pas pu être lus (pour la boucle de
             rafraîchissement de deploy/entrypoint.sh) ; sans l'option, toujours 0.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "pricing.json"
URL = os.environ.get(
    "LITELLM_MODEL_INFO_URL",
    "http://litellm-svc.sophia-core.svc.cluster.local:4000/v1/model/info",
)


def per_million(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return round(v * 1_000_000, 6) if v >= 0 else None


def extract(info):
    pricing = {}
    for dep in info.get("data") or []:
        name = dep.get("model_name")
        mi = dep.get("model_info") or {}
        inp = per_million(mi.get("input_cost_per_token"))
        out = per_million(mi.get("output_cost_per_token"))
        if not name or name in pricing or (inp is None and out is None):
            continue
        pricing[name] = {"inputPer1M": inp or 0, "outputPer1M": out or 0}
    return pricing


STATUS = "--status" in sys.argv[1:]


def write_atomic(text: str) -> None:
    """Écriture atomique : nginx ne sert jamais un fichier à moitié écrit."""
    tmp = OUTPUT.with_name(OUTPUT.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.chmod(0o644)
    os.replace(tmp, OUTPUT)


def keep_previous(reason):
    print(f"[pricing] AVERTISSEMENT: {reason}", file=sys.stderr)
    if not OUTPUT.exists():
        write_atomic("{}\n")
        print(f"[pricing] {OUTPUT.name} vide créé : coûts affichés à 0.", file=sys.stderr)
    else:
        print(f"[pricing] {OUTPUT.name} précédent conservé.", file=sys.stderr)
    return 1 if STATUS else 0


def main() -> int:
    key = os.environ.get("LITELLM_API_KEY", "").strip()
    if not key:
        return keep_previous("LITELLM_API_KEY absente de l'env.")
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            info = json.load(res)
    except urllib.error.HTTPError as e:
        return keep_previous(f"/v1/model/info a répondu {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return keep_previous(f"LiteLLM injoignable ({type(e).__name__}).")
    except ValueError:
        return keep_previous("réponse de /v1/model/info illisible (JSON invalide).")

    pricing = extract(info)
    write_atomic(json.dumps(pricing, indent=2, sort_keys=True) + "\n")
    for name, p in sorted(pricing.items()):
        print(f"[pricing] {name}: ${p['inputPer1M']} → ${p['outputPer1M']} /M")
    print(f"[pricing] {OUTPUT} généré ({len(pricing)} modèle(s) tarifé(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
