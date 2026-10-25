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

- Routage des modèles par LiteLLM : modèles distants et locaux derrière les mêmes alias ([`deploy/okd/core/`](../deploy/okd/core/))
- Inférence locale : texte et vision sur GPU, voix et images sur CPU, sans sortie réseau ([`deploy/okd/inference/`](../deploy/okd/inference/))
- Identité et SSO : Keycloak pour toutes les interfaces ([`deploy/okd/identity/`](../deploy/okd/identity/))
- Interface de discussion ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/))
- Recherche web par un sas isolé, première brique du Sas Paranoïaque ([`deploy/okd/dmz/`](../deploy/okd/dmz/))
- Outils MCP locaux : géographie, images avec règles de protection ([`deploy/okd/skills/`](../deploy/okd/skills/))
- Plateforme Git et assistant de code persistant ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/))

---

## Étape 2 : agents et mémoire

En cours. Les travaux suivent cet ordre :

| # | Travail | État |
|---|---|---|
| 0 | **Bus d'événements et workflows durables** : RabbitMQ (topologie, droits, lettres mortes), Temporal ; **répartiteur** des délégations, seul client de Temporal et seul éditeur des événements ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/)) | en service ([`deploy/okd/core/repartiteur/`](../deploy/okd/core/repartiteur/)) ; files et comptes des agents retirés du bus ; consommateurs des événements à faire |
| 1 | **Observabilité minimale** et **priorités CPU** : métriques des services, règles d'alerte, classes de priorité, quotas par namespace ([observabilité](concepts/10-observabilite.md), [inférence et matériel](concepts/11-inference-materiel.md)) | en service ([`deploy/okd/monitoring/`](../deploy/okd/monitoring/), [`deploy/okd/cluster/`](../deploy/okd/cluster/)) ; routage des alertes vers le répartiteur et quota du namespace des agents à faire |
| 2 | **Agents sur le modèle local**, avec un alias « de fond » qui laisse la priorité à la discussion, une clé du routeur par agent et des places de la carte selon l'heure | en service ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/)) ; plafond des missions au prochain build du répartiteur |
| 3 | **Mémoire (RAG)** : collection et schéma avec les tags, **API mémoire** (droits par tag, écriture long terme par le service mémoire), graphe et ingestion, stockage objet pour les fichiers | en cours : schéma, alias d'embedding ([`deploy/okd/memory/`](../deploy/okd/memory/)) et stockage objet ([`deploy/okd/storage/`](../deploy/okd/storage/)) en service ; API mémoire conçue ; graphe et ingestion à reconstruire |
| 4 | **L'interface comme demandeur** du répartiteur, avec un canal de retour pour les validations et les notifications ; un namespace dédié à l'interface | conçu ; premier pas en service : modèles par rôle, ouverture d'une application ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/)) |
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
- Refus par défaut dans la mémoire et le développement
- Volumes chiffrés, isolation complète de la mémoire
- Journalisation d'audit avancée, historisation brute des échanges, workflows de vérification des connaissances
- Workflow « incident » : de l'alarme au plan approuvé ([observabilité](concepts/10-observabilite.md))

---

## Étape 4 : ouverture et supervision

Futur.

- Ouverture à d'autres utilisateurs
- Tableau de bord du système, interface de connaissance
- Arbitre : un modèle extérieur consulté après le filtre anti-fuite

---

## Étape 5 : industrialisation

Long terme.

- Paquets de déploiement reproductibles
- Architecture de référence pour les organisations
- Déploiements multi-locataires
