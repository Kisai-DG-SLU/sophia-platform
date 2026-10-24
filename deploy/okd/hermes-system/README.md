# Deploiement du Pantheon Agentique Sophia

Ce repertoire contient les manifests OpenShift/Kubernetes pour deployer le **Pantheon Agentique SophIA** — une architecture multi-agents basee sur le zero-trust et la segmentation RBAC stricte.

## Ordre de deploiement

Les manifests doivent etre appliques sequentiellement pour satisfaire les dependances :

1. `01-agent-build.yaml` — Namespace, ServiceAccount, ImageStream, BuildConfig
2. `02-observer-dionysos.yaml` — (Optionnel) Pod observateur Dionysos pour le diagnostic du cluster
3. `03-agent-config.yaml` — ConfigMap avec les endpoints RAG et la configuration LLM
4. `04-agent-deployment-sophia.yaml` — Deploiement principal de l'agent Sophia
5. `05-gods-rbac.yaml` — ServiceAccounts et RBAC pour les agents specialises
6. `06-gods-deployments.yaml` — Deploiements d'Athena, Hephaistos, Ouranos
7. `07-network-policies.yaml` — Politiques reseau pour l'isolation zero-trust
8. `08-services.yaml` — Services internes headless pour le routage des agents
9. `09-executants-network.yaml` — entrée de l'`api_server` d'un exécutant ouverte au seul [répartiteur](../core/repartiteur/)
10. `10-recette-repartiteur.yaml` — Job de recette : une mission « pong » demandée au répartiteur par le vrai chemin

## Agnosticisme des modeles

Chaque pod agent est configure independamment via sa variable d'environnement `AGENT_MODEL`. Sophia peut utiliser un modele de raisonnement puissant (`${MODEL_THINK}`) tandis que ses sous-agents utilisent un modele plus leger et rapide (`${MODEL_ROUTINE}`). Chaque deite dans `06-gods-deployments.yaml` possede sa propre configuration de modele.

Etant donne que le comportement agentique est enforce par l'infrastructure (RBAC, NetworkPolicies, validation du format de sortie) plutot que par le modele lui-meme, l'architecture fonctionne avec n'importe quel modele — des petits modeles locaux aux grandes API publiques. Vous pouvez meme deployer un agent sans backend IA si son role est purement deterministe.

Les variables d'environnement `${AGENT_MODEL}`, `${OPENAI_API_BASE_URL}` et `${OPENAI_API_KEY}` dans le ConfigMap et les Secrets controlent le modele utilise par chaque agent.

## Assistant de code persistant (Dionysos)

Dionysos peut heberger un assistant de code (Claude Code) pour l'administration. Son volume `/opt/data` est un `emptyDir` : il survit au redemarrage du noeud, pas a la recreation du pod. Pour que l'assistant, sa configuration et son historique survivent, `02-observer-dionysos.yaml` ajoute :

