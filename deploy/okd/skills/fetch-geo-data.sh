#!/usr/bin/env bash
# Données géographiques de sophia-geo, préparées SUR LE NŒUD dans /var/mnt/models/skills/geo
# (sophia-skills n'a pas d'accès à Internet). geo_build.py tourne dans un conteneur Python jetable :
# communes (geo.api.gouv.fr), GeoNames cities1000 + noms français, pays Natural Earth.
# ≈ 230 Mo téléchargés, ≈ 8 Mo gardés. Mise à jour : relancer le script, puis redémarrer sophia-geo.
# Usage (sur le nœud, geo_build.py à côté du script) :
#   scp deploy/okd/skills/fetch-geo-data.sh deploy/okd/skills/geo_build.py core@${NODE_ADDR}:
#   ssh core@${NODE_ADDR} sudo bash fetch-geo-data.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DEST=/var/mnt/models/skills/geo
[ -f "$HERE/geo_build.py" ] || { echo "❌ geo_build.py absent à côté du script"; exit 1; }
mkdir -p "$DEST.new"
podman run --rm --network host -v "$HERE/geo_build.py":/geo_build.py:ro,z -v "$DEST.new":/out:z \
  docker.io/library/python:3.12-slim bash -euc "
    pip install -q --root-user-action=ignore pyshp==2.3.1
    python /geo_build.py /out"
# Remplacement d'un bloc : l'ancienne version reste en place si la préparation échoue
[ -s "$DEST.new/lieux.json.gz" ] && [ -s "$DEST.new/pays-10m.json.gz" ] || { echo "❌ préparation incomplète, rien n'est remplacé"; exit 1; }
rm -rf "$DEST.old"; [ -d "$DEST" ] && mv "$DEST" "$DEST.old"; mv "$DEST.new" "$DEST"; rm -rf "$DEST.old"
chmod -R a+rX /var/mnt/models/skills
chcon -R -t container_file_t /var/mnt/models/skills
cat "$DEST/sources.json" | head -3
du -sh "$DEST"
