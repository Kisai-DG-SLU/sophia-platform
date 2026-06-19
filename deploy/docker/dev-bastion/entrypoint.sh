#!/bin/bash
set -e

mkdir -p /home/${APP_USER:-app-user}/.ssh
if [ -f /tmp/ssh-pubkey/id_ed25519.pub ]; then
    cp /tmp/ssh-pubkey/id_ed25519.pub /home/${APP_USER:-app-user}/.ssh/authorized_keys
elif [ -f /tmp/ssh-pubkey/id_rsa.pub ]; then
    cp /tmp/ssh-pubkey/id_rsa.pub /home/${APP_USER:-app-user}/.ssh/authorized_keys
fi

chown -R ${APP_USER:-app-user}:${APP_USER:-app-user} /home/${APP_USER:-app-user}/.ssh
chmod 700 /home/${APP_USER:-app-user}/.ssh
chmod 600 /home/${APP_USER:-app-user}/.ssh/authorized_keys

echo "Starting SSH bastion gateway on port 2222..."
exec /usr/sbin/sshd -D -e
