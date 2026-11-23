# Composants : description technique

Pour chaque composant des gabarits de [`okd/`](okd/) : son stockage, ses ressources, son image et la façon dont elle est fixée, son exposition, et la raison de ces choix. Les valeurs sont lues dans les manifestes du dépôt (15/11/2026) ; la raison vient du README de chaque dossier, qui fait foi en cas d'écart. Une valeur que le manifeste ne fixe pas est notée « non fixé ».

Lecture des colonnes :

- **Ressources** : `demandé → au plus` (requests → limits) du conteneur principal ; les conteneurs voisins sont cités quand ils pèsent.
- **Image** : *empreinte* = figée par `@sha256` (un redémarrage ne tire jamais une autre version) ; *version* = étiquette de version ; *construite* = image construite dans le cluster (`BuildConfig`), puis tirée du registre interne.
- **Exposition** : Service (port), Route (terminaison TLS) ; le filtrage réseau du namespace est résumé sous chaque tableau.

## Règles communes

| Règle | Mise en œuvre | Raison |
|---|---|---|
| Classe de priorité nommée par chaque charge | `sophia-socle` à `sophia-dev`, aucune classe par défaut, aucune préemption sauf l'inférence ([`okd/cluster/`](okd/cluster/README.md)) | un pod sans classe passe après toutes les charges ; une préemption tue un pod en plein travail |
| Limites sur tous les conteneurs, quota par namespace | `ResourceQuota` sur les limits et `LimitRange` de valeurs par défaut | les limits déclarées dépassaient 160 % du nœud ; un conteneur sans limite reçoit la valeur par défaut, souvent trop basse |
| Volume local désigné | PV `local:` et PVC désignés l'un l'autre (`claimRef` + `volumeName`), `Retain` ; volume logique XFS dédié pour toute donnée qui grossit ([`stockage-persistant.md`](stockage-persistant.md)) | aucune autre PVC ne prend le volume ; les données survivent à la suppression des objets ; agrandissement à chaud |
| Une réplique, `Recreate` pour tout volume `ReadWriteOnce` | jamais deux instances sur le même répertoire | un seul nœud, pas de stockage partagé |
| Entrée refusée par défaut | une NetworkPolicy par service appelé ; sorties fermées là où le composant n'a besoin de rien | un pod compromis ne joint que ce que l'architecture prévoit |
| Exposition par le VPN seulement | Routes sous le domaine joker du routeur, noms résolus vers l'adresse du VPN ([`okd/ingress/`](okd/ingress/README.md), [`okd/host/wireguard/`](okd/host/wireguard/README.md)) | un seul chemin d'accès, le réseau local hors de portée du VPN |

## Orchestration — `${NS_CORE}` ([`okd/core/`](okd/core/README.md))

