# Répartiteur des délégations (`sophia-core`)

Le répartiteur est le seul chemin par lequel une demande atteint un agent. Il **décide sans modèle**, par des règles versionnées, et il exécute chaque demande acceptée dans un workflow durable. Concepts : [Panthéon Agentique](../../../../docs/concepts/08-pantheon-agentique.md), [Automation Déterministe](../../../../docs/concepts/09-automation-deterministe.md).

```
demandeur ──POST /v1/demandes──▶ RÉPARTITEUR (sophia-core, sans modèle)
 (une demande, jamais un ordre)   │ identité prouvée (TokenReview), règles, quotas
                                  │ seul client et seul worker Temporal
                                  ▼
                       workflow Delegation (id = task_id)
                         filtres de la destination, validations humaines
                                  │ HTTP, clé propre à chaque exécutant
                                  ▼
                       EXÉCUTANT : api_server de l'agent cible
                                  │
                       événements ──▶ RabbitMQ sophia.events (répartiteur seul éditeur)
```

## Conception

| Principe | Mise en œuvre | Pourquoi |
|---|---|---|
| **Une demande n'est pas un ordre** | une demande porte un type (`lecture`, `mission`, `consultation`), une cible, un objectif en texte et, pour une suite, le `task_id` parent ; **ni droit, ni commande, ni validation** | ce qu'un exécutant peut faire vient de ses propres droits, jamais de la consigne qu'il reçoit |
| **Identité prouvée, pas déclarée** | le demandeur présente le jeton **projeté** de son compte de service (audience `repartiteur`, courte durée) ; le répartiteur le vérifie par `TokenReview` et en déduit l'agent | un compte de service par agent ; un compte partagé par plusieurs pods ne prouve rien |
| **Règles sans modèle** | table versionnée (`02-regles.yaml`), lue au démarrage : qui demande quoi à qui, validation, durée maximale, quota par heure, filtres de retour ; **tout le reste est refusé et journalisé** | un modèle ne peut ni lire ni changer les règles |
| **Seul client de Temporal** | un workflow par demande (id = `task_id`) ; les agents n'ont aucun accès à Temporal | l'autorisation de Temporal ne connaît que des couples (namespace, rôle) : retirer le droit est la seule protection |
| **Seul éditeur des événements** | chaque étape publie sur `sophia.events` (clés `<demandeur>.delegate.<événement>`), `user_id` toujours posé ; les agents n'écrivent plus sur le bus | un consommateur refuse tout événement d'un autre émetteur |
| **Exécution en une seule tentative** | lancement avec `Idempotency-Key = task_id`, suivi du flux avec reprise, arrêt au délai maximal ; jamais de relance du travail lui-même | le travail d'un agent n'est pas idempotent : une relance est une nouvelle demande |
| **Une mission à la fois par exécutant** *(prêt : écrit et testé, en service au prochain build)* | une mission occupe sa cible de l'acceptation à la fin de son workflow, approbation du plan comprise ; une seconde reçoit `409 {"refus": "exécutant occupé"}`, sans consommer de quota ; les lectures ne comptent pas ; l'occupation est reconstituée au démarrage depuis Temporal | un agent n'a qu'une boucle de travail ; deux missions simultanées se disputeraient son espace |
| **Places du modèle local selon l'heure** *(prêt, même build)* | les missions sur l'alias de fond sont bornées à 1 le jour et à 2 de 3 h à 7 h (heure locale) ; au-delà, `409` (« modèle local occupé ») ; rien n'est interrompu au changement de plage | le verrou de l'alias ne couvre pas la génération en flux : la borne réelle des agents est ici ; la discussion garde ses places (voir [Inférence et matériel](../../../../docs/concepts/11-inference-materiel.md)) |
| **Filtres de la destination** | étapes déterministes du workflow : détection de secrets sur les réponses de supervision ; filtre anti-fuite à l'aller et tribunal au retour pour une consultation extérieure ; un filtre absent ou incertain arrête le workflow | rien ne passe par défaut ; tant que ces filtres n'existent pas, les règles refusent la consultation. Le filtre de secrets admet les noms lisibles segment par segment (noms d'objets longs, noms d'alertes, chemins d'options, empreintes git) et bloque les chaînes aléatoires : essayé sur des lectures réelles du cluster, il bloquait sinon des diagnostics ordinaires |
| **Validations D3a et D3b** | D3a : approbation de l'objectif avant le départ (signal lié à son empreinte) ; D3b : approbation de **chaque commande** ; le répartiteur ne transmet à l'exécutant que `once` ou `deny`, jamais une approbation permanente | une approbation ne vaut qu'une fois |
| **Principal vérifié** | avec `frontend.enablePrincipalPropagation`, chaque événement de l'historique Temporal porte le `sub` du jeton de l'appelant ; seuls les `sub` de la liste `approbateurs` sont retenus ; les validations passent par l'interface Temporal, réservée au groupe `admin` | le champ `identity` d'un signal est déclaré par le client : il ne prouve rien |

## Contrat HTTP

| Point | Rôle |
|---|---|
| `POST /v1/demandes` | `{type, cible, objectif[, parent]}` avec `Authorization: Bearer <jeton projeté>` ; `202 {task_id, etat}` si une règle l'accepte, `403 {refus}` sinon, `401` sans jeton valide, `409 {refus}` si la cible ou le modèle local est occupé |
| `GET /v1/demandes/{task_id}` | état et résultat filtré, pour le seul demandeur |
| `GET /sante` | santé (sonde) |
| `POST /v1/alertes` | entrée des alertes d'Alertmanager (demandeur « alertes », jeton porteur) ; **écrit et testé, désactivé** tant que son jeton n'est pas posé : il ne fera d'abord que valider et journaliser ([`../../monitoring/`](../../monitoring/)) |

Le code du service n'est pas fourni : ce dossier en décrit le contrat et le déploiement. Il est écrit en Python (SDK Temporal), sans modèle ; son image part d'une base figée par digest d'index, avec des dépendances verrouillées par empreinte (`pip install --require-hashes`), sous un UID arbitraire, système de fichiers en lecture seule.

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-build.yaml` | ImageStream du répartiteur ; **image de base importée par ImageStream** (digest d'index, `referencePolicy: Local`) ; BuildConfig en **source binaire** |
| `01-rbac.yaml` | compte de service et `system:auth-delegator` (TokenReview, rien d'autre) |
| `02-regles.yaml` | règles **d'exemple inertes** : aucun demandeur, aucun exécutant, toute demande refusée |
| `03-deployment.yaml` | Deployment (une réplique, `Recreate`), **image figée par empreinte** en `IfNotPresent`, Service en TLS par le certificat de service d'OKD |
| `04-network-policy.yaml` | entrée depuis le namespace des agents seulement ; RabbitMQ accepte le répartiteur |
| [`../../hermes-system/09-executants-network.yaml`](../../hermes-system/09-executants-network.yaml) | entrée d'un exécutant ouverte au seul répartiteur |
| [`../../hermes-system/10-recette-repartiteur.yaml`](../../hermes-system/10-recette-repartiteur.yaml) | Job de recette par le vrai chemin |

Changements des composants voisins, déjà dans leurs gabarits : compte `repartiteur` et `topic_permissions` de [RabbitMQ](../rabbitmq/), agents sans écriture ; `enablePrincipalPropagation` et entrée réservée au répartiteur dans [Temporal](../temporal/) ; client `temporal-repartiteur` et Keycloak qui accepte le répartiteur ([identité](../../identity/)) ; règle de l'EgressFirewall vers l'API Kubernetes (6443) pour le TokenReview ([`../network/policies.yaml`](../network/policies.yaml)).

| Variable | Rôle | Exemple |
|---|---|---|
| `${REPARTITEUR_SRC_DIR}` | dossier du code du service dans le dépôt interne | `services/repartiteur` |
| `${REPARTITEUR_DIGEST}` | empreinte de l'image construite | `sha256:…` |
| `${AGENT_NAMESPACE}` | namespace des agents (demandeurs et exécutants) | `agents` |

| Secret | Namespace | Clés |
|---|---|---|
| `temporal-repartiteur` | `sophia-core` | `client-id`, `client-secret` (posé par `identity/temporal-keycloak.py`) |
| `rabbitmq-users` | `sophia-core` | clé `repartiteur` (mot de passe hexadécimal) |
| `repartiteur-cle-<exécutant>` | `sophia-core` **et** namespace des agents | `cle` : la même valeur des deux côtés, générée sur place, jamais affichée |
| `repartiteur-tls` | `sophia-core` | créé par OKD (annotation du Service) |

## Procédure (l'administrateur)

Depuis un clone propre et à jour du dépôt interne ; les chemins des gabarits sont relatifs à `deploy/okd/`, sauf `git archive`, lancé à la racine du dépôt. Une étape à la fois ; chaque `oc apply` est précédé d'un `oc diff`.

1. **Mot de passe RabbitMQ** du répartiteur, avant l'étape 5 (sans lui, l'initContainer de RabbitMQ refuse de démarrer) :
   ```bash
   oc -n sophia-core patch secret rabbitmq-users --type=merge -p "{\"stringData\":{\"repartiteur\":\"$(openssl rand -hex 32)\"}}"
   ```
2. **Keycloak** : `python3 identity/temporal-keycloak.py --dry-run`, puis sans `--dry-run`. Attendu : création de `temporal-repartiteur` (`sophia:write`), son Secret, et la désactivation des anciens clients `temporal-<agent>`. Supprimer ensuite les Secrets `temporal-agent-<agent>` du namespace des agents.
3. **Réseau** : `identity/02-network.yaml`, `core/network/policies.yaml`, `core/temporal/03-network-policy.yaml`. Attendu dans `oc diff` : Keycloak accepte `repartiteur` ; l'EgressFirewall gagne la règle 6443 vers le plan de contrôle, avant le refus final ; Temporal n'accepte plus le namespace des agents ni le réseau du nœud, mais le pod `repartiteur`.
4. **Temporal** : `core/temporal/02-server.yaml`. Seul le ConfigMap de configuration dynamique change ; le serveur le relit sans redémarrer.
5. **RabbitMQ** : `core/rabbitmq/00-config.yaml`, puis `rollout restart deploy/rabbitmq`. Contrôle : `rabbitmqctl list_permissions -p /sophia` (le répartiteur écrit sur `^sophia\.events$` seulement, les agents n'écrivent nulle part) et `list_topic_permissions -p /sophia` (une ligne : `repartiteur`, `sophia.events`, `^[a-z]+\.delegate\.[a-z_]+$`).
6. **Image** : appliquer `00-build.yaml`, `01-rbac.yaml`, `02-regles.yaml`, `04-network-policy.yaml`, puis construire depuis le code **commité** :
   ```bash
   git archive --format=tar.gz -o /tmp/repartiteur.tar.gz HEAD ${REPARTITEUR_SRC_DIR}
   oc -n sophia-core start-build repartiteur --from-archive=/tmp/repartiteur.tar.gz --follow --wait
   rm /tmp/repartiteur.tar.gz
   ```
   Attendu : `Uploading archive file`, build `Complete`, installation des dépendances avec vérification des empreintes. Relever l'empreinte (`oc -n sophia-core get istag repartiteur:latest -o jsonpath='{.image.metadata.name}'`) et la reporter dans `03-deployment.yaml` (`${REPARTITEUR_DIGEST}`).
7. **Déploiement** : `03-deployment.yaml`, puis `rollout status`. Le journal contient `temporal` `connecté`, `rabbitmq` `connecté`, puis `demarrage` avec `executants` vide et `agents` 0 ; ensuite, aucune erreur `PermissionDenied` ni `ACCESS_REFUSED`.
8. **Contrôle par le vrai chemin**, depuis un pod jetable du namespace des agents : `GET /sante`, `POST /v1/demandes` sans jeton, puis avec un faux jeton. Attendu : **`200 401 401`**. Le premier code prouve le Service, le TLS et la règle réseau ; les deux autres, le refus sans identité. Le second refus passe par l'API Kubernetes, ce qui vérifie aussi la règle 6443 (une erreur 500 à ce troisième appel signale l'API injoignable).
9. **Image figée** : un `oc diff` de `03-deployment.yaml` ne montre que `image` et `imagePullPolicy` ; après `apply`, l'`imageID` du pod se termine par l'empreinte reportée, et le contrôle 8 redonne `200 401 401`. Un nouveau build ne change plus rien en service.

### Premier exécutant et recette « pong »

1. **Clé** : une valeur générée sur place, posée dans `repartiteur-cle-<exécutant>` des deux namespaces, jamais affichée (`K=$(openssl rand -hex 32)`, deux `oc create secret`, `unset K`).
2. **Entrée de l'exécutant** : `hermes-system/09-executants-network.yaml`. Contrôle négatif : un autre pod du namespace des agents ne joint pas l'`api_server` (`ConnectTimeout` attendu).
3. **Exécutant** : l'agent démarre son `api_server` avec la clé (Hermes Agent récent, version figée par digest ; une configuration d'une version antérieure se migre avant le démarrage, et les valeurs que la migration change se vérifient).
4. **Règles** : déclarer le demandeur `recette`, l'exécutant et la règle `mission` recette → exécutant (300 s, 10 par heure), ajouter la variable de la clé dans le Deployment, redémarrer. Journal : `demarrage` avec l'exécutant, les règles et un agent.
5. **Recette** : `hermes-system/10-recette-repartiteur.yaml`, puis `oc wait --for=condition=complete`. Attendu dans le journal du Job : `sans règle : 403`, `mission : 202` avec un `task_id`, `résultat :` à l'état `terminée` contenant **`pong`**, puis `RECETTE RÉUSSIE`. Dans l'interface Temporal, le workflow du même `task_id` est `Completed`, avec ses activités de lancement, de suivi et de publication. Le Job se rejoue après sa suppression.

## Retour arrière

Le répartiteur seul : supprimer son Deployment, son Service et ses deux NetworkPolicies. Le reste, objet par objet : revenir à la version précédente du gabarit, puis `oc apply` (et redémarrer RabbitMQ). Les anciens clients Keycloak se réactivent dans la console ; leurs Secrets ne sont à recréer que si un agent devait de nouveau parler à Temporal, ce que la conception exclut.

## Suite

Premier demandeur réel recetté entièrement en local : l'agent Sophia demande par un outil MCP (`repartiteur`, outils `mcp_repartiteur_*`), avec le jeton projeté de son compte sans droits ; une mission « pong » vers l'exécutant aboutit sur le modèle local. **Piège** : un serveur MCP qui porte le nom d'un toolset natif de l'agent (`delegation`) est masqué par lui, et ses outils ne sont jamais donnés au modèle ; un test de connexion du serveur MCP ne passe pas par cette résolution et donne un faux positif. La recette relève donc les outils réellement donnés au modèle.

Prévu : l'interface comme demandeur (conçue : le jeton de la personne relayé et vérifié dès le départ, quotas par personne et par jour, approbations du plan et des commandes dans l'interface, la console Temporal en secours, notifications dans la discussion puis en Web Push, une file de retour en lecture seule) ; la lecture vers la supervision (avec le filtre de secrets) ; les missions de déploiement et de maintenance avec D3a et D3b et la liste des approbateurs ; le TLS mutuel entre le répartiteur et les exécutants (l'`api_server` parle aujourd'hui HTTP dans le cluster, la clé y circule, l'entrée étant limitée au seul répartiteur) ; la consultation extérieure, après le filtre anti-fuite et le tribunal.
