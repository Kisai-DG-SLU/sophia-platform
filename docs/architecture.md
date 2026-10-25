# Architecture SophIA

SophIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) est une architecture ouverte et expérimentale conçue pour orchestrer des systèmes d'intelligence artificielle dans un environnement souverain et sécurisé.

La plateforme assemble des composants open source en une infrastructure cohérente qui permet aux organisations de déployer, gouverner et exploiter des systèmes d'IA tout en préservant le contrôle de leurs données et de leur infrastructure.

---

## Principes architecturaux

- **Souveraineté** sur les données, les modèles et l'infrastructure ; cible : inférence entièrement locale (voir [Inférence et matériel](concepts/11-inference-materiel.md)).
- **Indépendance du modèle** : l'architecture ne dépend d'aucun modèle. Chaque agent, étant un pod, peut utiliser un modèle différent, du plus petit modèle local au plus grand. L'intelligence du système réside dans l'architecture, pas dans le modèle.
- **Le code orchestre, le modèle réfléchit, les règles décident** : analyse par le modèle, décision par des règles, exécution par une compétence déterministe (voir [Automation Déterministe](concepts/09-automation-deterministe.md)).
- Isolation réseau stricte entre les composants critiques.
- Intégration modulaire de technologies open source.
- Déploiement reproductible de l'infrastructure.
- Auditabilité des interactions avec l'IA.

L'architecture est conçue pour être indépendante du **modèle**, du **logiciel** et du **matériel**. Chaque composant peut être remplacé par une alternative équivalente, open source, propriétaire ou développée en interne. Les choix de l'implémentation de référence sont des exemples parmi de nombreuses configurations possibles.

---

## Architecture haut niveau

SophIA repose sur une plateforme Kubernetes (OKD / OpenShift). Les services centraux sont isolés dans des namespaces dédiés, les environnements de développement et d'application dans des zones distinctes.

```
            utilisateurs (VPN, SSO)
                     |
          +----------------------+
          |  interface (apps)    |   couche haute : identité, gardes,
          |  demandeur           |   réponses courtes, validations
          +----------+-----------+
                     | demandes
          +----------v-----------+        +-------------------+
          |  sophia-core         |------->| sophia-inference  |
          |  routeur de modèles  |        | modèles locaux    |
          |  répartiteur         |        +-------------------+
          |  workflows, bus      |        +-------------------+
          +----------+-----------+------->| sophia-memory     |
                     | missions           | mémoire (RAG)     |
          +----------v-----------+        +-------------------+
          |  agents du panthéon  |        +-------------------+
          |  exécutants          |------->| sophia-skills     |
          +----------------------+        | outils MCP        |
                                          +-------------------+
          sophia-git : code, specs     sophia-dmz : web, nettoyé
```

---

## Deux couches

- **Couche haute : l'interface.** Elle porte l'identité des utilisateurs, les gardes, les réponses courtes et les validations humaines. Pour une demande simple, elle comprend la demande en sortie contrainte, et le serveur fabrique l'appel d'outil (en service). Pour ce qu'elle ne sait pas faire seule, elle devient **demandeur** du répartiteur (prévu).
- **Couche basse : les agents.** Ce sont des **exécutants**, joints par le seul répartiteur. Ils ne se parlent jamais.
- **Services partagés** : le modèle de langage et la mémoire sont appelés par les deux couches, chacune avec ses propres droits.

---

## Orchestration des agents

| Composant | Rôle | État |
|---|---|---|
| **Répartiteur** (`sophia-core`) | point d'entrée unique des demandes ; identité prouvée par jeton de compte de service ; règles déterministes (qui demande quoi à qui, validations, quotas) ; un workflow durable par demande ; filtres de la destination ; validations humaines à deux niveaux | en service |
| **Temporal** (`sophia-core`) | workflows durables ; **seul client applicatif : le répartiteur** ; l'historique de chaque workflow sert de journal | en service |
| **RabbitMQ** (`sophia-core`) | **événements** : chaque étape d'une délégation est publiée sur un exchange d'événements par le répartiteur, seul éditeur ; files en lettres mortes | en service, sans compte d'agent ; consommateurs prévus |
| **Agents autonomes** (Hermes Agent, version figée) | là où une boucle libre avec des outils est le métier : le développement, puis la maintenance et le déploiement avec une liste fermée d'outils et chaque commande approuvée | développement en recette, le reste prévu |
| **Planificateur** | objectifs ouverts : un workflow en code qui demande au modèle une décision à la fois, la fait valider par des règles et exécuter par le répartiteur | prévu, prototype à comparer à un agent planificateur |
| **Supervision** | fonctions de lecture déterministes exposées au répartiteur, dans un pod à part ; l'interprétation revient au modèle dans un workflow « incident » | prévu : conçu et testé |
| **Métrologie et alertes** | supervision des charges de la plateforme, règles d'alerte, exporteur du nœud | en service |

