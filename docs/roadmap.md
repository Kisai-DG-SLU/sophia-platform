# Feuille de route SophIA

Le projet SophIA évolue progressivement de l'expérimentation infrastructurelle vers une plateforme d'IA souveraine complète. Chaque étape correspond à une ou plusieurs phases du plan de travail ; une brique n'est dite « en service » que lorsqu'elle tourne dans l'installation de référence **et** que sa recette reproductible est publiée dans `deploy/`.

---

## Étape 0 : fondations d'infrastructure

En service.

- Serveur physique, cluster OKD à un nœud
- Accès par VPN uniquement ([`deploy/okd/host/wireguard/`](../deploy/okd/host/wireguard/))
- Stockage local persistant ([`deploy/stockage-persistant.md`](../deploy/stockage-persistant.md))
- Namespaces par zone de sécurité, refus par défaut en entrée dans les applications et l'orchestration ([sécurité](security.md))

---

## Étape 1 : plateforme centrale

En service.

- Routage des modèles par LiteLLM : modèles distants et locaux derrière les mêmes alias, une clé virtuelle par usage, clé maître confinée au routeur ([`deploy/okd/core/`](../deploy/okd/core/), [modèles par rôle](concepts/13-modeles-par-role.md))
- Base relationnelle commune en PostgreSQL 18, un rôle par base, sur un volume dédié extensible ([`deploy/okd/core/`](../deploy/okd/core/))
- Inférence locale : texte et vision sur GPU, voix et images sur CPU, sans sortie réseau ([`deploy/okd/inference/`](../deploy/okd/inference/))
- Identité et SSO : Keycloak pour toutes les interfaces ([`deploy/okd/identity/`](../deploy/okd/identity/))
- Interface de discussion, dans son namespace ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/)) ; devenue le **cockpit** : accueil pour parler à Sophia, applications au centre (cuisine, école et visualisation vérifiées ; messagerie, visio et bureautique en recette), « Quoi de neuf ? » nourri par les résumés des applications, « Demander à Sophia » dans chaque application, ouverture par Sophia de la bonne page ou du bon document, écriture de Sophia dans le document ouvert, lieux du profil ; voix lue pendant l'écriture
- Bureautique : fichiers et édition en ligne, retrouvés et lus depuis la discussion sous l'identité de la personne ([module Bureautique](modules/bureautique/README.md), [relais de l'identité](concepts/12-relais-identite.md))
- Chat permanent du foyer (Matrix) et visio (Jitsi Meet, par le navigateur seulement) : en service, en recette, affichés dans le cockpit ([module Communication](modules/communication/README.md)) ; courrier reporté
- Recherche web par un sas isolé, première brique du Sas Paranoïaque ([`deploy/okd/dmz/`](../deploy/okd/dmz/))
- Outils MCP locaux : géographie, images avec règles de protection, fichiers de la personne ([`deploy/okd/skills/`](../deploy/okd/skills/))
- Plateforme Git et assistant de code persistant ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/))

---

## Étape 2 : agents et mémoire

En cours. Les travaux suivent cet ordre :

