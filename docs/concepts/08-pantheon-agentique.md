# Le Panthéon Agentique : spécialisation et confinement

Le **Panthéon Agentique** est l'ensemble des agents spécialisés qui opèrent au sein de l'architecture SophIA. Chaque agent possède un rôle, des droits et un périmètre d'action strictement définis.

L'objectif est de spécialiser les comportements plutôt que de confier l'ensemble des tâches à un agent généraliste, plus difficile à contrôler et à auditer.

---

## Principe de conception

Dans une architecture multi-agents, le risque principal est la dilution des responsabilités. Un agent capable de tout faire est un agent capable de faire n'importe quoi.

Le Panthéon Agentique répond à ce problème par trois règles :

1. **Un agent, un domaine.** Chaque agent est spécialisé dans un type de tâche et ne peut pas en exercer d'autre.
2. **Droits minimaux.** Chaque agent dispose des permissions strictement nécessaires à ses tâches, et de rien d'autre. La garantie vient des droits de l'exécutant, jamais de la consigne qu'il reçoit.
3. **Aucun agent ne parle à un autre.** Toute demande passe par un composant déterministe, le **répartiteur**, qui décide sans modèle.

**Indépendant du modèle.** Chaque agent étant un pod, chacun peut utiliser un modèle différent, ou aucun : le comportement agentique (spécialisation, confinement, format de sortie) est imposé par l'infrastructure, pas supposé du modèle.

**Autonomie là où elle est le métier.** Un moteur d'agent autonome (Hermes Agent, en version figée) ne sert que là où une boucle libre avec des outils est le travail lui-même. Ailleurs, la réflexion est un appel au modèle à l'intérieur d'un workflow écrit en code (voir [Automation Déterministe](09-automation-deterministe.md)).

---

## Deux couches

| Couche | Qui | Rôle |
|---|---|---|
| **Haut** | l'interface de discussion, et à travers elle les utilisateurs | identité, gardes, réponses courtes, **validations humaines** ; elle devient **demandeur** du répartiteur pour ce qu'elle ne sait pas faire seule |
| **Bas** | les agents du panthéon | **exécutants**, joints par le seul répartiteur |

La mémoire (RAG) et le modèle de langage sont des **services** appelés par les deux couches, chacune avec ses propres droits : ils n'appartiennent à aucun agent.

---

## Les agents

L'architecture définit quatre rôles fondamentaux, plus un planificateur. La liste peut être étendue.

| Agent | Domaine | Droits | Moteur | État |
|---|---|---|---|---|
| **Hephaistos** | développement | pleins pouvoirs dans son environnement de développement, un cluster enfant par projet ; tout ce qu'il produit est versionné dans la forge Git | agent autonome | en recette, premier exécutant derrière le répartiteur |
| **Ouranos** | déploiement d'applications | limité au namespace des applications | agent, liste fermée d'outils, chaque commande approuvée | prévu |
| **Athena** | maintenance de la plateforme | administratrice du cluster, **chaque commande approuvée** par un humain après approbation du plan | agent, liste fermée d'outils (le terminal sous approbation) | prévu |
| **Dionysos** | supervision | lecture seule de tout le cluster et de la métrologie ; peut alerter, jamais agir | fonctions de lecture déterministes exposées au répartiteur ; l'interprétation revient au modèle, dans un workflow | prévu |
| **Planificateur** | objectifs ouverts : découper, puis répartir entre agents | aucun droit propre : il ne fait que des demandes au répartiteur | workflow en code, une décision du modèle à la fois | prévu, prototype à comparer à un agent planificateur |

Athena et Dionysos ne demandent jamais rien. Seul le planificateur, ou l'interface, confie une mission.

---

## Le répartiteur

Le répartiteur est un service sans modèle, dans `sophia-core`. Il est le **seul client du moteur de workflows durables** (Temporal) et le **seul éditeur des événements** (RabbitMQ).

1. **Demande.** Un demandeur envoie un type (`lecture`, `mission`, `consultation`), une cible et un objectif en texte. Une demande ne contient ni droit, ni commande, ni validation.
2. **Identité.** Elle se prouve, elle ne se déclare pas : le pod présente un jeton de compte de service projeté, de courte durée, vérifié auprès de l'API Kubernetes. D'où **un compte de service par agent**.
3. **Décision.** Une table de règles versionnée, lue au démarrage, dit qui peut demander quoi à qui, avec quelles validations et quels quotas. Tout le reste est refusé et journalisé. Un modèle ne peut pas changer ces règles.
4. **Exécution.** Un workflow durable par demande (son identifiant est celui de la tâche) appelle l'exécutant une seule fois, suit son avancement, l'arrête au délai maximal. On ne relance jamais le travail d'un agent : une relance est une nouvelle demande.
5. **Filtres de la destination.** Étapes déterministes du workflow, choisies selon la destination : détection de secrets sur les réponses de supervision, filtre anti-fuite avant toute sortie vers un modèle extérieur, tribunal sémantique au retour. Un filtre absent ou incertain arrête le workflow : rien ne passe par défaut.
6. **Événements.** Chaque étape publie un événement daté sur le bus, signé par le compte du répartiteur ; les consommateurs refusent tout autre émetteur.

**Validations humaines.** Deux niveaux : l'approbation du plan avant le départ, puis l'approbation de chaque commande. Elles passent par un seul chemin, l'interface du moteur de workflows, réservée au groupe d'administration : l'auteur authentifié de chaque signal est inscrit dans l'historique, et seul un approbateur de la liste est accepté. Un signal ne porte qu'une décision et une empreinte, jamais une commande. Une approbation n'est valable qu'une fois : rien ne s'inscrit dans une liste permanente.

État : **en service** pour les règles, le workflow, les événements et la mission vers le développement (en recette). **Prévus** : l'interface comme demandeur, la lecture vers la supervision, les missions de déploiement et de maintenance, la consultation d'un modèle extérieur (après le filtre anti-fuite et le tribunal), le TLS mutuel.

---

## Confinement et isolation

- **Un namespace commun aux agents.** L'isolation ne vient pas du namespace, mais d'un compte de service et d'un UID propres à chaque pod, de NetworkPolicies qui n'ouvrent l'entrée des agents qu'au répartiteur, et des droits de chaque compte.
- **Aucun accès des agents au moteur de workflows ni en écriture sur le bus.** Un exécutant n'a aucun moyen de joindre un autre agent : ni clé d'un autre, ni moteur de workflows, ni bus.
- **Une clé propre à chaque exécutant**, connue de lui et du répartiteur seulement.
- **Liste fermée d'outils** par agent, vérifiée en recette de non-régression : les outils réellement donnés au modèle sont relevés à chaque mise à jour du moteur d'agent, dont les valeurs par défaut peuvent changer.

---

## Position dans l'architecture

Le Panthéon Agentique s'appuie sur :

- le répartiteur (`sophia-core`) pour toute demande entre couches ou entre agents ;
- les environnements de développement (`sophia-sandbox`) pour l'exécution isolée ;
- les outils MCP (`sophia-skills`) pour les capacités locales ;
- la validation humaine, imposée par le code, sur le déploiement et l'infrastructure.

---

## Objectif

Structurer l'intelligence du système en domaines spécialisés, chacun isolé, auditable et contrôlé de manière indépendante. La surface d'attaque se réduit à un seul composant à protéger fortement, le répartiteur ; un agent peut être ajouté, remplacé ou retiré sans impact sur le reste.
