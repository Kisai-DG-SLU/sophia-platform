#!/usr/bin/env python3
"""Synchronise les tarifs DeepInfra dans config.yaml (ConfigMap litellm-config).

LiteLLM ne connaît pas tous les modèles DeepInfra (DeepSeek-V4 absent de sa
table embarquée → coût 0, budgets des virtual keys inopérants). DeepInfra
publie ses tarifs, sans clé, dans GET /v1/openai/models → metadata.pricing
($ par million de tokens). Ce script les recopie, pour chaque modèle
`deepinfra/…` de model_list, en input_cost_per_token / output_cost_per_token
dans litellm_params.

Le fichier est édité ligne à ligne (commentaires et ordre conservés) ; seules
les lignes de tarif et leur commentaire daté sont réécrites. On relit le
diff, puis on applique :
    python3 deploy/okd/core/litellm/sync-pricing.py           # met à jour
    python3 deploy/okd/core/litellm/sync-pricing.py --check   # code 1 si écart
    oc diff -f deploy/okd/core/litellm/config.yaml
    oc apply -f deploy/okd/core/litellm/config.yaml && oc rollout restart deploy/litellm -n sophia-core

Le tarif du cache (cache_read_tokens) n'est pas reporté : les tokens lus en
cache sont donc comptés au tarif d'entrée, ce qui surestime le coût.
Bibliothèque standard uniquement.
"""

import argparse
import datetime
import json
import re
import sys
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "config.yaml"
URL = "https://api.deepinfra.com/v1/openai/models"
MARK = "# Tarif DeepInfra"
MODEL_RE = re.compile(r"^(\s*)model:\s*[\"']?deepinfra/([^\s\"'#]+)")
COST_RE = re.compile(r"^\s*(input|output)_cost_per_token:")


def fetch_pricing():
    req = urllib.request.Request(URL, headers={"User-Agent": "sophia-sync-pricing"})
    with urllib.request.urlopen(req, timeout=20) as res:
        data = json.load(res)
    out = {}
    for m in data.get("data", []):
        p = (m.get("metadata") or {}).get("pricing") or {}
        if "input_tokens" in p and "output_tokens" in p:
            out[m["id"]] = (float(p["input_tokens"]), float(p["output_tokens"]))
    return out


def per_token(per_million):
    return f"{per_million / 1_000_000:.10f}".rstrip("0").rstrip(".") or "0"


def block_end(lines, start, indent):
    """Index de la première ligne après le bloc litellm_params de `start`."""
    i = start + 1
    while i < len(lines):
        s = lines[i]
        if s.strip() and (len(s) - len(s.lstrip())) < len(indent):
            break
        i += 1
    while i > start + 1 and not lines[i - 1].strip():
        i -= 1
    return i


def sync(text, pricing, today):
    lines = text.split("\n")
    report, changed = [], False
    i = 0
    while i < len(lines):
        m = MODEL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        indent, model = m.group(1), m.group(2)
        end = block_end(lines, i, indent)
        body = lines[i + 1:end]
        old = {k: v for k, v in (re.match(r"^\s*(\w+):\s*(\S+)", l).groups()
               for l in body if COST_RE.match(l))}
        if model not in pricing:
            report.append(f"  ?  {model} : absent de DeepInfra, inchangé")
            i = end
            continue
        pin, pout = pricing[model]
        new_in, new_out = per_token(pin), per_token(pout)
        kept = [l for l in body if not COST_RE.match(l) and MARK not in l]
        same = (old.get("input_cost_per_token") is not None
                and float(old["input_cost_per_token"]) == float(new_in)
                and float(old.get("output_cost_per_token", "nan")) == float(new_out))
        if same:
            # Tarif inchangé : on garde la date de la dernière synchronisation.
            report.append(f"  =  {model} : {pin:g} → {pout:g} $/M")
            i = end
            continue
        added = [f"{indent}{MARK} synchronisé le {today} ($/M : {pin:g} → {pout:g})",
                 f"{indent}input_cost_per_token: {new_in}",
                 f"{indent}output_cost_per_token: {new_out}"]
        lines[i + 1:end] = kept + added
        before = (f"{float(old['input_cost_per_token']) * 1e6:g} → "
                  f"{float(old.get('output_cost_per_token', 0)) * 1e6:g}"
                  if "input_cost_per_token" in old else "aucun tarif")
        report.append(f"  ~  {model} : {before}  ⇒  {pin:g} → {pout:g} $/M")
        changed = True
        i = i + 1 + len(kept) + len(added)
    return "\n".join(lines), changed, report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="n'écrit rien, code 1 si un tarif diffère")
    args = ap.parse_args()
    try:
        pricing = fetch_pricing()
    except Exception as e:  # réseau, JSON : on n'écrit rien
        print(f"[sync-pricing] ERREUR: lecture de {URL} impossible ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    text = CONFIG.read_text(encoding="utf-8")
    new, changed, report = sync(text, pricing, datetime.date.today().isoformat())
    print("\n".join(report) or "  aucun modèle deepinfra/ dans config.yaml")
    if args.check:
        return 1 if changed else 0
    if changed:
        CONFIG.write_text(new, encoding="utf-8")
        print(f"[sync-pricing] {CONFIG.name} mis à jour : relire `git diff`, puis `oc diff -f`.")
    else:
        print("[sync-pricing] tarifs à jour, rien à écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
