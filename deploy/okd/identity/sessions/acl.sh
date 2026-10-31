#!/usr/bin/env bash
# Fichier d'ACL du Valkey des sessions, Secret sophia-identity/valkey-sessions-acl.
# Les mots de passe restent dans les Secrets de chaque application ; on ne lit ici que leur empreinte
# SHA-256 (`#<hex>`), seule à entrer dans le fichier. Rien n'est affiché d'autre.
#
#   bash deploy/okd/identity/sessions/acl.sh               affiche le fichier (empreintes seulement)
#   bash deploy/okd/identity/sessions/acl.sh --a-blanc     oc apply --dry-run=server du Secret
#   bash deploy/okd/identity/sessions/acl.sh --appliquer   oc apply du Secret
#
# Le fichier est construit en entier avant tout envoi : un fichier d'ACL vide ou sans `user default`
# rendrait l'utilisateur default actif sans mot de passe, avec tous les droits.
# Écrit pour le bash 3.2 du Mac : pas d'inherit_errexit, donc chaque $(…) est contrôlé à la main.
set -euo pipefail

MODE=${1:-}
case "$MODE" in ''|--a-blanc|--appliquer) ;; *) echo "acl.sh : option inconnue $MODE" >&2; exit 2 ;; esac

empreinte() {
  if command -v sha256sum >/dev/null; then sha256sum; else shasum -a 256; fi | cut -d' ' -f1
}

# Empreinte du mot de passe (clé `password`) d'un Secret ; refuse un Secret absent ou un mot de passe court.
empreinte_secret() {
  local ns=$1 secret=$2 taille h
  taille=$(oc -n "$ns" get secret "$secret" -o jsonpath='{.data.password}' | base64 -d | wc -c | tr -d ' ') || taille=0
  if [ "$taille" -lt 32 ]; then
    echo "acl.sh : $ns/$secret absent ou mot de passe de moins de 32 caractères" >&2
    exit 1
  fi
  h=$(oc -n "$ns" get secret "$secret" -o jsonpath='{.data.password}' | base64 -d | empreinte)
  [ ${#h} -eq 64 ] || { echo "acl.sh : empreinte illisible pour $ns/$secret" >&2; exit 1; }
  echo "$h"
}

# Commandes d'oauth2-proxy v7.15.5 (pkg/sessions/redis) : GET, SET avec expiration, DEL, PING ;
# verrou de rafraîchissement (bsm/redislock v0.10.0) : EXISTS, et des scripts Lua (EVALSHA, puis EVAL
# si le script n'est pas en cache) qui appellent MSETNX, MSET, MGET, GETRANGE, PEXPIRE, PTTL, DEL.
# Connexion de go-redis v9 : HELLO 3 avec AUTH, puis CLIENT SETINFO.
COMMANDES='+ping +hello +auth +client|setinfo +get +set +del +exists +mget +mset +msetnx +getrange +pexpire +pttl +evalsha +eval'

# Une application : utilisateur, namespace et Secret de son mot de passe, nom de son cookie.
# oauth2-proxy nomme ses clés `<cookie>-<ticket>` et son verrou `<cookie>-<ticket>.lock` : le motif
# `~<cookie>-*` les couvre, sans toucher aux clés d'une autre application (`_sophia-*` ne prend pas
# `_sophia_autre-…`).
application() {
  local utilisateur=$1 ns=$2 secret=$3 cookie=$4 h
  h=$(empreinte_secret "$ns" "$secret") || return 1
  echo "user $utilisateur reset on #$h ~$cookie-* $COMMANDES"
}

ACL="user default reset off"
# Contrôle en lecture (administrateur) : nombre de clés et mémoire, aucune clé lisible
h=$(empreinte_secret sophia-identity valkey-sessions-controle) || exit 1
ACL+=$'\n'"user controle reset on #$h +ping +hello +auth +info +dbsize"
ligne=$(application sophia-interface sophia-interface sophia-interface-sessions _sophia) || exit 1; ACL+=$'\n'"$ligne"
# Une autre application, avec son entrée dans 03-network.yaml (utilisateur, namespace, Secret, cookie) :
# ligne=$(application <application> <namespace> <application>-sessions <cookie>) || exit 1; ACL+=$'\n'"$ligne"

# Dernier contrôle : default désactivé, chaque autre utilisateur avec une empreinte de 64 caractères.
[ "$(printf '%s\n' "$ACL" | head -n 1)" = "user default reset off" ] || { echo "acl.sh : ligne default absente" >&2; exit 1; }
if printf '%s\n' "$ACL" | sed 1d | grep -v -E '^user [a-z-]+ reset on #[0-9a-f]{64} ' >/dev/null; then
  echo "acl.sh : ligne d'utilisateur mal formée, rien n'est envoyé" >&2
  exit 1
fi

case "$MODE" in
  '') printf '%s\n' "$ACL" ;;
  --a-blanc|--appliquer)
    blanc=--dry-run=none
    [ "$MODE" = --a-blanc ] && blanc=--dry-run=server
    printf '%s\n' "$ACL" | oc -n sophia-identity create secret generic valkey-sessions-acl \
      --from-file=users.acl=/dev/stdin --dry-run=client -o yaml | oc apply "$blanc" -f -
    ;;
esac
