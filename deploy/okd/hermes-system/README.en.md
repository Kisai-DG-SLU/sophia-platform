# Sophia Agent Pantheon Deployment

This directory contains the OpenShift/Kubernetes manifests for deploying the **SophIA Agent Pantheon** — a multi-agent architecture based on zero-trust and strict RBAC segmentation.

## Deployment Order

The manifests must be applied sequentially to satisfy dependencies:

1. `01-agent-build.yaml` — Namespace, ServiceAccount, ImageStream, BuildConfig
2. `02-observer-dionysos.yaml` — (Optional) Dionysos observer pod for cluster diagnosis
3. `03-agent-config.yaml` — ConfigMap with RAG endpoints and LLM configuration
4. `04-agent-deployment-sophia.yaml` — Main Sophia agent deployment
5. `05-gods-rbac.yaml` — ServiceAccounts and RBAC for specialized agents
6. `06-gods-deployments.yaml` — Athena, Hephaistos, Ouranos deployments
7. `07-network-policies.yaml` — Network policies for zero-trust isolation
8. `08-services.yaml` — Internal headless services for agent routing
9. `09-executants-network.yaml` — an executor's `api_server` ingress open to the [dispatcher](../core/repartiteur/) only
10. `10-recette-repartiteur.yaml` — acceptance Job: a "pong" mission requested from the dispatcher through the real path
11. `11-executant-build.yaml` — executor image (recent Hermes Agent version, pinned by digest)
12. `12-sophia-sa.yaml` — Sophia's service account, without any right on the cluster (apply before `04`)

## Pantheon security

Agents are **executors**, reached by the [dispatcher](../core/repartiteur/) only, which decides by rules without a model ([Agent Pantheon](../../../docs/concepts/08-pantheon-agentique.en.md)).

| Point | Implementation | Why |
|---|---|---|
| No shared key, no open `api_server` | `api_server` disabled on every agent (`API_SERVER_ENABLED=false`), except on an **executor**: its own key (Secret `repartiteur-cle-<agent>`, known to it and to the dispatcher only), ingress reserved for the dispatcher (`09-executants-network.yaml`) | a shared key let whoever held it start a run on any agent, including the cluster administrator, and answer approvals themselves |
| Delegation through the dispatcher | Sophia requests through an MCP tool, with her account's projected token (audience `repartiteur`); no agent reaches Temporal or writes to RabbitMQ; Hermes' native delegation (`delegate_task`) is removed from Sophia; on an executor, it stays internal and bounded | a single door to protect, rules no model can change |
| Account without rights for Sophia | `sophia-sa` (`12-sophia-sa.yaml`): no RBAC binding, `restricted-v2` SCC, no API token mounted | Sophia never modifies the infrastructure herself |
| One UID per agent | the observer (`hostPID`) runs under its own UID (`${OBSERVER_UID}`), distinct from the other agents' | with `hostPID`, a shared UID allows reading a more privileged agent's environment and token through `/proc` |
| Restricted messaging | `TELEGRAM_ALLOWED_USERS` on every agent with a bot; no more `GATEWAY_ALLOW_ALL_USERS` | without a list, the gateway would accept any messaging user, over the Internet, outside the VPN |
| Images pinned by digest | `@${AGENT_IMAGE_DIGEST}`, `@${EXECUTANT_IMAGE_DIGEST}` with `IfNotPresent`; build bases pinned too | a restart never changes image without a decision; changing image = a new digest, then `apply` |
| Human approval | maintenance: `REQUIRE_HITL=systematic`, every command waits for approval; behind the dispatcher, approval of the plan then of each command (D3a, D3b) through the Temporal UI | **known gap**: on the deployment agent, `prompt` is handled by no code, so approval is not enforced; switching to `systematic` is planned before any use |
| Executor on a recent version | `11-executant-build.yaml` (Hermes Agent pinned by digest); an initContainer migrates the shared configuration, then applies the agent's overrides (bounds of its internal delegation) | the migration changes defaults: overrides come after it |

Closed tool list: at every Hermes update, list the tools actually given to the model; a default may change from one version to the next.

## Model Agnosticism

Each agent pod is configured independently via its `AGENT_MODEL` environment variable. Sophia can use a powerful reasoning model (`${MODEL_THINK}`) while her sub-agents run a lighter, faster model (`${MODEL_ROUTINE}`). Target: the local model for all, with a "background" alias that leaves priority to chat ([Inference and Hardware](../../../docs/concepts/11-inference-materiel.en.md)). Each god deployment in `06-gods-deployments.yaml` has its own model configuration.

Because agentic behavior is enforced by infrastructure (RBAC, NetworkPolicies, output format validation) rather than the model itself, the architecture works with any model -- from small local models to large public APIs. You can even deploy an agent without any AI backend if its role is purely deterministic.

The `${AGENT_MODEL}`, `${OPENAI_API_BASE_URL}`, and `${OPENAI_API_KEY}` environment variables in the ConfigMap and Secrets control which model each agent uses.

## Persistent coding assistant (Dionysos)

Dionysos can host a coding assistant (Claude Code) for administration. Its `/opt/data` volume is an `emptyDir`: it survives a node reboot, not a pod re-creation. To keep the assistant, its configuration and its history, `02-observer-dionysos.yaml` adds:

