#!/bin/bash
# Teste, expression par expression, ce que le nft embarqué dans OVN-Kubernetes sait relire.
# sudo bash test-nft-ovn.sh — tables de test SANS chaîne de base (aucun hook, aucun effet
# sur le trafic), chacune supprimée aussitôt. Ne touche ni à OVN, ni à OpenShift, ni à wg0.
# Adresses de documentation (RFC 5737) et ports neutres : seule la syntaxe compte ici.
# Attendu (OKD 4.21, nft OVN 1.0.9) : 02, 03, 06, 07, 21 → 139 (sets nommés) ; tout le reste → 0.
set -u
CID=$(crictl ps --name '^ovn-controller$' -q | head -1); [ -n "$CID" ] || { echo "ovn-controller introuvable"; exit 1; }
echo "hôte: $(nft --version) | OVN: $(crictl exec "$CID" nft --version)"
cleanup() { nft list tables | awk '$3 ~ /^sophia_t_/ {print $2, $3}' | while read f n; do nft delete table "$f" "$n"; done; }
trap cleanup EXIT INT TERM
# t <id> <famille d'adresses> <set: none|interval|plain> <règle>
t() { local id=$1 fam=$2 set=$3 body=$4 sd=""
  case $set in
    interval) sd='set admins { type ipv4_addr; flags interval; elements = { 192.0.2.2-192.0.2.9 } }' ;;
    plain)    sd='set admins { type ipv4_addr; elements = { 192.0.2.2, 192.0.2.3, 192.0.2.4, 192.0.2.5, 192.0.2.6, 192.0.2.7, 192.0.2.8, 192.0.2.9 } }' ;;
  esac
  nft -f - <<EOT || { echo "$id  refusé par nft hôte : $body"; return; }
table $fam sophia_t_$id {
  $sd
  chain c {
    $body
  }
}
EOT
  out=$(crictl exec "$CID" nft list table "$fam" "sophia_t_$id" 2>&1 >/dev/null); rc=$?
  nft delete table "$fam" "sophia_t_$id"
  printf '%s rc=%-3s [%s|set:%s] %s\n' "$id" "$rc" "$fam" "$set" "$body"
  [ $rc -ne 0 ] && [ -n "$out" ] && echo "      ↳ $(echo "$out" | head -3 | tr '\n' ' ')"; }
t 01 inet none     ''
t 02 inet interval ''
t 03 inet plain    ''
t 04 inet none     'ip saddr { 192.0.2.2-192.0.2.9 } accept'
t 05 inet none     'ip saddr 192.0.2.2-192.0.2.9 accept'
t 06 inet plain    'ip saddr @admins accept'
t 07 ip   interval ''
t 10 inet none 'iifname != "wg0" accept'
t 11 inet none 'ct state established,related accept'
t 12 inet none 'tcp dport { 80, 443 } accept'
t 13 inet none 'icmp type echo-request accept'
t 14 inet none 'counter drop comment "VPN : rien de relayé hors Forgejo (admin)"'
t 15 inet none 'ct original ip daddr 192.0.2.1 accept'
t 16 inet none 'meta nfproto ipv4 ct original daddr 192.0.2.1 accept'
t 17 inet none 'ct status dnat accept'
t 20 inet none  'ip saddr 192.0.2.2-192.0.2.9 ct original ip daddr 192.0.2.1 tcp dport { 8022, 8080 } accept'
t 21 inet plain 'ip saddr @admins ct original ip daddr 192.0.2.1 tcp dport { 8022, 8080 } accept'
echo "restantes : $(nft list tables | grep -c sophia_t_)"   # doit afficher 0
