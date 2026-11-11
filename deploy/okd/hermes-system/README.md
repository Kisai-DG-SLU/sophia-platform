# Déploiement du Panthéon Agentique Sophia

Ce répertoire contient les manifests OpenShift/Kubernetes pour déployer le **Panthéon Agentique SophIA** — une architecture multi-agents basée sur le zero-trust et la segmentation RBAC stricte.

## Ordre de déploiement

Les manifests doivent être appliqués séquentiellement pour satisfaire les dépendances :

1. `01-agent-build.yaml` — Namespace, ServiceAccount, ImageStream, BuildConfig
2. `02-observer-dionysos.yaml` — (Optionnel) Pod observateur Dionysos pour le diagnostic du cluster
3. `03-agent-config.yaml` — ConfigMap avec les endpoints RAG et la configuration LLM
4. `04-agent-deployment-sophia.yaml` — Déploiement principal de l'agent Sophia
5. `05-gods-rbac.yaml` — ServiceAccounts et RBAC pour les agents spécialisés
6. `06-gods-deployments.yaml` — Déploiements d'Athena, Hephaistos, Ouranos
7. `07-network-policies.yaml` — Politiques réseau pour l'isolation zero-trust
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
| Une clé du routeur de modèles par agent | Secret `litellm-cle-<agent>` (clé `cle`), lu par l'init et le conteneur de chaque agent ; clé virtuelle limitée à l'alias de fond et à l'embedding, débit plafonné ; une variable `env` l'emporte sur l'`OPENAI_API_KEY` d'un `envFrom` | une clé commune, ou la clé maître du routeur, ouvrait tous les modèles à tous les agents, sans traçabilité par agent ; contrôle : `/key/info` lancé dans l'agent avec sa clé renvoie son propre alias (la clé maître répond 404). **En place pour les cinq agents, assistant de code compris** ; la clé maître est retirée du Secret commun des agents, puis renouvelée : elle n'est plus lue que par le routeur ([Modèles par rôle](../../../docs/concepts/13-modeles-par-role.md)) |
| Outils web sans adresses internes, catalogue de modèles coupé | configuration commune des agents : `browser.allow_private_urls` et `security.allow_private_urls` à `false`, `model_catalog.enabled` à `false` | `allow_private_urls` ouvre aux outils web les adresses internes du cluster (SSRF) ; le catalogue interroge Internet pour rien, puisque les modèles sont fixés par le routeur |
| Exécutant sur une version récente | `11-executant-build.yaml` (Hermes Agent figé par digest) ; un initContainer migre la configuration commune, puis applique les surcharges de l'agent (bornes de sa délégation interne) | la migration change des valeurs par défaut : les surcharges passent après elle |

Liste fermée d'outils : relever à chaque mise à jour de Hermes les outils réellement donnés au modèle ; une valeur par défaut peut changer d'une version à l'autre.

## Modèle local

Tous les agents tournent sur le **modèle local**, par l'alias « de fond » du routeur (`${AGENT_MODEL_ALIAS}`, par défaut `sophia-local-fond`), qui laisse la priorité à la discussion ([Inférence et matériel](../../../docs/concepts/11-inference-materiel.md)). Aucun agent n'appelle un modèle distant ; l'assistant de code (Dionysos) y est passé lui aussi, dans son créneau, avec sa propre clé et la classe du socle. Chaque pod reste configurable seul par `AGENT_MODEL` : l'architecture ne suppose aucune capacité du modèle, puisque le comportement est imposé par l'infrastructure (RBAC, NetworkPolicies, règles du répartiteur, sortie contrainte). Un agent purement déterministe peut même se passer de modèle.

Le nombre de missions simultanées n'est pas borné par l'alias, mais par le [répartiteur](../core/repartiteur/) : en flux, le sémaphore du routeur est relâché à la première réponse et ne couvre pas la génération.