| Item | Role |
|---|---|
| `init-claude` initContainer | restores configuration and history from a dedicated private Git repository (`${CLAUDE_REPO}`), then installs the assistant at version `${CLAUDE_CODE_VERSION}` if missing; idempotent (replayed after a node reboot without overwriting local work) |
| `claude-sync` native sidecar | pushes the history every `${CLAUDE_SYNC_INTERVAL}` seconds, at the end of every session (an assistant `SessionEnd` hook creates `/opt/data/.claude-home/.sync-request`, covering `/clear` and exit) and when the pod stops (`SIGTERM`, `terminationGracePeriodSeconds: 60`) |
| `dionysos` container | `CLAUDE_CONFIG_DIR`, `PATH`, `npm_config_*`, `DISABLE_AUTOUPDATER` (version pinned by the initContainer), `CLAUDE_CODE_OAUTH_TOKEN` |

**Secret `${CLAUDE_SECRET}`** (created by the administrator, never committed), keys `oauth-token` (token from `claude setup-token`), `forgejo-username`, `forgejo-token` (token limited to repository write: the one in `${FORGEJO_SECRET_PREFIX}-dionysos` stays read-only). Every reference is `optional`: without the Secret the pod starts, only the sync fails.

**What is committed**: allow-list in the repository's `.gitignore` (`.claude.json`, `settings.json`, `history.jsonl`, `projects/`, `agents/`, `commands/`, `skills/`, plugin lists). **Never** `.credentials.json`: authentication goes through the Secret. Transcripts may contain sensitive tool output: the repository must stay private.

**Per-project sessions**: the container runs `ws up` at start (one directory, session, memory and zellij tab per project); the sidecar reports unpushed work. See `assistant/README.en.md`. The assistant pushes with a write token mounted as a file (`${PUSH_SECRET}`, `/var/run/secrets/forgejo-push/`), never as an environment variable.

The manifest's scripts mix shell variables (`$CH`, `$CFG`…) with template variables: render the file with `envsubst` and the **explicit list** of the variables in the table below, never plain `envsubst`.

The agents' Forgejo credentials (`FORGEJO_USER`, `FORGEJO_TOKEN`) come from a Secret and are **not** template variables: the initContainer hands them to git through a credential helper, never in the remote URL, where they would stay in clear text in `.git/config` (`git remote -v`). `git remote set-url` cleans a volume already initialised with the old URL.

## Variable Reference

Substitute the following variables (via envsubst or Helm) before applying:

| Variable | Description | Default |
|---|---|---|
| `${AGENT_NAMESPACE}` | Agent system namespace | `hermes-system` |
| `${INTERNAL_REGISTRY}` | Internal image registry URL | `image-registry.openshift-image-registry.svc:5000` |
| `${AGENT_IMAGE_NAME}` | Agent image stream name | `hermes-agent-oc` |
| `${AGENT_IMAGE_DIGEST}` | Digest of the agent image (dispatcher acceptance test) | `sha256:…` |
| `${SERVICE_ACCOUNT}` | Main agent service account | `hermes-sa` |
| `${AGENT_CONFIG_MAP}` | ConfigMap name | `hermes-behavior-config` |
| `${AGENT_SECRET}` | Agent secret name | `hermes-agent-secret` |
| `${FORGEJO_SERVICE}` | Git service internal URL | `forgejo-svc.git-ns.svc.cluster.local:3000` |
| `${LITELLM_SERVICE}` | LiteLLM proxy URL | `http://litellm-svc.core-ns.svc.cluster.local:4000/v1` |
| `${ORG_NAME}` | Git organization | `my-org` |
| `${BRAIN_REPO}` | Agent configuration repository | `agent-brain` |
| `${SANDBOX_NAMESPACE}` | Hephaistos sandbox namespace | `sandbox` |
| `${APPS_NAMESPACE}` | Ouranos apps namespace | `apps` |
| `${GIT_NAMESPACE}` | Git service namespace | `git` |
| `${MODEL_THINK}` | Reasoning model for Sophia | `sophia-think` |
| `${MODEL_ROUTINE}` | Lightweight model for sub-agents | `sophia-routine` |
| `${TELEGRAM_HITL_CHAT_ID}` | Telegram chat ID for HITL approvals | (required) |
| `${TELEGRAM_ALLOWED_USERS}` | Telegram IDs allowed to talk to the agent (list) | (required if bot) |
| `${OBSERVER_UID}`, `${OBSERVER_FSGROUP}` | Observer's own UID and group | (to set, outside the other agents' range) |
| `${EXECUTANT_IMAGE_NAME}`, `${EXECUTANT_IMAGE_DIGEST}` | Executor image and its digest | `hermes-executant`, `sha256:…` |
| `${HERMES_AGENT_VERSION}`, `${HERMES_AGENT_DIGEST}` | Version and digest of the agent image base | (to set) |
| `${CLAUDE_REPO}` | Private Git repository for the coding assistant's configuration and history | `assistant-history` |
| `${CLAUDE_SECRET}` | Assistant Secret (OAuth token, Forgejo write credentials) | (required for sync) |
| `${CLAUDE_CODE_VERSION}` | Assistant version installed by `init-claude` | (to pin) |
| `${CLAUDE_SYNC_INTERVAL}` | History sync interval, in seconds | `900` |
| `${PUSH_SECRET}` | Secret holding the assistant's Forgejo write token (keys `username`, `password`) | (optional) |
