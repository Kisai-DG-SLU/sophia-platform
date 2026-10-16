#!/usr/bin/env python3
"""Banc d'essai de l'inférence locale (SP0.9) — à lancer contre le NOUVEAU serveur seulement.

Trois mesures, avec des requêtes ordinaires (aucune entrée piège, aucune charge au-delà de
l'usage visé : 4 discussions en même temps) :
  1. appels d'outils : le modèle choisit le bon outil et produit des arguments JSON valides,
     puis exploite le résultat de l'outil (boucle à deux tours, comme l'interface) ;
  2. débit d'une discussion seule (tokens/s en génération, délai du premier token) ;
  3. débit à 4 discussions simultanées (par discussion et total).

Usage : python3 bench.py [URL]   (défaut : http://llama-server.sophia-inference.svc.cluster.local:8080/v1)
"""

import concurrent.futures as cf
import json
import sys
import time
import urllib.request

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://llama-server.sophia-inference.svc.cluster.local:8080/v1").rstrip("/")
MODEL = "sophia-local"

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search", "description": "Recherche sur le web. Renvoie titres, URL et extraits.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "weather_forecast", "description": "Prévisions météo d'un lieu, jour par jour.",
        "parameters": {"type": "object", "properties": {
            "place": {"type": "string"}, "days": {"type": "integer"}}, "required": ["place"]}}},
    {"type": "function", "function": {
        "name": "create_reminder", "description": "Crée un rappel pour la personne.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}, "when": {"type": "string", "description": "date ISO 8601"}},
            "required": ["text", "when"]}}},
]

CASES = [  # (question, outil attendu, argument qui doit apparaître)
    ("Quel temps fera-t-il demain à Pornic ?", "weather_forecast", "place"),
    ("Cherche les horaires d'ouverture de la médiathèque de Saint-Nazaire.", "web_search", "query"),
    ("Rappelle-moi d'appeler le dentiste le 20 octobre 2026 à 9 h.", "create_reminder", "when"),
    ("Quelle est la règle du hors-jeu au football ? Vérifie sur le web.", "web_search", "query"),
]

SYSTEM = "Tu es SophIA, une assistante familiale. Nous sommes le 16 octobre 2026. Utilise les outils quand c'est utile."


def post(path, body, stream=False, timeout=300):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def chat(messages, tools=None, max_tokens=512):
    body = {"model": MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    if tools:
        body["tools"] = tools
    with post("/chat/completions", body) as r:
        return json.load(r)


def tool_calls_test():
    ok = 0
    for question, expected, arg in CASES:
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
        t = time.time()
        r = chat(msgs, TOOLS)
        m = r["choices"][0]["message"]
        calls = m.get("tool_calls") or []
        verdict, detail = "❌", "aucun appel d'outil"
        if calls:
            c = calls[0]["function"]
            try:
                a = json.loads(c["arguments"])
                if c["name"] == expected and a.get(arg):
                    # second tour : résultat de l'outil fourni, le modèle doit l'exploiter
                    msgs += [m, {"role": "tool", "tool_call_id": calls[0].get("id", "0"),
                                 "content": json.dumps({"résultat": "donnée de test : 14 °C, ensoleillé"
                                                        if expected == "weather_forecast" else "donnée de test"})}]
                    r2 = chat(msgs, TOOLS, max_tokens=300)
                    m2 = r2["choices"][0]["message"]
                    answer = (m2.get("content") or "").strip()
                    again = [x["function"]["name"] for x in m2.get("tool_calls") or []]
                    # second tour valable : une réponse, ou un nouvel appel d'outil (l'agent relance)
                    verdict = "✅" if answer or again else "⚠️"
                    suite = f"réponse {len(answer)} car." if answer else f"relance {again}" if again else "réponse vide"
                    detail = f"{c['name']}({json.dumps(a, ensure_ascii=False)}) → {suite}"
                    ok += verdict == "✅"
                else:
                    detail = f"{c['name']}({c['arguments']}) — attendu {expected}.{arg}"
            except (json.JSONDecodeError, KeyError) as e:
                detail = f"arguments invalides : {c.get('arguments')!r} ({e})"
        print(f"  {verdict} {question[:55]:55} {time.time() - t:5.1f} s  {detail}")
    print(f"  → {ok}/{len(CASES)} boucles d'outils réussies")


def stream_once(prompt, max_tokens=400):
    body = {"model": MODEL, "stream": True, "max_tokens": max_tokens, "temperature": 0.7,
            "messages": [{"role": "user", "content": prompt}],
            "stream_options": {"include_usage": True}}
    t0 = time.time(); first = None; n = 0; usage = None
    with post("/chat/completions", body, timeout=600) as r:
        for raw in r:
            line = raw.decode().strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            e = json.loads(line[5:])
            if e.get("usage"):
                usage = e["usage"]
            for c in e.get("choices") or []:
                d = c.get("delta") or {}
                if d.get("content") or d.get("reasoning_content"):
                    first = first or time.time()
                    n += 1
    end = time.time()
    toks = (usage or {}).get("completion_tokens") or n
    gen = end - (first or end)
    return {"ttft": (first or end) - t0, "tokens": toks, "tps": toks / gen if gen > 0 else 0, "total": end - t0}


PROMPTS = [
    "Explique en quelques paragraphes comment fonctionne la photosynthèse.",
    "Raconte une courte histoire pour une enfant de 8 ans, avec un chat et un phare.",
    "Donne un plan de révision d'une semaine pour un contrôle d'histoire sur la Révolution française.",
    "Propose trois idées de repas végétariens simples, avec la liste des courses.",
]


def main():
    print(f"Serveur : {URL}")
    with urllib.request.urlopen(URL.rsplit("/v1", 1)[0] + "/health", timeout=10) as r:
        print("  santé :", r.read().decode().strip())

    print("\n1. Appels d'outils")
    tool_calls_test()

    print("\n2. Une discussion seule")
    s = stream_once(PROMPTS[0])
    print(f"  premier token {s['ttft']:.2f} s · {s['tokens']} tokens · {s['tps']:.1f} tokens/s")

    print("\n3. Quatre discussions en même temps")
    t = time.time()
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(stream_once, PROMPTS))
    wall = time.time() - t
    for i, s in enumerate(res, 1):
        print(f"  #{i} premier token {s['ttft']:.2f} s · {s['tokens']} tokens · {s['tps']:.1f} tokens/s")
    total = sum(s["tokens"] for s in res)
    print(f"  → {total / wall:.1f} tokens/s au total, {min(s['tps'] for s in res):.1f} tokens/s pour la plus lente")


if __name__ == "__main__":
    main()