Détail : [Panthéon Agentique](concepts/08-pantheon-agentique.md), [Observabilité](concepts/10-observabilite.md).

---

## Namespaces centraux

### sophia-core

Couche d'orchestration centrale : routage des modèles (LiteLLM), répartiteur des délégations, workflows durables (Temporal), bus d'événements (RabbitMQ), base relationnelle.

### sophia-inference

Exécution locale des modèles : hébergement, inférence CPU et GPU, isolation sans accès réseau.

Technologies (exemple) : llama.cpp (texte et vision, GPU), stable-diffusion.cpp (images, CPU), modèles vocaux sur CPU. Alternatives : vLLM, Ollama.

### sophia-memory

Connaissance persistante : stockage vectoriel, indexation RAG, embedding. La mémoire est un **service**, appelé par l'interface comme par les agents, chacun selon ses droits.

Technologies (exemple) : Qdrant.

### sophia-git

Gouvernance des connaissances et du code : mémoire de projet, spécifications, versionnement.

Technologies (exemple) : Forgejo.

### sophia-skills

Outils locaux : serveurs MCP, injection de contexte, outils pour l'interface et les agents.

### sophia-storage

Stockage objet S3 commun : une identité et un seau par application, refus par défaut en entrée et en sortie.

Technologies (exemple) : SeaweedFS.

### sophia-dmz

Acquisition web sécurisée : extraction, nettoyage, mécanismes anti-traçage.

---

## Zones de développement et d'exécution

| Namespace | Rôle |
|---|---|
| namespace des agents | pods du panthéon, un compte de service et un UID par pod |
| sophia-sandbox | environnements de développement, clusters enfants par projet |
| sophia-test | validation CI/CD |
| sophia-apps | interfaces utilisateur et modules |
| namespaces dédiés (prévus) | l'interface de discussion et l'outil de visualisation, hors de la portée de l'agent de déploiement |
| prod-* | charges de travail des locataires |

---

## Plateforme d'infrastructure

L'implémentation de référence fonctionne sur un cluster Kubernetes mono-nœud (OKD) déployé sur un serveur physique.

- orchestration Kubernetes ;
- politiques réseau strictes ;
- stockage persistant local ;
- conception indépendante du matériel : toute infrastructure qui répond aux exigences peut être substituée.

La configuration matérielle du Proof of Concept est documentée dans la section déploiement ; le partage de la carte graphique et le budget CPU dans [Inférence et matériel](concepts/11-inference-materiel.md). Ces choix ne sont pas prescriptifs : chaque organisation adapte l'infrastructure à son contexte, à son échelle et à ses exigences de sécurité.

---

## Architecture anti-hallucination

La plateforme restreint les hallucinations par l'architecture, et non par le modèle. Ces mécanismes sont indépendants du modèle sous-jacent :

- **Confinement RBAC** : chaque agent a des permissions strictement minimales. Si un agent hallucine une commande destructrice hors de son périmètre, le cluster la rejette.
- **Décision sans modèle** : le répartiteur accepte ou refuse chaque demande selon des règles versionnées qu'aucun modèle ne peut modifier.
- **Validation humaine imposée par le code** : approbation du plan, puis de chaque commande, par un seul chemin authentifié ; un signal ne porte qu'une décision et une empreinte.
- **Sortie contrainte** : le modèle répond selon un schéma imposé ; tout écart est rejeté par les règles.
- **Isolation réseau** : les NetworkPolicies n'ouvrent l'entrée des agents qu'au répartiteur.
- **Supervision** : la lecture seule de l'ensemble du système permet d'alerter sur un comportement anormal.

Ces mécanismes fonctionnent avec n'importe quel modèle, du plus petit (quelques milliards de paramètres) au plus grand. L'architecture ne suppose aucune capacité agentique du modèle : le comportement est imposé par la structure des pods, le RBAC, les règles et l'infrastructure.

---

## Statut

L'architecture est expérimentale. L'infrastructure, le routage des modèles, l'inférence locale (agents compris), l'identité, le répartiteur et ses workflows, la métrologie et les alertes, les priorités CPU et le stockage objet sont en service ; l'état de chaque fonction est détaillé dans le [périmètre fonctionnel](functional-scope.md) et la [feuille de route](roadmap.md).
