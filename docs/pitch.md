# SophIA en bref

Ce document présente SophIA en trois longueurs : une phrase, trente secondes, trois minutes. Il dit aussi clairement ce qui fonctionne déjà et ce qui reste à construire.

---

## En une phrase

**SophIA assemble des briques open source en une plateforme d'IA agentique que l'organisation héberge, gouverne et audite elle-même. La sécurité vient de l'architecture, pas du modèle.**

---

## En trente secondes

Les organisations veulent des agents d'IA. Mais elles ne peuvent pas confier leurs données sensibles à des plateformes opaques hors de leur juridiction, ni laisser des agents autonomes agir sans garde-fous.

SophIA est une architecture de référence qui répond à ces deux contraintes. Elle repose sur un cluster que l'organisation contrôle. Les agents spécialisés n'ont que des droits minimaux et ne se parlent jamais : chaque demande passe par un répartiteur qui décide par des règles, sans modèle, et les actions critiques attendent une validation humaine. La mémoire est versionnée dans Git. Les modèles tournent en local, derrière un routeur qui accepte n'importe quel modèle.

On change de modèle sans changer d'architecture, et chaque décision reste auditable.

---

## En trois minutes

### 1. Le problème

Adopter l'IA aujourd'hui, c'est accepter trois risques :

- **Les données sortent.** La plupart des usages reposent sur des API externes, hors de tout contrôle.
- **La dépendance s'installe.** API propriétaires, écosystèmes fermés, infrastructures situées dans une autre juridiction.
- **Les agents sont imprévisibles.** Injection de prompt, exfiltration, ingestion de contenus web malveillants ou générés par IA.

À cela s'ajoute un écosystème fragmenté. Chaque équipe assemble à la main des outils qui n'ont pas été conçus pour fonctionner ensemble.

### 2. L'idée centrale

**On ne rend pas le modèle fiable : on rend l'infrastructure fiable.**

Un modèle peut halluciner. Avec SophIA, ses erreurs restent sans conséquence :

- le code orchestre, le modèle réfléchit, les règles décident : le modèle propose en sortie contrainte, des règles valident, une compétence déterministe exécute ;
- un agent qui génère une commande destructrice est arrêté par le contrôle d'accès du cluster ;
- une action de modification attend une validation humaine, imposée par le code et non par une consigne ;
- le réseau limite chaque composant à son périmètre.

Ces garde-fous fonctionnent quel que soit le modèle, du plus petit au plus grand.

### 3. La solution : quatre piliers

| Pilier | Ce que cela apporte |
|---|---|
| **Souveraineté** | Infrastructure Kubernetes maîtrisée, stockage local, mémoire de projet dans une forge Git auto-hébergée. Routeur de modèles agnostique : un modèle local ou distant est un choix de routage, pas une dépendance. |
| **Panthéon agentique** | Des agents spécialisés, un domaine chacun : développement en sandbox, déploiement, maintenance, supervision en lecture seule. Ils sont joints par un seul répartiteur, qui décide par des règles ; droits minimaux, validation humaine sur les actions critiques. |
| **Mémoire RAG 5D** | Cinq dimensions complémentaires : vectorielle, relationnelle, versionnée, structurelle, graphe. Chaque fait retrouvé peut être relié à sa source. |
| **Sécurité par conception** | Acquisition web isolée et nettoyée (Sas Paranoïaque), validation croisée avant ingestion (Tribunal Sémantique), requêtes leurres (Ghost Search), filtrage des fuites (DLP), journalisation des interactions. |

### 4. Ce qui différencie SophIA

SophIA n'est pas un produit de plus. C'est **une recette reproductible** qui assemble des composants existants (Kubernetes, LiteLLM, llama.cpp, Keycloak, Temporal, RabbitMQ, Qdrant, PostgreSQL, Forgejo, Hermes Agent) de manière cohérente.

- **Reproductible** : l'infrastructure est décrite et versionnée.
- **Auditable** : les décisions, le code et la mémoire sont tracés dans Git.
- **Indépendante du modèle** : le comportement agentique est imposé par l'infrastructure, pas supposé du modèle.

### 5. Où en est le projet

SophIA est une architecture expérimentale en construction. Nous distinguons ce qui fonctionne de ce qui est prévu.

**Opérationnel aujourd'hui**

