#!/bin/bash
# Banc local (jamais sur le nœud) : compare l'ancien garde-fou (celui qui tourne sur le nœud) et le
# nouveau (métrique) avec de faux crictl, podman, nft et logger. Pour chaque scénario OVN et chaque état du
# fichier de métrique (inscriptible, absent, en erreur), le code de sortie et la suite exacte des
# actions (nft delete, logger…) doivent être identiques. Usage, depuis la racine du dépôt :
#   bash deploy/okd/host/wireguard/test-garde-fou-metrique.sh <copie de l'ancien wg-filter-check.sh>
set -u
# Le garde-fou s'exécute sur le nœud avec le sed GNU (« \+ » dans ses expressions) : un banc lancé
# avec le sed BSD de macOS ne rejouerait pas le même comportement. Lancer sous Linux (faux outils
# locaux seulement, rien ne touche le nœud).
if ! sed --version >/dev/null 2>&1; then
  echo "banc à lancer sous Linux (sed GNU, comme sur le nœud) : rien n'est comparé" >&2
  exit 2
fi
[ -f "${1:-}" ] || { echo "usage : $0 <copie de l'ancien wg-filter-check.sh>" >&2; exit 2; }
empreinte() { if command -v md5sum >/dev/null; then md5sum; else md5 -q; fi; }
B=$(mktemp -d)
trap 'rm -rf "$B"' EXIT
mkdir -p "$B/bin"
cp "$1" "$B/ancien.sh"
cp deploy/okd/host/wireguard/wg-filter-check.sh "$B/nouveau.sh"
cat > "$B/bin/crictl" <<'X'
#!/bin/bash
echo "crictl $*" >> "$TRACE"
case "$1" in
  ps) case "$SCEN" in podman_ok|podman_ko|rien) ;; *) echo cid123 ;; esac ;;
  inspect) echo "quay.io/ovn@sha256:abc" ;;
  exec) case "$SCEN" in ok) exit 0 ;; illisible) echo "command terminated with exit code 139" >&2; exit 1 ;; esac ;;
esac
X
cat > "$B/bin/podman" <<'X'
#!/bin/bash
echo "podman $*" >> "$TRACE"
case "$SCEN" in podman_ok) exit 0 ;; podman_ko) exit 1 ;; *) exit 127 ;; esac
X
printf '#!/bin/bash\necho "nft $*" >> "$TRACE"\n' > "$B/bin/nft"
printf '#!/bin/bash\necho "logger $*" >> "$TRACE"\n' > "$B/bin/logger"
chmod +x "$B"/bin/*
run() {
  local s="$B/$1.$2.$3.sh" t="$B/trace.$1.$2.$3" cache="$B/cache.$1.$2.$3"
  sed -e "s#CACHE=/var/lib/sophia/ovn-nft-image#CACHE=$cache#" "$B/$1.sh" > "$s"
  case $3 in
    inscriptible) sed -i.bak "s#METRIQUE=/var/lib/sophia/metrics/wg_filter.prom#METRIQUE=$B/m.$2/wg_filter.prom#" "$s" ;;
    absent) sed -i.bak "s#METRIQUE=/var/lib/sophia/metrics/wg_filter.prom#METRIQUE=/proc/interdit/wg_filter.prom#" "$s" ;;
    erreur) mkdir -p "$B/err.$2/wg_filter.prom"; sed -i.bak "s#METRIQUE=/var/lib/sophia/metrics/wg_filter.prom#METRIQUE=$B/err.$2/wg_filter.prom#" "$s" ;;
  esac
  case $2 in podman_ok|podman_ko) echo "quay.io/ovn@sha256:abc" > "$cache" ;; esac
  : > "$t"; PATH="$B/bin:/usr/bin:/bin" TRACE="$t" SCEN="$2" bash "$s" 2>/dev/null
  echo "$? $(empreinte < "$t" | cut -c1-8)"
}
ecart=0
for sc in ok illisible podman_ok podman_ko rien; do
  for mc in inscriptible absent erreur; do
    a=$(run ancien $sc $mc); n=$(run nouveau $sc $mc)
    if [ "$a" = "$n" ]; then r=identique; else r=ÉCART; ecart=1; fi
    printf '%-10s %-12s ancien=%s nouveau=%s %s\n' "$sc" "$mc" "$a" "$n" "$r"
  done
done
[ $ecart -eq 0 ] && echo "AUCUN ÉCART (15 cas)" || { echo "ÉCART : ne pas installer"; exit 1; }
