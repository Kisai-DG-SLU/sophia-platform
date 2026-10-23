#!/usr/bin/env bash
# Modèles de sophia-image, déposés DEPUIS LE NŒUD dans /var/mnt/models/image
# (sophia-inference n'a pas d'accès à Internet). Révisions Hugging Face et SHA-256 figés.
#   - SDXL-Turbo fp16 (Stability AI, licence sai-nc-community : usage NON commercial)
#   - TAESDXL (décodeur rapide, MIT)
#   - classifieur Falconsai/nsfw_image_detection (Apache 2.0), contrôle des images générées
# Usage (sur le nœud) : sudo bash fetch-image-models.sh      (≈ 7,3 Go)
set -euo pipefail
ROOT=/var/mnt/models/image
HF=https://huggingface.co

fetch() {  # fetch URL DESTINATION SHA256
    if [ -f "$2" ] && echo "$3  $2" | sha256sum -c --status; then echo "✓ $2 (déjà là)"; return; fi
    curl -fL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
    echo "$3  $2" | sha256sum -c --quiet && echo "✓ $2"
}

mkdir -p $ROOT/nsfw
fetch $HF/stabilityai/sdxl-turbo/resolve/71153311d3dbb46851df1931d3ca6e939de83304/sd_xl_turbo_1.0_fp16.safetensors \
      $ROOT/sd_xl_turbo_1.0_fp16.safetensors e869ac7d6942cb327d68d5ed83a40447aadf20e0c3358d98b2cc9e270db0da26
fetch $HF/madebyollin/taesdxl/resolve/b20258aaef75ef61e659c1e0f14f251cf0ad153e/diffusion_pytorch_model.safetensors \
      $ROOT/taesdxl.safetensors ff4824aca94dd6111e0340fa749347fb74101060d9712cb5ef1ca8f1cf17502f
fetch $HF/Falconsai/nsfw_image_detection/resolve/96cb0d0342c7afb80cab76ecc58b265fa44da256/model.safetensors \
      $ROOT/nsfw/model.safetensors 97b2ce64ec146884b37f98ee7944ca4891aa72f6827dc0cb10684a1cbecd5830

chmod -R a+rX $ROOT
chcon -R -t container_file_t $ROOT
du -sh $ROOT/*