- Cluster Kubernetes (OKD) mono-nœud sur serveur physique, accès par VPN seulement, identité unique (SSO) pour toutes les interfaces.
- Inférence locale sur le GPU du serveur (texte et vision), voix et images sur CPU, sans accès réseau ; modèle local par défaut de l'interface et des modules.
- Routeur de modèles unifié : local et distant derrière les mêmes alias.
- Interface de discussion dans son namespace, connectée au routeur et à des outils locaux (géographie, images, fichiers de la personne), sans aucune clé dans le navigateur ni dépendance externe (polices et bibliothèques embarquées) ; modèle imposé par le serveur selon le rôle, une clé du routeur par usage ; thèmes visuels au choix ; réponse lue à voix haute pendant qu'elle s'écrit.
- Cockpit : la discussion devient la coquille de toutes les interactions, avec un accueil pour parler à Sophia (avatar en hologramme qui montre la réflexion, l'outil appelé et la parole) et les applications de cuisine, d'école et de visualisation affichées au centre, chacune sous sa propre connexion ; un lieu tiré par le modèle n'est retenu que s'il a été dit.
- Bureautique (fichiers et édition en ligne) ; la discussion retrouve, ouvre et lit les documents de la personne sous son identité, le contenu ne partant qu'au modèle local.
- Base relationnelle commune en PostgreSQL 18, sur un volume dédié.
- Acquisition web isolée par le sas, première brique du Sas Paranoïaque.
- Répartiteur des délégations, workflows durables et bus d'événements ; premier agent exécutant (développement) en recette.
- Forge Git auto-hébergée, source de vérité du code et de la mémoire des projets ; environnements de développement isolés, sans privilège sur le nœud.
- Base vectorielle avec son schéma sur son volume dédié, service d'embedding, stockage objet S3 avec corbeille.
- Agents du panthéon sur le modèle local, avec priorité à la discussion sur la carte graphique ; une clé du routeur par agent, clé maître confinée au routeur.
- Observabilité minimale : métriques des services, règles d'alerte, carte graphique, garde-fou du filtre VPN ; priorités CPU sans préemption et quotas par namespace ; état mesuré de chaque composant et contrôle horaire des miroirs des dépôts ; alertes filtrées envoyées à l'administrateur hors de la plateforme.

**En service, en recette**

- Chat permanent du foyer (Matrix) et visio (Jitsi Meet, par le navigateur seulement), chacun dans son namespace, réservés aux comptes du foyer, le média de la visio joignable par le VPN seulement ; affichés dans le cockpit, comme la bureautique et le document qu'on y ouvre.
- « Quoi de neuf ? » dans le cockpit, première version calculée par le serveur.

**En cours**

- L'interface comme demandeur du répartiteur.
- Cockpit : ouverture par Sophia du bon module sans clic (prête), résumés déterministes de chaque application, documents ouverts et complétés par Sophia, lieux enregistrés dans le profil avec un géocodage local, accès par le cockpit seul.
- Clusters de développement : un cluster virtuel éphémère par projet (décidé, à construire).
- Service mémoire (conçu), pipeline d'ingestion et dimension graphe.
- Sauvegardes planifiées, veille des failles, conformité (RGPD, AI Act, ISO 27001).

**Prévu**

- Planificateur des objectifs ouverts.
- Workflow « incident » ; supervision, déploiement et maintenance derrière le répartiteur.
- Tribunal Sémantique, Ghost Search, filtre DLP.
- Niveaux de confidentialité de la mémoire.
- Paquets de déploiement reproductibles et multi-locataires.

Le détail est dans la [feuille de route](roadmap.md).

### 6. La suite

- **Démonstration** : la même question posée à un modèle distant puis au modèle local, depuis le même sélecteur de l'interface ; avec le modèle local, rien ne quitte le cluster.
- **Livre blanc** technique, en préparation.
- **Ouverture** aux retours d'ingénieurs, de chercheurs et d'organisations intéressés par une IA souveraine.

---

## Questions fréquentes

**SophIA est-elle souveraine aujourd'hui ?**
Oui pour l'usage courant : l'infrastructure, la mémoire, le contrôle d'accès et l'inférence de l'interface, des modules et des agents sont locaux. Un modèle distant ne reste qu'une dérogation de développement, choisie par routage.

**Faut-il un très gros modèle ?**
Non. Le confinement, les règles, la validation humaine et la sortie contrainte ne dépendent pas des capacités du modèle. Les tâches sont découpées en petites décisions, à la portée d'un modèle local modeste.

**Pourquoi ne pas utiliser une plateforme existante ?**
Parce que l'objectif est le contrôle : chaque brique est open source, remplaçable et auditable, et l'ensemble peut être reproduit sur l'infrastructure de l'organisation.

---

Voir aussi : [Vision](vision.md) · [Architecture](architecture.md) · [Sécurité](security.md) · [Glossaire](glossary.md)
