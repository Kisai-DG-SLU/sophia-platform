#!/bin/bash
# Vérifie que le ruleset COMPLET du nœud reste lisible par le nft embarqué dans
# OVN-Kubernetes (voir l'avertissement en tête de wg-filter.nft).
#
# Codes : 0 lisible · 1 illisible → table inet sophia_wg SUPPRIMÉE, alerte
#         (le cluster prime : le VPN reste ouvert, sans filtre, jamais coupé)
#         2 vérification impossible (pas de nft OVN joignable) → table conservée, avertissement
#
# Appelé par sophia-wg-filter.service (après chargement) et sophia-wg-filter-check.timer.
set -u
CACHE=/var/lib/sophia/ovn-nft-image   # image OVN de la dernière vérification réussie
log() { logger -t sophia-wg-filter -p "daemon.$1" -- "$2"; echo "$2" >&2; }

# Lance « nft list ruleset » avec le nft d'OVN. Affiche le code de nft lui-même,
# ou « ? » si la vérification n'a pas pu avoir lieu.
ovn_list_rc() {
    local cid img out rc
    cid=$(crictl ps --name '^ovn-controller$' -q 2>/dev/null | head -1)
    if [ -n "$cid" ]; then
        # 1. OVN tourne : son conteneur ovn-controller
        img=$(crictl inspect -o go-template --template '{{.status.imageRef}}' "$cid" 2>/dev/null)
        out=$(crictl exec "$cid" nft list ruleset 2>&1 >/dev/null); rc=$?
        if [ $rc -eq 0 ]; then
            [ -n "$img" ] && mkdir -p "${CACHE%/*}" && echo "$img" > "$CACHE"
            echo 0; return
        fi
        # crictl rend le code de la commande dans son message (« exit code 139 »)
        rc=$(echo "$out" | sed -n 's/.*exit code \([0-9]\+\).*/\1/p' | head -1)
        echo "${rc:-?}"; return
    fi
    # 2. Démarrage du nœud (CRI-O pas encore là) : même image, lancée par podman
    img=$(cat "$CACHE" 2>/dev/null)
    [ -n "$img" ] || { echo "?"; return; }
    podman run --rm --pull=never --net=host --cap-add=NET_ADMIN --security-opt label=disable \
        --entrypoint nft "$img" list ruleset >/dev/null 2>&1; rc=$?
    case $rc in 125|126|127) echo "?" ;; *) echo $rc ;; esac
}

rc=$(ovn_list_rc)
case $rc in
    0)  log info "ruleset lisible par le nft d'OVN-Kubernetes"; exit 0 ;;
    \?) log warning "vérification impossible (OVN injoignable, pas d'image en cache) — table inet sophia_wg conservée"; exit 2 ;;
    *)  nft delete table inet sophia_wg 2>/dev/null
        log crit "ALERTE : ruleset illisible par le nft d'OVN (code $rc) — table inet sophia_wg SUPPRIMÉE pour protéger le cluster, VPN NON FILTRÉ (jamais coupé). Voir /etc/sophia/wg-filter.nft."
        exit 1 ;;
esac
