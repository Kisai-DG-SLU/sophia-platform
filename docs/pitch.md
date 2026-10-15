# SophIA en bref

Ce document présente SophIA en trois longueurs : une phrase, trente secondes, trois minutes. Il dit aussi clairement ce qui fonctionne déjà et ce qui reste à construire.

---

## En une phrase

**SophIA assemble des briques open source en une plateforme d'IA agentique que l'organisation héberge, gouverne et audite elle-même. La sécurité vient de l'architecture, pas du modèle.**

---

## En trente secondes

Les organisations veulent des agents d'IA. Mais elles ne peuvent pas confier leurs données sensibles à des plateformes opaques hors de leur juridiction, ni laisser des agents autonomes agir sans garde-fous.

SophIA est une architecture de référence qui répond à ces deux contraintes. Elle repose sur un cluster que l'organisation contrôle. Chaque agent spécialisé vit dans un environnement confiné, avec des droits minimaux, et les actions critiques attendent une validation humaine. La mémoire est versionnée dans Git. Un routeur de modèles accepte n'importe quel modèle, local ou distant.

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

- un agent qui génère une commande destructrice est arrêté par le contrôle d'accès du cluster ;
- une action de modification attend une validation humaine, imposée par le code et non par une consigne ;
- les sous-agents ne communiquent qu'en JSON strict, et tout écart est rejeté ;
- le réseau limite chaque composant à son périmètre.

Ces garde-fous fonctionnent quel que soit le modèle, du plus petit au plus grand.

### 3. La solution : quatre piliers

| Pilier | Ce que cela apporte |
|---|---|
| **Souveraineté** | Infrastructure Kubernetes maîtrisée, stockage local, mémoire de projet dans une forge Git auto-hébergée. Routeur de modèles agnostique : un modèle local ou distant est un choix de routage, pas une dépendance. |
| **Panthéon agentique** | Des agents spécialisés, un domaine chacun : développement en sandbox, déploiement, maintenance, supervision en lecture seule. Droits minimaux, validation humaine sur les actions critiques. |
| **Mémoire RAG 5D** | Cinq dimensions complémentaires : vectorielle, relationnelle, versionnée, structurelle, graphe. Chaque fait retrouvé peut être relié à sa source. |
| **Sécurité par conception** | Acquisition web isolée et nettoyée (Sas Paranoïaque), validation croisée avant ingestion (Tribunal Sémantique), requêtes leurres (Ghost Search), filtrage des fuites (DLP), journalisation des interactions. |

### 4. Ce qui différencie SophIA

SophIA n'est pas un produit de plus. C'est **une recette reproductible** qui assemble des composants existants (Kubernetes, LiteLLM, Qdrant, PostgreSQL, Forgejo, agents Hermes) de manière cohérente.

- **Reproductible** : l'infrastructure est décrite et versionnée.
- **Auditable** : les décisions, le code et la mémoire sont tracés dans Git.
- **Indépendante du modèle** : le comportement agentique est imposé par l'infrastructure, pas supposé du modèle.

### 5. Où en est le projet

SophIA est une architecture expérimentale en construction. Nous distinguons ce qui fonctionne de ce qui est prévu.

**Opérationnel aujourd'hui**

- Cluster Kubernetes (OKD) mono-nœud sur serveur physique, accès VPN, GPU disponible.
- Forge Git auto-hébergée, source de vérité du code et de la mémoire des projets.
- Routeur de modèles unifié, avec plusieurs profils (routine, réflexion, architecture).
- Environnements de développement isolés, pilotés par des agents.
- Interface de discussion connectée au routeur, sans aucune clé dans le navigateur.
- Agents du panthéon déployés, chacun dans son propre environnement.
- Base vectorielle et service d'embedding en service.

**En cours**

- Inférence sur GPU local. Aujourd'hui, les modèles passent par un fournisseur distant via le routeur : la souveraineté est garantie par la conception, pas encore par l'exploitation.
- Pipeline d'ingestion de la mémoire et dimension graphe.
- Bus de communication entre agents.

**Prévu**

- Sas Paranoïaque, Tribunal Sémantique, filtre DLP.
- Permissions par rôle et niveaux de confidentialité de la mémoire.
- Paquets de déploiement reproductibles et multi-locataires.

Le détail est dans la [feuille de route](roadmap.md).

### 6. La suite

- **Démonstration** : la même question posée à un modèle distant puis à un modèle local, depuis la même interface, sans que les données locales quittent le cluster.
- **Livre blanc** technique, en préparation.
- **Ouverture** aux retours d'ingénieurs, de chercheurs et d'organisations intéressés par une IA souveraine.

---

## Questions fréquentes

**SophIA est-elle souveraine aujourd'hui ?**
Elle l'est par sa conception : l'infrastructure, la mémoire et le contrôle d'accès sont maîtrisés. L'inférence passe encore par un fournisseur distant, et le passage au GPU local est en cours. Le routeur rend cette bascule transparente pour les utilisateurs et les agents.

**Faut-il un très gros modèle ?**
Non. Le confinement, la validation humaine et le format de sortie imposé ne dépendent pas des capacités du modèle.

**Pourquoi ne pas utiliser une plateforme existante ?**
Parce que l'objectif est le contrôle : chaque brique est open source, remplaçable et auditable, et l'ensemble peut être reproduit sur l'infrastructure de l'organisation.

---

Voir aussi : [Vision](vision.md) · [Architecture](architecture.md) · [Sécurité](security.md) · [Glossaire](glossary.md)
