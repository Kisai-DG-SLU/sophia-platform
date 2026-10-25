#!/usr/bin/env python3
"""Rendu de deploy/nginx.conf (gitignoré) depuis nginx.conf.in (tracké).

Substitue ${LITELLM_AUTH} par la valeur de LITELLM_API_KEY issue de
l'environnement du conteneur (injectée par OKD : secretKeyRef →
litellm-secret/api-key).

Règles :
- la clé n'est JAMAIS affichée, ni imprimée, ni écrite ailleurs qu' dans
  deploy/nginx.conf (mode 600) ;
- clé absente ou vide → `proxy_set_header Authorization "";`
  (suppression de l'en-tête, LiteLLM répondra 401) ;
- caractère interdit dans la clé (guillemet, antislash, retour ligne) →
  erreur fatale : on refuse d'écrire une conf cassée.

Usage : python3 deploy/render-config.py
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / "nginx.conf.in"
OUTPUT = BASE / "nginx.conf"
MARKER = "${LITELLM_AUTH}"
# Routes de la voix : une clé LiteLLM à part, limitée aux modèles audio locaux (sophia-stt, sophia-tts),
# pour que le navigateur ne puisse pas y viser un modèle distant. Absente : clé du pod (ancien comportement).
AUDIO_MARKER = "${LITELLM_AUDIO_AUTH}"


def main() -> int:
    if not TEMPLATE.exists():
        print(f"[render] ERREUR: template introuvable: {TEMPLATE}", file=sys.stderr)
        return 1

    key = os.environ.get("LITELLM_API_KEY", "").strip()
    audio_key = os.environ.get("LITELLM_AUDIO_API_KEY", "").strip()
    if audio_key and any(c in audio_key for c in '"\\\n\r'):
        print("[render] ERREUR: LITELLM_AUDIO_API_KEY contient des caractères interdits.", file=sys.stderr)
        return 1

    if key:
        if any(c in key for c in '"\\\n\r'):
            # On ne relaye jamais le contenu de la clé, même en erreur.
            print(
                "[render] ERREUR: LITELLM_API_KEY contient des caractères "
                "interdits (guillemet / antislash / retour ligne).",
                file=sys.stderr,
            )
            return 1
        auth = f'"Bearer {key}"'
        print(
            f"[render] identité LiteLLM injectée depuis l'env "
            f"({len(key)} caractères, valeur non affichée)."
        )
    else:
        auth = '""'
        print(
            "[render] AVERTISSEMENT: LITELLM_API_KEY absente de l'env → "
            "aucun en-tête Authorization (LiteLLM répondra 401).",
            file=sys.stderr,
        )

    text = TEMPLATE.read_text(encoding="utf-8")
    if text.count(MARKER) < 1:
        print(
            f"[render] ERREUR: marqueur {MARKER} absent du template.",
            file=sys.stderr,
        )
        return 1

    if audio_key:
        audio_auth = f'"Bearer {audio_key}"'
        print(f"[render] clé audio dédiée injectée ({len(audio_key)} caractères, valeur non affichée).")
    else:
        audio_auth = auth
        if AUDIO_MARKER in text:
            print("[render] AVERTISSEMENT: LITELLM_AUDIO_API_KEY absente → routes de la voix avec la clé du pod "
                  "(modèle choisi par le navigateur non borné aux modèles audio).", file=sys.stderr)

    OUTPUT.write_text(text.replace(AUDIO_MARKER, audio_auth).replace(MARKER, auth), encoding="utf-8")
    OUTPUT.chmod(0o600)
    print(f"[render] {OUTPUT} généré (mode 600).")
    return 0


if __name__ == "__main__":
    sys.exit(main())