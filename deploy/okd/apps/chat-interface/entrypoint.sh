#!/bin/sh
# Démarrage du conteneur de production : rendu puis nginx au premier plan.
# render-config.py refuse une clé mal formée (code 1) : le pod ne démarre pas
# plutôt que de servir une configuration cassée. render-pricing.py ne bloque
# jamais (tarifs à 0 si LiteLLM est injoignable).
set -eu
cd /mnt/prod
python3 deploy/render-config.py
python3 deploy/render-pricing.py
exec nginx -c /mnt/prod/deploy/nginx.conf -e /dev/stderr -g 'daemon off;'
