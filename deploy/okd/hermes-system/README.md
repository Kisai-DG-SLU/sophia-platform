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

## Agnosticisme des modeles

Chaque pod agent est configure independamment via sa variable d'environnement `AGENT_MODEL`. Sophia peut utiliser un modele de raisonnement puissant (`${MODEL_THINK}`) tandis que ses sous-agents utilisent un modele plus leger et rapide (`${MODEL_ROUTINE}`). Chaque deite dans `06-gods-deployments.yaml` possede sa propre configuration de modele.

Etant donne que le comportement agentique est enforce par l'infrastructure (RBAC, NetworkPolicies, validation du format de sortie) plutot que par le modele lui-meme, l'architecture fonctionne avec n'importe quel modele — des petits modeles locaux aux grandes API publiques. Vous pouvez meme deployer un agent sans backend IA si son role est purement deterministe.

Les variables d'environnement `${AGENT_MODEL}`, `${OPENAI_API_BASE_URL}` et `${OPENAI_API_KEY}` dans le ConfigMap et les Secrets controlent le modele utilise par chaque agent.

## Reference des variables

Substituez les variables suivantes (via envsubst ou Helm) avant d'appliquer :

| Variable | Description | Defaut |
|---|---|---|
| `${AGENT_NAMESPACE}` | Namespace du systeme d'agents | `hermes-system` |
| `${INTERNAL_REGISTRY}` | URL du registre d'images interne | `image-registry.openshift-image-registry.svc:5000` |
| `${AGENT_IMAGE_NAME}` | Nom de l'image stream de l'agent | `hermes-agent-oc` |
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