| Réglage (configuration commune des agents) | Valeur | Pourquoi |
|---|---|---|
| `prefill_messages_file` | `''` (vide) | le prefill de chaque agent était un message `system`, inséré **après** le prompt système : `system, system, user`. Un fournisseur distant l'acceptait ; le gabarit de chat du modèle local le refuse (« System message must be at the beginning »), et chaque appel échouait en erreur 500 |
| `model.context_length` | `64000` | le serveur local ne publie pas sa fenêtre : l'agent se replie sur 256 000 tokens, ne compresse qu'à la moitié et prend la réserve de la discussion. 64 000 est le plancher accepté par l'agent (61 440, la fenêtre par discussion du serveur, serait refusé) ; la compression part alors à 32 000 |

Chaque réglage s'essaie d'abord sur un seul agent, redémarré seul, puis sur les autres : la configuration commune est relue à chaque démarrage, et un changement non essayé partirait avec le prochain redémarrage de tous. Contrôle : relire les valeurs effectives dans l'agent (`yq`), puis une mission « pong » par le répartiteur, sans erreur de gabarit dans le serveur d'inférence.

## Assistant de code persistant (Dionysos)

Dionysos peut héberger un assistant de code (Claude Code) pour l'administration. Son volume `/opt/data` est un `emptyDir` : il survit au redémarrage du noeud, pas à la recréation du pod. Pour que l'assistant, sa configuration et son historique survivent, `02-observer-dionysos.yaml` ajoute :

