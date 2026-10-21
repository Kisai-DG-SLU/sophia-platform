#!/usr/bin/env bash
# Ajoute un appareil au VPN (pair WireGuard) dans le profil NetworkManager wg0.
#
# La clé privée de l'appareil est générée par l'application WireGuard et ne le quitte
# jamais : seule sa clé PUBLIQUE est donnée ici. Aucun secret n'est lu ni affiché.
#
# Usage (sur le nœud) :  sudo VPN_PREFIX=… VPN_HOST_MIN=… VPN_HOST_MAX=… \
#                          ./add-peer.sh <nom> <adresse VPN> <clé publique de l'appareil>
#   VPN_PREFIX    les trois premiers octets du réseau VPN (/24), sans point final
#   VPN_HOST_MIN  premier dernier-octet attribuable (après l'adresse du serveur)
#   VPN_HOST_MAX  dernier dernier-octet attribuable
# Plages d'administration et des utilisateurs : voir wg-filter.nft et README.md.
set -euo pipefail

CONF=/etc/NetworkManager/system-connections/wg0.nmconnection
: "${VPN_PREFIX:?VPN_PREFIX non défini (voir README.md)}"
: "${VPN_HOST_MIN:?VPN_HOST_MIN non défini}" "${VPN_HOST_MAX:?VPN_HOST_MAX non défini}"
name="${1:-}"; ip="${2:-}"; pub="${3:-}"

[ "$(id -u)" = 0 ] || { echo "❌ à lancer avec sudo"; exit 1; }
[[ "$name" =~ ^[a-z0-9-]{2,40}$ ]] || { echo "❌ nom : minuscules, chiffres, tirets"; exit 1; }
[[ "$ip" =~ ^${VPN_PREFIX//./\\.}\.([0-9]{1,3})$ ]] && o="${BASH_REMATCH[1]}" \
    && [ "$o" -ge "$VPN_HOST_MIN" ] && [ "$o" -le "$VPN_HOST_MAX" ] \
    || { echo "❌ adresse : $VPN_PREFIX.$VPN_HOST_MIN à $VPN_PREFIX.$VPN_HOST_MAX"; exit 1; }
[[ "$pub" =~ ^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=$ ]] || { echo "❌ clé publique WireGuard invalide (44 caractères base64)"; exit 1; }
grep -q "^\[wireguard-peer\.$pub\]" "$CONF" && { echo "❌ cette clé est déjà déclarée"; exit 1; }
grep -q "^allowed-ips=$ip/32;" "$CONF" && { echo "❌ $ip est déjà attribuée"; exit 1; }

cp -p "$CONF" "$CONF.bak-$(date +%Y%m%d-%H%M%S)"
printf '\n# %s (%s)\n[wireguard-peer.%s]\nallowed-ips=%s/32;\npersistent-keepalive=25\n' \
    "$name" "$(date +%F)" "$pub" "$ip" >> "$CONF"
chmod 600 "$CONF"

nmcli connection reload
# reapply : applique les pairs sans couper les tunnels existants ; sinon redémarrage de wg0.
nmcli device reapply wg0 2>/dev/null && echo "✓ $name → $ip (sans coupure)" \
    || { nmcli connection up wg0 >/dev/null && echo "✓ $name → $ip (wg0 redémarré)"; }
