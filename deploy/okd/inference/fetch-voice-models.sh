#!/usr/bin/env bash
# Modèles vocaux de sophia-voice, déposés DEPUIS LE NŒUD dans /var/mnt/models/voice
# (sophia-inference n'a pas d'accès à Internet). Révisions Hugging Face et SHA-256 figés.
# Usage (sur le nœud) : sudo bash fetch-voice-models.sh
set -euo pipefail
ROOT=/var/mnt/models/voice
TTS=https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/resolve/575d14372df89a4534bcb989870a34e77544b09f/languages/french
ASR=https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/resolve/8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce

fetch() {  # fetch URL DESTINATION SHA256
    if [ -f "$2" ] && echo "$3  $2" | sha256sum -c --status; then echo "✓ $2 (déjà là)"; return; fi
    curl -fL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
    echo "$3  $2" | sha256sum -c --quiet && echo "✓ $2"
}

mkdir -p $ROOT/pocket-tts-fr/embeddings $ROOT/parakeet-v3
fetch $TTS/model.safetensors             $ROOT/pocket-tts-fr/model.safetensors                56366cfed6c25bfcd3bf4c61e66e06efaf52e78a5d06e1dcade1c588495bc699
fetch $TTS/tokenizer.json                $ROOT/pocket-tts-fr/tokenizer.json                   6211acffe9cb95172f71f0051f18e26ea305b2b32ea00b331ee976551c70887f
fetch $TTS/tokenizer.model               $ROOT/pocket-tts-fr/tokenizer.model                  dd8dc8cfad3c4b3711a8629ede27d5be934eb98bcb00462bf91ed40fb8f6f38a
fetch $TTS/embeddings/estelle.safetensors $ROOT/pocket-tts-fr/embeddings/estelle.safetensors  d9efd55657f74ba9483caec23f9fd1d155e121b058feef86af3760d54ea8aa15
fetch $ASR/config.json                   $ROOT/parakeet-v3/config.json                        666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466
fetch $ASR/vocab.txt                     $ROOT/parakeet-v3/vocab.txt                          d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d
fetch $ASR/nemo128.onnx                  $ROOT/parakeet-v3/nemo128.onnx                       a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f
fetch $ASR/encoder-model.int8.onnx       $ROOT/parakeet-v3/encoder-model.int8.onnx            6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09
fetch $ASR/decoder_joint-model.int8.onnx $ROOT/parakeet-v3/decoder_joint-model.int8.onnx      eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70

chmod -R a+rX $ROOT
chcon -R -t container_file_t $ROOT
du -sh $ROOT/*
