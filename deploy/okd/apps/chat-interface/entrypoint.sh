#!/bin/sh
# Démarrage du conteneur de production : rendu puis nginx au premier plan.
# render-config.py refuse une clé mal formée (code 1) : le pod ne démarre pas
# plutôt que de servir une configuration cassée. render-pricing.py ne bloque
# jamais (tarifs à 0 si LiteLLM est injoignable).
set -eu
cd /mnt/prod
python3 deploy/render-config.py
python3 deploy/render-pricing.py
# Tarifs relus en tâche de fond : toutes les 30 s tant que LiteLLM ne répond pas
# (démarrage pendant une panne), puis toutes les 10 min (changement de prix).
( while :; do
      if python3 deploy/render-pricing.py --status >/dev/null 2>&1; then sleep 600; else sleep 30; fi
  done ) &
exec nginx -c /mnt/prod/deploy/nginx.conf -e /dev/stderr -g 'daemon off;'