| Élément | Rôle |
|---|---|
| initContainer `init-claude` | restaure la configuration et l'historique depuis un dépôt Git privé dédié (`${CLAUDE_REPO}`), puis installe l'assistant à la version `${CLAUDE_CODE_VERSION}` si elle manque ; idempotent (rejoue après un redémarrage du noeud sans écraser le travail local) |
| sidecar natif `claude-sync` | pousse l'historique toutes les `${CLAUDE_SYNC_INTERVAL}` secondes, à chaque fin de session (un hook `SessionEnd` de l'assistant crée `/opt/data/.claude-home/.sync-request`, couvre `/clear` et la sortie) et à l'arrêt du pod (`SIGTERM`, `terminationGracePeriodSeconds: 60`) |
| conteneur `dionysos` | `CLAUDE_CONFIG_DIR`, `PATH`, `npm_config_*`, `DISABLE_AUTOUPDATER` (version figée par l'initContainer), `CLAUDE_CODE_OAUTH_TOKEN` |

**Secret `${CLAUDE_SECRET}`** (créé par l'administrateur, jamais versionné), clés `oauth-token` (jeton de `claude setup-token`), `forgejo-username`, `forgejo-token` (jeton limité à l'écriture de dépôts : celui de `${FORGEJO_SECRET_PREFIX}-dionysos` reste en lecture seule). Toutes les références sont `optional` : sans Secret, le pod démarre, seule la synchronisation échoue.

**Ce qui est versionné** : liste blanche dans le `.gitignore` du dépôt (`.claude.json`, `settings.json`, `history.jsonl`, `projects/`, `agents/`, `commands/`, `skills/`, listes de plugins). **Jamais** `.credentials.json` : l'authentification passe par le Secret. Les transcripts peuvent contenir des sorties d'outils sensibles : le dépôt doit rester privé.

**Sessions par projet** : le conteneur lance `ws up` au démarrage (un répertoire, une session, une mémoire et un onglet zellij par projet) ; le sidecar relève le travail non poussé. Voir `assistant/README.md`. Les pushes de l'assistant passent par un jeton d'écriture monté en fichier (`${PUSH_SECRET}`, `/var/run/secrets/forgejo-push/`), jamais en variable d'environnement.

Dans les scripts du manifeste, les variables du shell (`$CH`, `$CFG`…) côtoient les variables du gabarit : rendre le fichier avec `envsubst` et la **liste explicite** des variables du tableau ci-dessous, jamais `envsubst` seul.

Les identifiants Forgejo des agents (`FORGEJO_USER`, `FORGEJO_TOKEN`) viennent d'un Secret et ne sont **pas** des variables du gabarit : l'initContainer les passe à git par un credential helper, jamais dans l'URL du remote, où ils resteraient en clair dans `.git/config` (`git remote -v`). `git remote set-url` nettoie un volume déjà initialisé avec l'ancienne URL.

## Référence des variables

Substituez les variables suivantes (via envsubst ou Helm) avant d'appliquer :

| Variable | Description | Défaut |
|---|---|---|
| `${AGENT_NAMESPACE}` | Namespace du système d'agents | `hermes-system` |
| `${INTERNAL_REGISTRY}` | URL du registre d'images interne | `image-registry.openshift-image-registry.svc:5000` |
| `${AGENT_IMAGE_NAME}` | Nom de l'image stream de l'agent | `hermes-agent-oc` |
| `${AGENT_IMAGE_DIGEST}` | Empreinte de l'image de l'agent (recette du répartiteur) | `sha256:…` |
| `${SERVICE_ACCOUNT}` | Service account principal de l'agent | `hermes-sa` |
| `${AGENT_CONFIG_MAP}` | Nom du ConfigMap | `hermes-behavior-config` |
| `${AGENT_SECRET}` | Nom du secret de l'agent | `hermes-agent-secret` |
| `${FORGEJO_SERVICE}` | URL interne du service Git | `forgejo-svc.git-ns.svc.cluster.local:3000` |
| `${LITELLM_SERVICE}` | URL du proxy LiteLLM | `http://litellm-svc.core-ns.svc.cluster.local:4000/v1` |
| `${ORG_NAME}` | Organisation Git | `my-org` |
| `${BRAIN_REPO}` | Dépôt de configuration des agents | `agent-brain` |
| `${SANDBOX_NAMESPACE}` | Namespace sandbox d'Hephaistos | `sandbox` |
| `${APPS_NAMESPACE}` | Namespace apps d'Ouranos | `apps` |
| `${GIT_NAMESPACE}` | Namespace du service Git | `git` |
| `${AGENT_MODEL_ALIAS}` | Alias du routeur pour tous les agents (modèle local, de fond) | `sophia-local-fond` |
| `${AGENT_PRIORITY_CLASS}`, `${SOCLE_PRIORITY_CLASS}` | Classes de priorité des agents et de l'observateur ([`../cluster/`](../cluster/)) | `sophia-agents`, `sophia-socle` |
| `${TELEGRAM_HITL_CHAT_ID}` | ID du chat Telegram pour les approbations HITL | (requis) |
| `${TELEGRAM_ALLOWED_USERS}` | Identifiants Telegram autorisés à parler à l'agent (liste) | (requis si bot) |
| `${OBSERVER_UID}`, `${OBSERVER_FSGROUP}` | UID et groupe propres de l'observateur | (à fixer, hors de la plage des autres agents) |
| `${EXECUTANT_IMAGE_NAME}`, `${EXECUTANT_IMAGE_DIGEST}` | Image des exécutants et son empreinte | `hermes-executant`, `sha256:…` |
| `${HERMES_AGENT_VERSION}`, `${HERMES_AGENT_DIGEST}` | Version et empreinte de la base de l'image des agents | (à fixer) |
| `${CLAUDE_REPO}` | Dépôt Git privé de la configuration et de l'historique de l'assistant de code | `assistant-history` |
| `${CLAUDE_SECRET}` | Secret de l'assistant (jeton OAuth, identifiants Forgejo en écriture) | (requis pour la synchronisation) |
| `${CLAUDE_CODE_VERSION}` | Version de l'assistant installée par `init-claude` | (à fixer) |
| `${CLAUDE_SYNC_INTERVAL}` | Intervalle de synchronisation de l'historique, en secondes | `900` |
| `${PUSH_SECRET}` | Secret du jeton Forgejo en écriture utilisé par l'assistant (clés `username`, `password`) | (optionnel) |