Quota du namespace : 12 CPU, 16 Gi, 15 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Routeur de modèles ([LiteLLM](okd/core/README.md)) | aucun (`emptyDir` ; données dans PostgreSQL) | 250m, 768 Mi → 2 CPU, 2 Gi | construite sur une base figée par empreinte (version *nightly*), étiquette `latest`, `Always` | Service 4000, Route edge `${LITELLM_HOST}` | ≈ 550 Mi au repos, les photos gonflent les requêtes ; le plafond CPU borne un gel sur un comptage de tokens pathologique ; sondes et `RollingUpdate` pour changer de configuration sans couper le chat |
| [PostgreSQL 18](okd/core/postgres18/README.md) (toutes les bases) | volume logique dédié, `${PG_SIZE}` (20 Gi au départ) | 100m, 256 Mi → 2 CPU, 2 Gi | empreinte (`${PG18_DIGEST}`), `IfNotPresent` | Service 5432, aucune Route | une instance partagée, un rôle propriétaire par base, aucun superutilisateur par le réseau ; hors de `/var` du nœud, alerte à 80 et 90 % |
| [RabbitMQ](okd/core/rabbitmq/README.md) (bus d'événements) | répertoire du nœud, 5 Gi, lié nommément | 100m, 256 Mi → 1 CPU, 1 Gi | version (`4.4.0-management`) | Service 5672 et 15672, Route edge de l'administration (derrière le fournisseur d'identité) | une PVC sans PV désigné avait pris le volume d'un autre composant ; mémoire alignée sur la limite |
| [Temporal](okd/core/temporal/README.md) (workflows durables) | aucun (bases dans PostgreSQL) | 250m, 512 Mi → 1 CPU, 1,5 Gi | version (`1.32.1`) | Service 7233 (gRPC) et 7243, aucune Route | pas de base de plus à exploiter ; montée de version une mineure à la fois |
| Interface de Temporal | aucun | 20m, 64 Mi → 500m, 256 Mi, plus oauth2-proxy | version (`2.56.0`) ; oauth2-proxy en version | Service 4180 (oauth2-proxy), Route edge | l'interface ne s'ouvre qu'après connexion au fournisseur d'identité |
| [Répartiteur](okd/core/repartiteur/README.md) (délégations) | aucun | 50m, 128 Mi → 500m, 512 Mi | construite, déployée par empreinte (`${REPARTITEUR_DIGEST}`), `IfNotPresent` | Service 8443 (TLS du certificat de service), aucune Route | seul client de Temporal et seul éditeur d'événements ; décide par des règles sans modèle |

Réseau : entrée refusée par défaut, puis une règle par service ; le routeur n'admet que les namespaces de ses appelants enregistrés, le routeur d'entrée et le réseau du nœud. Sortie (EgressFirewall) : Services et pods du cluster, fournisseur de modèles distant, registres et index de paquets des builds, fournisseur d'identité en 443.

## Identité — `sophia-identity` ([`okd/identity/`](okd/identity/README.md))

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Keycloak (opérateur officiel, approbation manuelle) | aucun (base dans PostgreSQL) | 200m, 768 Mi → 2 CPU, 1,5 Gi | empreinte | Service de l'opérateur, Route edge (`auth.apps.example.org`) | royaume et clients décrits comme ressources Kubernetes, reproductibles ; pas de nouveau volume |
| [Valkey des sessions](okd/identity/sessions/README.md) d'oauth2-proxy | petit volume local, 1 Gi, AOF chaque seconde | 20m, 64 Mi → 200m, 192 Mi | empreinte, `IfNotPresent` | Service 6379, aucune Route | la session entière dans le cookie dépassait les limites d'en-tête ; un redémarrage ne déconnecte personne |

Réseau : sur son port HTTP, Keycloak n'admet que le routeur et une liste nommée de clients qui passent par son Service interne (la même liste est portée par la ressource de l'opérateur, qui crée sinon sa propre politique ouverte) ; son port de gestion, son seul namespace. Valkey : entrée depuis les pods des applications nommées, **aucune sortie**.

## Mémoire — `${NS_MEMORY}` ([`okd/memory/`](okd/memory/README.md))

Quota du namespace : 8 CPU, 16 Gi, 10 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Service d'embedding (bge-m3, CPU) | aucun dans le manifeste (modèle dans l'image) | 1 CPU, 2 Gi → 2 CPU, 4 Gi (valeurs par défaut des variables) | construite, étiquette `latest`, `Always` | non fixé dans le gabarit ; port 8080 sans authentification | le pod démarre sans Internet, la révision du modèle suit l'image ; le modèle tient en mémoire sans GPU |
| [Base vectorielle (Qdrant)](okd/memory/README.md) | volume logique dédié, 20 Gi au départ | 100m, 256 Mi → 2 CPU, 2 Gi | version et empreinte (`v1.13.4`) | Service 6333 et 6334, clé d'API, joignable par le seul service mémoire ; aucune Route | hors de `/var` du nœud ; l'optimisation demande jusqu'à deux fois la place ; télémétrie coupée |
| Graphe (Neo4j) | répertoire du nœud, 10 Gi | non publié | non publié | non publié | **à 0 réplique**, jamais démarré |
| [Service mémoire](okd/memory/memoire/README.md) | registre dans PostgreSQL, documents dans le stockage objet | 50m, 192 Mi → 1 CPU, 512 Mi ; extraction 50m, 128 Mi → 1 CPU, 1 536 Mi | construite, déployée par empreinte (`${MEMOIRE_IMAGE_DIGEST}`) ; une image pour le service et l'extraction | Service 8080, joignable par le seul chat ; extraction 8081, joignable par le seul service ; aucune Route | l'extraction des documents tourne à part, sans Secret, sans jeton, sans sortie |

Réseau : refus par défaut en entrée et en sortie, puis une règle par flux ; EgressFirewall limité aux réseaux internes du cluster. Le service d'embedding ne doit être joignable que depuis le routeur de modèles.

## Inférence — `sophia-inference` ([`okd/inference/`](okd/inference/README.md))

