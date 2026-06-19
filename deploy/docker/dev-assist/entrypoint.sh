#!/bin/bash
set -e

echo "Initialisation du workspace ${PROJECT_NAME:-default}..."

mkdir -p /home/${APP_USER:-app-user}/.ssh
if [ -f /tmp/workspace-secrets/id_ed25519 ]; then
    cp /tmp/workspace-secrets/id_ed25519.pub /home/${APP_USER:-app-user}/.ssh/authorized_keys
    cp /tmp/workspace-secrets/id_ed25519 /home/${APP_USER:-app-user}/.ssh/id_ed25519
    chmod 600 /home/${APP_USER:-app-user}/.ssh/id_ed25519 /home/${APP_USER:-app-user}/.ssh/authorized_keys
fi

cat <<EOF > /home/${APP_USER:-app-user}/.ssh/config
Host ${FORGEJO_SERVICE:-forgejo}
    Port 2222
    User git
    IdentityFile /home/${APP_USER:-app-user}/.ssh/id_ed25519
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
EOF

mkdir -p /home/${APP_USER:-app-user}/.config/opencode
ln -sf /mnt/rules/agent-context.md /home/${APP_USER:-app-user}/.config/opencode/AGENTS.md

rm -f /home/${APP_USER:-app-user}/.config/opencode/opencode.json

mkdir -p /home/${APP_USER:-app-user}/bin
cat <<'EOF_PROFILE' > /home/${APP_USER:-app-user}/.bash_profile
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi
EOF_PROFILE

{
    echo "export PATH=\$PATH:/home/${APP_USER:-app-user}/bin"
    echo "export PROJECT_NAME='${PROJECT_NAME:-default}'"
    echo "export PROJECT_ORG='${PROJECT_ORG:-default-org}'"
    echo "export GIT_SSH_COMMAND='ssh -F /home/${APP_USER:-app-user}/.ssh/config'"

    echo "export OPENAI_API_BASE='${LITELLM_SERVICE:-http://litellm:4000/v1}'"
    echo "export OPENAI_API_KEY='\$LITELLM_API_KEY'"

    echo "cd ${WORKSPACE_DIR:-/workspace}"
} >> /home/${APP_USER:-app-user}/.bashrc

cat <<'EOF_SCRIPT' > /home/${APP_USER:-app-user}/bin/memory-push
#!/bin/bash
export GIT_SSH_COMMAND="ssh -F /home/${APP_USER:-app-user}/.ssh/config"
PROJECT_NAME_FIXED="$PROJECT_NAME"
MESSAGE=${1:-"Memory save: $PROJECT_NAME_FIXED"}

git config --global user.name "${ADMIN_NAME:-Admin}"
git config --global user.email "${ADMIN_EMAIL:-admin@example.local}"

cd /tmp && rm -rf sync-repo
git clone git@${FORGEJO_SERVICE:-forgejo}:${ORG_NAME:-org}/${MEMORY_REPO:-memory-repo}.git sync-repo > /dev/null 2>&1
cd sync-repo && rm -rf "$PROJECT_NAME_FIXED" && mkdir -p "$PROJECT_NAME_FIXED"
cp -a /mnt/memory/. "$PROJECT_NAME_FIXED/"

git add "$PROJECT_NAME_FIXED/"
if git diff-index --quiet HEAD; then
    echo "Nothing to save."
else
    git commit -m "$MESSAGE" && git push
    echo "Memory synchronized."
fi
cd /home/${APP_USER:-app-user} && rm -rf /tmp/sync-repo && cd ${WORKSPACE_DIR:-/workspace}
EOF_SCRIPT

chmod +x /home/${APP_USER:-app-user}/bin/memory-push

export GIT_SSH_COMMAND="ssh -F /home/${APP_USER:-app-user}/.ssh/config"

git clone --depth 1 git@${FORGEJO_SERVICE:-forgejo}:${ORG_NAME:-org}/${MEMORY_REPO:-memory-repo}.git /tmp/memory-repo

SPEC_SOURCE=$(find /tmp/memory-repo -type d -name "$PROJECT_NAME" | head -n 1)

if [ -n "$SPEC_SOURCE" ]; then
    cp -r "$SPEC_SOURCE/." /mnt/memory/
fi
rm -rf /tmp/memory-repo

git clone git@${FORGEJO_SERVICE:-forgejo}:${PROJECT_ORG:-org}/$PROJECT_NAME.git ${WORKSPACE_DIR:-/workspace}

echo "Starting SSHD..."
/usr/sbin/sshd -D -e -p 2222
