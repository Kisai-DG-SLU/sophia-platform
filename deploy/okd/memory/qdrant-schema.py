#!/usr/bin/env python3
"""Schéma de la collection vectorielle de la mémoire (Qdrant) : collection et index de payload.

Un index par étiquette du schéma de la mémoire, sous son nom français. Idempotent : crée seulement
ce qui manque, ne supprime ni ne modifie rien. Un champ déjà indexé avec un autre type est signalé
(code de sortie 1), jamais changé. Bibliothèque standard seule.

Par un tunnel vers le Service de Qdrant :
    oc -n ${SOPHIA_MEMORY_NAMESPACE} port-forward svc/${QDRANT_SERVICE} 16333:6333
    python3 qdrant-schema.py --url http://127.0.0.1:16333            (lecture seule)
    python3 qdrant-schema.py --url http://127.0.0.1:16333 --apply
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

COLLECTION = "sophia_memory"  # changer avec --collection
VECTEURS = {"size": 1024, "distance": "Cosine"}  # BAAI/bge-m3

# Champ → type d'index Qdrant. Les champs libres (source) ne sont pas indexés.
INDEX = {
    "utilisateur": "keyword",
    "type_memoire": "keyword",
    "stockage": "keyword",
    "provenance": "keyword",
    "format": "keyword",
    "confidentialite": "keyword",
    "projet": "keyword",
    "theme": "keyword",
    "mots_cles": "keyword",
    "priorite": "keyword",
    "statut_arbitrage": "keyword",
    "confiance": "float",
    "version": "integer",
    "date_creation": "datetime",
    "date_maj": "datetime",
    "date_validation": "datetime",
    "date_expiration": "datetime",
}


def appel(base, methode, chemin, corps=None):
    req = urllib.request.Request(base.rstrip("/") + chemin, method=methode,
                                 data=None if corps is None else json.dumps(corps).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None


def main():
    global COLLECTION
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--collection", default=COLLECTION)
    a = ap.parse_args()
    COLLECTION = a.collection
    code, info = appel(a.url, "GET", f"/collections/{COLLECTION}")
    if code == 404:
        print(f"[à faire] collection {COLLECTION} {VECTEURS}")
        if a.apply:
            code, _ = appel(a.url, "PUT", f"/collections/{COLLECTION}", {"vectors": VECTEURS})
            if code != 200:
                sys.exit(f"création refusée (HTTP {code})")
            print(f"✓ collection {COLLECTION} créée")
            code, info = appel(a.url, "GET", f"/collections/{COLLECTION}")
        existant = {}
    elif code == 200:
        r = info["result"]
        v = r["config"]["params"]["vectors"]
        if v.get("size") != VECTEURS["size"] or v.get("distance") != VECTEURS["distance"]:
            sys.exit(f"collection {COLLECTION} : vecteurs {v}, attendu {VECTEURS} — arrêt, rien n'est modifié")
        print(f"✓ collection {COLLECTION} : {v}, {r.get('points_count')} points")
        existant = r.get("payload_schema") or {}
    else:
        sys.exit(f"Qdrant : HTTP {code}")
    ecarts = 0
    for champ, type_ in INDEX.items():
        deja = existant.get(champ, {}).get("data_type")
        if deja == type_:
            print(f"✓ {champ} : {type_}")
        elif deja:
            print(f"⚠ {champ} : indexé en {deja}, attendu {type_} — non modifié")
            ecarts += 1
        elif a.apply:
            c, _ = appel(a.url, "PUT", f"/collections/{COLLECTION}/index?wait=true",
                         {"field_name": champ, "field_schema": type_})
            if c != 200:
                sys.exit(f"index {champ} refusé (HTTP {c})")
            print(f"✓ {champ} : {type_} (créé)")
        else:
            print(f"[à faire] {champ} : {type_}")
    for champ in sorted(set(existant) - set(INDEX)):
        print(f"· {champ} : indexé hors schéma, laissé tel quel")
    if not a.apply:
        print("Lecture seule : rien n'a été modifié.")
    sys.exit(1 if ecarts else 0)


if __name__ == "__main__":
    main()