Quota du namespace : 40 CPU, 64 Gi, 6 pods. Les trois serveurs lisent le même volume de modèles (volume logique dédié de 200 Gi, monté en lecture seule).

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Serveur du modèle de langage (`llama-server`, GPU) | volume des modèles ; bibliothèque du pilote montée depuis l'hôte | 20 CPU exclusifs, 40 Gi (`Guaranteed`, demandes égales aux limites) | construite, version (`v0.7.0-cu124`) | Service 8080, aucune Route | modèle à experts dont une partie est calculée par le CPU (kubelet en politique CPU `static`) ; CUDA compatible avec le pilote du nœud ; conteneur privilégié, sans ressource `nvidia.com/gpu` (le crochet de l'opérateur échoue sur ce nœud) ; seule classe qui préempte |
| Voix (reconnaissance et synthèse, CPU) | volume des modèles | 1 CPU, 2 Gi → 4 CPU, 4 Gi | construite, étiquette `latest` | Service 8000, aucune Route | le GPU reste au texte ; classe `sophia-voix` au-dessus des agents |
| Génération d'images et classifieur (CPU) | volume des modèles | 1 CPU, 6 Gi → 8 CPU, 12 Gi ; classifieur 100m, 512 Mi → 2 CPU, 1 Gi | construites, étiquette `latest` | Service 1234 et 8001, aucune Route | plafonnée à 8 CPU pour ne pas concurrencer la voix ; contrôle déterministe de chaque image produite |
| Exporteur de métriques du nœud ([`okd/monitoring/`](okd/monitoring/README.md)) | dossiers de l'hôte en lecture | 10m, 32 Mi → 100m, 64 Mi | empreinte, `IfNotPresent` | Service 9400, aucune Route | occupation de `/var` et des volumes dédiés, état du GPU |

Réseau : **aucune sortie** ; les modèles sont déposés depuis le nœud, à des révisions et empreintes figées.

## Supervision ([`okd/monitoring/`](okd/monitoring/README.md))

La surveillance des charges utilisateur d'OKD, pas une pile à part : une seule pile, déjà maintenue par la plateforme. Prometheus 1 à 3 Gi, rétention de 15 jours, coût mesuré d'environ 0,2 CPU et 1 à 2 Gi. Des Services de métriques à part (`*-metrics`), pour ne rien changer aux Services existants ; une NetworkPolicy par namespace n'ouvre que les ports de métriques au seul Prometheus des charges utilisateur. L'exporteur du nœud est décrit avec l'inférence, ci-dessus.

## Outils locaux — `sophia-skills` ([`okd/skills/`](okd/skills/README.md))

Quota du namespace : 8 CPU, 6 Gi, 8 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Géographie (`sophia-geo`) | dossier `skills` du volume des modèles, 20 Gi, lecture seule | 20m, 320 Mi → 1 CPU, 768 Mi | construite, étiquette `latest` | Service 8000 (MCP), aucune Route | calculer positions, distances et cartes au lieu de laisser le modèle estimer ; données préparées depuis le nœud |
| Images (`sophia-image`) | aucun | 20m, 96 Mi → 1 CPU, 384 Mi | construite, étiquette `latest` | Service 8000 (MCP), aucune Route | règles de protection appliquées avant la génération |

Réseau : tout refusé ; entrée de l'interface sur 8000, d'un module vers l'outil d'images seul ; sortie DNS et outil d'images → générateur. Aucune sortie vers Internet.

## Sas web — `sophia-dmz` ([`okd/dmz/`](okd/dmz/README.md))

Quota du namespace : 8 CPU, 12 Gi, 12 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Métamoteur (SearXNG) | aucun (`emptyDir` de cache) | 50m, 128 Mi → 1 CPU, 512 Mi | version | Service 8080, aucune Route | recherche auto-hébergée, sortie JSON, instance privée |
| Service web (`sophia-web` : recherche, pages, météo) | aucun (cache de la météo en mémoire seulement) | 20m, 320 Mi → 1 CPU, 768 Mi | construite (namespace des applications), étiquette `latest` | Service 8000 (MCP et REST), aucune Route | lire le web depuis une zone qui ne peut joindre aucune adresse interne |

Réseau : tout refusé par défaut ; sortie Internet 80/443 hors plages privées et DNS ; entrée du service web depuis l'interface, les agents et le module Cuisine ; métamoteur joignable par le service web seul.

## Stockage objet — `sophia-storage` ([`okd/storage/`](okd/storage/README.md))

