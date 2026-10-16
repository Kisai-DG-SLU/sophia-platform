#!/usr/bin/env bash
# Conversion des voix françaises retenues (CML-TTS, CC-BY 4.0) en empreintes Pocket TTS,
# SUR LE NŒUD, dans un conteneur Linux jetable (pas de PyTorch pour les Mac Intel).
# La conversion demande la version « clonage » de Pocket TTS (accès restreint) ; le serveur
# garde la version sans clonage. Le jeton Hugging Face passe par l'environnement, jamais par la
# ligne de commande ni par un fichier.
#
# Prérequis, une fois : accepter les conditions sur https://huggingface.co/kyutai/pocket-tts,
# puis créer un jeton en lecture (Settings → Access Tokens).
# Usage (sur le nœud) :
#   read -rs HF_TOKEN; export HF_TOKEN      # coller le jeton, Entrée
#   sudo --preserve-env=HF_TOKEN bash export-voices.sh
#   unset HF_TOKEN
set -euo pipefail
[ -n "${HF_TOKEN:-}" ] || { echo "❌ HF_TOKEN absent (read -rs HF_TOKEN; export HF_TOKEN)"; exit 1; }
DEST=/var/mnt/models/voice/pocket-tts-fr/embeddings
REV=323332d33f997de8394f24a193e1a76df720e01a          # kyutai/tts-voices, figé le 
[ -d "$DEST" ] || { echo "❌ $DEST absent : lancer d'abord fetch-voice-models.sh"; exit 1; }

podman run --rm --network host -e HF_TOKEN -v "$DEST":/out:z docker.io/library/python:3.12-slim bash -euc "
  pip install -q --root-user-action=ignore 'pocket-tts==3.3.0' --extra-index-url https://download.pytorch.org/whl/cpu
  while read -r name file; do
    echo \"→ \$name\"
    pocket-tts export-voice --quiet --language french \
      \"hf://kyutai/tts-voices/cml-tts/fr/\${file}_enhanced.wav@$REV\" \"/out/\$name.safetensors\"
  done <<'LIST'
fr02 12080_11650_000047-0001
fr03 3267_1902_000075-0001
fr04 5830_4703_000037-0001
fr05 577_394_000070-0001
fr17 5476_3103_000072-0001
LIST
"
chmod a+r "$DEST"/fr*.safetensors
chcon -t container_file_t "$DEST"/fr*.safetensors
ls -la "$DEST"
