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
11. `11-executant-build.yaml` — image des exécutants (version récente de Hermes Agent, figée par digest)
12. `12-sophia-sa.yaml` — compte de service de Sophia, sans aucun droit sur le cluster (à appliquer avant `04`)

## Sécurité du panthéon

Les agents sont des **exécutants**, joints par le seul [répartiteur](../core/repartiteur/), qui décide par des règles sans modèle ([Panthéon Agentique](../../../docs/concepts/08-pantheon-agentique.md)).

| Point | Mise en œuvre | Pourquoi |
|---|---|---|
| Pas de clé commune, pas d'`api_server` ouvert | `api_server` coupé chez tous les agents (`API_SERVER_ENABLED=false`), sauf chez un **exécutant** : clé propre (Secret `repartiteur-cle-<agent>`, connue de lui et du répartiteur seuls), entrée réservée au répartiteur (`09-executants-network.yaml`) | une clé commune permettait à qui la détenait de lancer une exécution chez n'importe quel agent, y compris l'administrateur du cluster, et de répondre lui-même aux approbations |
| Délégation par le répartiteur | Sophia demande par un outil MCP, avec le jeton projeté de son compte (audience `repartiteur`) ; aucun agent n'accède à Temporal ni n'écrit sur RabbitMQ ; la délégation native de Hermes (`delegate_task`) est retirée à Sophia ; chez un exécutant, elle reste interne et bornée | une seule porte à protéger, des règles qu'aucun modèle ne change |
| Compte sans droits pour Sophia | `sophia-sa` (`12-sophia-sa.yaml`) : aucune liaison RBAC, SCC `restricted-v2`, aucun jeton d'API monté | Sophia ne modifie jamais l'infrastructure elle-même |
| Un UID par agent | l'observateur (`hostPID`) tourne sous un UID propre (`${OBSERVER_UID}`), distinct de celui des autres agents | en `hostPID`, un même UID permet de lire par `/proc` l'environnement et le jeton d'un agent plus privilégié |
| Messagerie limitée | `TELEGRAM_ALLOWED_USERS` chez tout agent qui a un bot ; plus de `GATEWAY_ALLOW_ALL_USERS` | sans liste, la passerelle accepterait tout utilisateur de la messagerie, par Internet, hors VPN |
| Images figées par empreinte | `@${AGENT_IMAGE_DIGEST}`, `@${EXECUTANT_IMAGE_DIGEST}` en `IfNotPresent` ; base des builds figée elle aussi | un redémarrage ne change jamais d'image sans décision ; changer d'image = un nouveau digest, puis `apply` |
| Validation humaine | maintenance : `REQUIRE_HITL=systematic`, chaque commande attend une approbation ; derrière le répartiteur, approbation du plan puis de chaque commande (D3a, D3b) par l'interface Temporal | **écart connu** : chez l'agent de déploiement, `prompt` n'est traité par aucun code, la validation n'est donc pas imposée ; passage à `systematic` prévu avant tout usage |
| Exécutant sur une version récente | `11-executant-build.yaml` (Hermes Agent figé par digest) ; un initContainer migre la configuration commune, puis applique les surcharges de l'agent (bornes de sa délégation interne) | la migration change des valeurs par défaut : les surcharges passent après elle |

Liste fermée d'outils : relever à chaque mise à jour de Hermes les outils réellement donnés au modèle ; une valeur par défaut peut changer d'une version à l'autre.

## Agnosticisme des modeles

Chaque pod agent est configure independamment via sa variable d'environnement `AGENT_MODEL`. Sophia peut utiliser un modele de raisonnement puissant (`${MODEL_THINK}`) tandis que ses sous-agents utilisent un modele plus leger et rapide (`${MODEL_ROUTINE}`). Cible : le modele local pour tous, avec un alias « de fond » qui laisse la priorite a la discussion ([Inférence et matériel](../../../docs/concepts/11-inference-materiel.md)). Chaque deite dans `06-gods-deployments.yaml` possede sa propre configuration de modele.

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
| `${TELEGRAM_HITL_CHAT_ID}` | ID du chat Telegram pour les approbations HITL | (requis) |
| `${TELEGRAM_ALLOWED_USERS}` | Identifiants Telegram autorisés à parler à l'agent (liste) | (requis si bot) |
| `${OBSERVER_UID}`, `${OBSERVER_FSGROUP}` | UID et groupe propres de l'observateur | (à fixer, hors de la plage des autres agents) |
| `${EXECUTANT_IMAGE_NAME}`, `${EXECUTANT_IMAGE_DIGEST}` | Image des exécutants et son empreinte | `hermes-executant`, `sha256:…` |
| `${HERMES_AGENT_VERSION}`, `${HERMES_AGENT_DIGEST}` | Version et empreinte de la base de l'image des agents | (à fixer) |
| `${CLAUDE_REPO}` | Depot Git prive de la configuration et de l'historique de l'assistant de code | `assistant-history` |
| `${CLAUDE_SECRET}` | Secret de l'assistant (jeton OAuth, identifiants Forgejo en ecriture) | (requis pour la synchronisation) |
| `${CLAUDE_CODE_VERSION}` | Version de l'assistant installee par `init-claude` | (a fixer) |
| `${CLAUDE_SYNC_INTERVAL}` | Intervalle de synchronisation de l'historique, en secondes | `900` |
| `${PUSH_SECRET}` | Secret du jeton Forgejo en ecriture utilise par l'assistant (cles `username`, `password`) | (optionnel) |