| # | Travail | État |
|---|---|---|
| 0 | **Bus d'événements et workflows durables** : RabbitMQ (topologie, droits, lettres mortes), Temporal ; **répartiteur** des délégations, seul client de Temporal et seul éditeur des événements ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/)) | en service ([`deploy/okd/core/repartiteur/`](../deploy/okd/core/repartiteur/)) ; files et comptes des agents retirés du bus ; consommateurs des événements à faire |
| 1 | **Observabilité minimale** et **priorités CPU** : métriques des services, règles d'alerte, classes de priorité, quotas par namespace ([observabilité](concepts/10-observabilite.md), [inférence et matériel](concepts/11-inference-materiel.md)) | en service ([`deploy/okd/monitoring/`](../deploy/okd/monitoring/), [`deploy/okd/cluster/`](../deploy/okd/cluster/)), quota du namespace des agents et alerte de remplissage des volumes compris ; alertes filtrées envoyées à l'administrateur hors de la plateforme, copie journalisée par le répartiteur ; registre des incidents à faire |
| 2 | **Agents sur le modèle local**, avec un alias « de fond » qui laisse la priorité à la discussion, une clé du routeur par agent et des places de la carte selon l'heure | en service ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/)) ; une mission à la fois par exécutant, places du modèle local selon l'heure |
| 3 | **Mémoire (RAG)** : collection et schéma avec les tags, **API mémoire** (droits par tag, écriture long terme par le service mémoire), graphe et ingestion, stockage objet pour les fichiers | en cours : schéma, base vectorielle sur son volume dédié, alias d'embedding ([`deploy/okd/memory/`](../deploy/okd/memory/)) et stockage objet ([`deploy/okd/storage/`](../deploy/okd/storage/)) en service ; API mémoire conçue ; graphe et ingestion à reconstruire |
| 4 | **L'interface comme demandeur** du répartiteur, avec un canal de retour pour les validations et les notifications | conçu ; premiers pas en service : namespace dédié, modèles par rôle, ouverture d'une application, cockpit, jeton de la personne relayé jusqu'à un outil et jusqu'aux routes de résumé des applications ; espace de supervision du développement par les agents dans le cockpit prévu ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/)) |
| 5 | Délégations vers la **supervision** (lecture), le **déploiement** et la **maintenance** (approbations à deux niveaux) ; TLS mutuel | à faire |
| 6 | **Planificateur** des objectifs ouverts : prototype en workflow, comparé à un agent planificateur sur des objectifs réels | à faire |
| 7 | **n8n** (avec le premier outil qui en a besoin), **filtre anti-fuite**, **Tribunal Sémantique** | à faire |
| — | Mesure d'un modèle à experts en hybride carte + mémoire vive, pointe CPU comprise, avant tout changement de modèle | à planifier |

La mémoire passe avant l'interface demandeur et le planificateur : tous deux en ont besoin, comme outil typé et pour l'écriture en mémoire long terme.

Également dans cette étape :

- Modules construits sur la plateforme ([`docs/modules/`](modules/))
- Gestion des espaces de travail, modèle de projet, gestion de contexte

---

## Étape 3 : sécurité et gouvernance

Futur.

- Niveaux de confidentialité de la mémoire, permissions par rôle sur la mémoire
- Refus par défaut dans la mémoire ; règle réseau d'administration et admission des seules images du registre interne dans le développement (le privilège sur le nœud y est déjà retiré)
- Clusters de développement : un cluster virtuel éphémère par projet, recréé depuis la forge par un workflow, paquets par des relais en lecture seule dans le sas, une clé du routeur par projet limitée au modèle local
- Volumes chiffrés, isolation complète de la mémoire
- Sauvegardes planifiées et chiffrées, avec essai de restauration ; double authentification
- Veille des mises à jour et des failles des images figées
- Conformité (RGPD, AI Act, ISO 27001 visée « certifiable ») : état des lieux mesuré, plan d'action, suivi (conçu, [module Visualisation](modules/visualisation/README.md))
- Journalisation d'audit avancée, historisation brute des échanges, workflows de vérification des connaissances
- Workflow « incident » : de l'alarme au plan approuvé ([observabilité](concepts/10-observabilite.md))

---

## Étape 4 : ouverture et supervision

Futur.

- Ouverture à d'autres utilisateurs
- Tableau de bord du système : premier pas en service, l'état mesuré de chaque composant et le contrôle des miroirs ([module Visualisation](modules/visualisation/README.md)) ; interface de connaissance
- Arbitre : un modèle extérieur consulté après le filtre anti-fuite

---

## Étape 5 : industrialisation

Long terme.

- Paquets de déploiement reproductibles
- Architecture de référence pour les organisations
- Déploiements multi-locataires
