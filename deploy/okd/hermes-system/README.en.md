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

## Model Agnosticism

Each agent pod is configured independently via its `AGENT_MODEL` environment variable. Sophia can use a powerful reasoning model (`${MODEL_THINK}`) while her sub-agents run a lighter, faster model (`${MODEL_ROUTINE}`). Each god deployment in `06-gods-deployments.yaml` has its own model configuration.

Because agentic behavior is enforced by infrastructure (RBAC, NetworkPolicies, output format validation) rather than the model itself, the architecture works with any model -- from small local models to large public APIs. You can even deploy an agent without any AI backend if its role is purely deterministic.

The `${AGENT_MODEL}`, `${OPENAI_API_BASE_URL}`, and `${OPENAI_API_KEY}` environment variables in the ConfigMap and Secrets control which model each agent uses.

## Variable Reference

Substitute the following variables (via envsubst or Helm) before applying:

| Variable | Description | Default |
|---|---|---|
| `${AGENT_NAMESPACE}` | Agent system namespace | `hermes-system` |
| `${INTERNAL_REGISTRY}` | Internal image registry URL | `image-registry.openshift-image-registry.svc:5000` |
| `${AGENT_IMAGE_NAME}` | Agent image stream name | `hermes-agent-oc` |
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
| `${API_SERVER_KEY}` | Internal API key for agent communication | (required) |
| `${TELEGRAM_HITL_CHAT_ID}` | Telegram chat ID for HITL approvals | (required) |
