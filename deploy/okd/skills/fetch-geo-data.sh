#!/usr/bin/env bash
# Données géographiques de sophia-geo, préparées SUR LE NŒUD dans /var/mnt/models/skills/geo
# (sophia-skills n'a pas d'accès à Internet). geo_build.py tourne dans un conteneur Python jetable :
# communes (geo.api.gouv.fr), GeoNames cities1000 + noms français, pays Natural Earth.
# ≈ 230 Mo téléchargés, ≈ 8 Mo gardés. Mise à jour : relancer le script, puis redémarrer sophia-geo.
# --ban <dép> <dép>… ajoute les adresses de la Base Adresse Nationale de ces départements (ban.sqlite). La liste
# est donnée au lancement, jamais écrite dans un dépôt ; sans --ban, la liste de la préparation précédente est reprise.
# Usage (sur le nœud, geo_build.py et ban.py à côté du script) :
#   scp deploy/okd/skills/fetch-geo-data.sh deploy/okd/skills/geo_build.py deploy/okd/skills/ban.py core@${NODE_ADDR}:
#   ssh core@${NODE_ADDR} sudo bash fetch-geo-data.sh [--ban <dép> <dép>…]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
DEST=/var/mnt/models/skills/geo
[ -f "$HERE/geo_build.py" ] && [ -f "$HERE/ban.py" ] || { echo "❌ geo_build.py ou ban.py absent à côté du script"; exit 1; }
BAN=()
if [ "${1:-}" = "--ban" ]; then
  shift; BAN=("$@")
  [ ${#BAN[@]} -gt 0 ] || { echo "❌ --ban sans département"; exit 1; }
elif [ -f "$DEST/ban-departements" ]; then
  mapfile -t BAN < "$DEST/ban-departements"
fi
for d in "${BAN[@]}"; do
  [[ "$d" =~ ^(0[1-9]|1[0-9]|2[1-9]|2A|2B|[3-8][0-9]|9[0-5]|97[1-6])$ ]] || { echo "❌ département invalide : $d"; exit 1; }
done
rm -rf "$DEST.new"; mkdir -p "$DEST.new"
podman run --rm --network host -e BAN="${BAN[*]}" -v "$HERE/geo_build.py":/w/geo_build.py:ro,z \
  -v "$HERE/ban.py":/w/ban.py:ro,z -v "$DEST.new":/out:z docker.io/library/python:3.12-slim bash -euc '
    pip install -q --root-user-action=ignore pyshp==2.3.1
    python /w/geo_build.py /out "" ${BAN:+--ban $BAN}' || { echo "❌ préparation en échec, rien n'est remplacé"; exit 1; }
[ ${#BAN[@]} -eq 0 ] || printf '%s\n' "${BAN[@]}" > "$DEST.new/ban-departements"
# Remplacement d'un bloc : l'ancienne version reste en place si la préparation échoue
[ -s "$DEST.new/lieux.json.gz" ] && [ -s "$DEST.new/pays-10m.json.gz" ] || { echo "❌ préparation incomplète, rien n'est remplacé"; exit 1; }
[ ${#BAN[@]} -eq 0 ] || [ -s "$DEST.new/ban.sqlite" ] || { echo "❌ ban.sqlite absent, rien n'est remplacé"; exit 1; }
rm -rf "$DEST.old"; [ -d "$DEST" ] && mv "$DEST" "$DEST.old"; mv "$DEST.new" "$DEST"; rm -rf "$DEST.old"
chmod -R a+rX /var/mnt/models/skills
chcon -R -t container_file_t /var/mnt/models/skills
cat "$DEST/sources.json" | head -3
du -sh "$DEST"