| Element | Role |
|---|---|
| initContainer `init-claude` | restaure la configuration et l'historique depuis un depot Git prive dedie (`${CLAUDE_REPO}`), puis installe l'assistant a la version `${CLAUDE_CODE_VERSION}` si elle manque ; idempotent (rejoue apres un redemarrage du noeud sans ecraser le travail local) |
| sidecar natif `claude-sync` | pousse l'historique toutes les `${CLAUDE_SYNC_INTERVAL}` secondes, a chaque fin de session (un hook `SessionEnd` de l'assistant cree `/opt/data/.claude-home/.sync-request`, couvre `/clear` et la sortie) et a l'arret du pod (`SIGTERM`, `terminationGracePeriodSeconds: 60`) |
| conteneur `dionysos` | `CLAUDE_CONFIG_DIR`, `PATH`, `npm_config_*`, `DISABLE_AUTOUPDATER` (version figee par l'initContainer), `CLAUDE_CODE_OAUTH_TOKEN` |

**Secret `${CLAUDE_SECRET}`** (cree par l'administrateur, jamais versionne), cles `oauth-token` (jeton de `claude setup-token`), `forgejo-username`, `forgejo-token` (jeton limite a l'ecriture de depots : celui de `${FORGEJO_SECRET_PREFIX}-dionysos` reste en lecture seule). Toutes les references sont `optional` : sans Secret, le pod demarre, seule la synchronisation echoue.

**Ce qui est versionne** : liste blanche dans le `.gitignore` du depot (`.claude.json`, `settings.json`, `history.jsonl`, `projects/`, `agents/`, `commands/`, `skills/`, listes de plugins). **Jamais** `.credentials.json` : l'authentification passe par le Secret. Les transcripts peuvent contenir des sorties d'outils sensibles : le depot doit rester prive.

**Sessions par projet** : le conteneur lance `ws up` au demarrage (un repertoire, une session, une memoire et un onglet zellij par projet) ; le sidecar releve le travail non pousse. Voir `assistant/README.md`. Les pushes de l'assistant passent par un jeton d'ecriture monte en fichier (`${PUSH_SECRET}`, `/var/run/secrets/forgejo-push/`), jamais en variable d'environnement.

Dans les scripts du manifeste, les variables du shell (`$CH`, `$CFG`…) cotoient les variables du gabarit : rendre le fichier avec `envsubst` et la **liste explicite** des variables du tableau ci-dessous, jamais `envsubst` seul.

Les identifiants Forgejo des agents (`FORGEJO_USER`, `FORGEJO_TOKEN`) viennent d'un Secret et ne sont **pas** des variables du gabarit : l'initContainer les passe à git par un credential helper, jamais dans l'URL du remote, où ils resteraient en clair dans `.git/config` (`git remote -v`). `git remote set-url` nettoie un volume déjà initialisé avec l'ancienne URL.

## Reference des variables

Substituez les variables suivantes (via envsubst ou Helm) avant d'appliquer :

| Variable | Description | Defaut |
|---|---|---|
| `${AGENT_NAMESPACE}` | Namespace du systeme d'agents | `hermes-system` |
| `${INTERNAL_REGISTRY}` | URL du registre d'images interne | `image-registry.openshift-image-registry.svc:5000` |
| `${AGENT_IMAGE_NAME}` | Nom de l'image stream de l'agent | `hermes-agent-oc` |
| `${AGENT_IMAGE_DIGEST}` | Empreinte de l'image de l'agent (recette du répartiteur) | `sha256:…` |
| `${SERVICE_ACCOUNT}` | Service account principal de l'agent | `hermes-sa` |
| `${AGENT_CONFIG_MAP}` | Nom du ConfigMap | `hermes-behavior-config` |
| `${AGENT_SECRET}` | Nom du secret de l'agent | `hermes-agent-secret` |
| `${FORGEJO_SERVICE}` | URL interne du service Git | `forgejo-svc.git-ns.svc.cluster.local:3000` |
| `${LITELLM_SERVICE}` | URL du proxy LiteLLM | `http://litellm-svc.core-ns.svc.cluster.local:4000/v1` |
| `${ORG_NAME}` | Organisation Git | `my-org` |
| `${BRAIN_REPO}` | Depot de configuration des agents | `agent-brain` |
| `${SANDBOX_NAMESPACE}` | Namespace sandbox d'Hephaistos | `sandbox` |
| `${APPS_NAMESPACE}` | Namespace apps d'Ouranos | `apps` |
| `${GIT_NAMESPACE}` | Namespace du service Git | `git` |
| `${MODEL_THINK}` | Modele de raisonnement pour Sophia | `sophia-think` |
| `${MODEL_ROUTINE}` | Modele leger pour les sous-agents | `sophia-routine` |
| `${API_SERVER_KEY}` | Cle API interne pour la communication entre agents | (requis) |
| `${TELEGRAM_HITL_CHAT_ID}` | ID du chat Telegram pour les approbations HITL | (requis) |
| `${CLAUDE_REPO}` | Depot Git prive de la configuration et de l'historique de l'assistant de code | `assistant-history` |
| `${CLAUDE_SECRET}` | Secret de l'assistant (jeton OAuth, identifiants Forgejo en ecriture) | (requis pour la synchronisation) |
| `${CLAUDE_CODE_VERSION}` | Version de l'assistant installee par `init-claude` | (a fixer) |
| `${CLAUDE_SYNC_INTERVAL}` | Intervalle de synchronisation de l'historique, en secondes | `900` |
| `${PUSH_SECRET}` | Secret du jeton Forgejo en ecriture utilise par l'assistant (cles `username`, `password`) | (optionnel) |