Quota du namespace : 3 CPU, 3 Gi, 4 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| SeaweedFS (`weed mini`, passerelle S3) | volume logique dédié, `${S3_SIZE}` (200 Gi dans l'installation de référence) | 100m, 256 Mi → 2 CPU, 2 Gi | version et empreinte, `IfNotPresent` | Service 9000 (TLS) vers le port 8443, Route reencrypt `${S3_HOST}` | maintenu, un seul processus sur un nœud ; seule la passerelle TLS est ouverte |
| Job d'initialisation (seau, versioning, CORS, politique) | aucun | 20m, 64 Mi → 500m, 256 Mi | version et empreinte | aucune | réglage rejouable |

Réseau : refus par défaut en entrée et en sortie ; entrée 8443 depuis le routeur, le namespace de l'espace de travail (bureautique) et le Job ; sortie DNS seulement.

## Interface de discussion — namespace dédié ([`okd/apps/chat-interface/`](okd/apps/chat-interface/README.md))

Quota du namespace : 4 CPU, 3 Gi, 6 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| oauth2-proxy | aucun (sessions dans le Valkey des sessions) | 10m, 32 Mi → 200m, 128 Mi | version (`v7.15.5`) | Service 8080 vers son port 4180, Route edge | connexion obligatoire, aucune clé dans le navigateur |
| nginx et front | aucun | 20m, 64 Mi → 500m, 256 Mi | construite, étiquette `latest` | port 8080, joignable depuis le pod seulement | front statique, liste blanche des routes |
| API des discussions | aucun (données dans PostgreSQL) | 20m, 96 Mi → 500m, 256 Mi | même image construite | interne au pod | contexte injecté, outils MCP, relais de l'identité |

Réseau : entrée refusée par défaut, puis le routeur d'entrée sur 4180 (oauth2-proxy) ; sorties nommées : routeur de modèles, identité, Valkey des sessions, base, forge, sas web, outils MCP, école, modules ; une politique à part ouvre la route de résumé de chaque application du dashboard. Namespace à part : l'agent de déploiement, administrateur du namespace des applications, n'y lit pas les Secrets.

## Agents — `${NS_AGENTS}` ([`okd/hermes-system/`](okd/hermes-system/README.md))

Quota du namespace : 28 CPU, 48 Gi, 15 pods.

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Assistant de code (pod de lecture du cluster) | `emptyDir`, configuration repoussée vers un dépôt dédié | 1 CPU, 12 Gi → 16 CPU, 32 Gi | construite, déployée par empreinte (`${AGENT_IMAGE_DIGEST}`) | aucune Route | classe `sophia-socle` : comprendre l'état du cluster même en panne ; demande mémoire au-dessus du pic mesuré |
| Sophia (agent principal) | `emptyDir` | 500m, 1 Gi → 2 CPU, 4 Gi (valeurs par défaut des variables) | empreinte | aucune | compte sans aucun droit : Sophia ne modifie jamais l'infrastructure |
| Agents de maintenance et de déploiement | `emptyDir` | 50m, 256 Mi → 1 CPU, 1 Gi | empreinte | Service `${AGENT_API_PORT}` (API coupée hors de l'exécutant) | délégation par le seul répartiteur |
| Exécutant (Hermes récent) | `emptyDir` | 100m, 512 Mi → 2 CPU, 2 Gi | construite, empreinte (`${EXECUTANT_IMAGE_DIGEST}`), `IfNotPresent` | Service `${AGENT_API_PORT}`, entrée réservée au répartiteur | clé propre, connue de lui et du répartiteur seuls |

Réseau : entrée des exécutants réservée au répartiteur ; outils web sans adresses internes.

## Développement — `${SANDBOX_NAMESPACE}` ([`okd/pod-bases/dev-bastion/`](okd/pod-bases/dev-bastion/README.md))

| Composant | Stockage | Ressources | Image | Exposition | Raison |
|---|---|---|---|---|---|
| Passerelle SSH de développement | aucun (clé publique par Secret) | non fixé | construite, étiquette `latest` | Service 2222 en ClusterIP seule ; Service sur l'adresse du VPN, port `${DEV_GATEWAY_VPN_PORT}` | sans NodePort, qui serait servi sur le réseau local ; SCC propre (copie d'`anyuid` plus `SYS_CHROOT`), aucun pod privilégié dans le namespace |

Réseau : la passerelle ne joint que le DNS et les pods de développement.

## Composants décrits sans manifestes publics

Ils sont documentés par une recette (composants, prérequis, réseau, variables, procédure), sans gabarit complet :

| Composant | Recette |
|---|---|
| Bureautique (Fichiers, Collabora), chat permanent, visio, messagerie XMPP | [`okd/office/`](okd/office/README.md) |
| Forge Git | seul le filtre de sortie du namespace est publié ([`okd/git/network/egress.yaml`](okd/git/network/egress.yaml)) ; dans l'installation de référence, Forgejo a une sonde de disponibilité sur `/api/healthz` (port HTTP), un quota et des valeurs par défaut ([quotas](okd/cluster/README.md#quotas-de-linstallation-de-référence)) |

Le socle de juin 2026 (`docker/`, `okd/workspaces/notebook/`, `okd/pod-bases/runner/`) est **historique, non maintenu** : il n'est pas décrit ici.
