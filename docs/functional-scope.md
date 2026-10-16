# Périmètre fonctionnel

Ce document décrit **ce que SophIA doit faire et pour qui**. Les fiches [concepts](index.md#concepts-architecturaux) décrivent *comment* chaque mécanisme fonctionne, la [feuille de route](roadmap.md) dit *quand*.

Chaque fonction porte un état : **opérationnel**, **en cours** ou **prévu**. Ce qui est prévu décrit la cible, pas l'existant.

---

## En bref

1. **Le socle est une plateforme d'IA souveraine** : un cluster Kubernetes maîtrisé, une mémoire en plusieurs couches, un panthéon d'agents spécialisés, et une sécurité imposée par l'infrastructure plutôt que par le modèle.
2. **Des briques fonctionnelles s'y ajoutent** : discussion, recherche, développement d'outils, automatisation, voix.
3. **Trajectoire** : assembler des briques open source pour aller vite ; une fois la solution fonctionnelle, certaines briques pourront être redéveloppées par les agents de la plateforme elle-même.

---

## Intention

Un **assistant pour un foyer ou une organisation** : il discute, recherche, développe des outils selon les besoins, et enrichit sa mémoire en permanence pour répondre juste et de la manière la plus appropriée.

Il fait appel à des outils **déterministes quand la fiabilité l'exige**, et à des modèles de langage pour la créativité et la réflexion.

Le projet est mené avec des exigences professionnelles : reproductibilité, résilience, auditabilité. **Un matériel limité est traité comme une contrainte d'étude** : l'objectif est de l'atteindre malgré elle, ou de documenter les obstacles et les chemins pour y parvenir.

---

## Utilisateurs et rôles

| Rôle | Accès |
|---|---|
| **Administrateur** | tout ; une consultation d'urgence est notifiée et journalisée |
| **Responsable** | ses espaces ; destinataire des alertes concernant les utilisateurs protégés dont il a la charge |
| **Utilisateur protégé** (par exemple un mineur) | son espace personnel et intime uniquement ; une alerte est envoyée à son responsable en cas de situation critique |
| **Invité** | informations publiques uniquement |

Cinq niveaux de confidentialité, du plus ouvert au plus restreint : `public` > `famille` (ou groupe) > `personnel` > `intime` > `admin`.

---

## Principes transverses

| Principe | Énoncé |
|---|---|
| **Tout est projet** | une activité professionnelle, un projet personnel, un développement, une étude. Un projet réunit un **Brain** (mémoire, spécifications), un **Repository** (livrable) et un **Workspace** (éphémère, jamais source de vérité) — voir [Project Model](concepts/00-project-model.md) |
| **Les discussions sont des projets** | chaque nouvelle discussion est **rattachée** à un projet existant, au projet global de discussion, ou ouverte en nouveau projet. Une discussion qui s'enrichit est **promue** en projet à part entière. À terme, tout se pilote par la discussion, y compris le développement |
| **Déterministe ou modèle** | un processus métier s'exécute dans un moteur déterministe ; un agent peut le déclencher, pas le piloter — voir [Automation Déterministe](concepts/09-automation-deterministe.md) |
| **Répondre juste** | toute affirmation est sourcée dans la mémoire ; une inférence non vérifiée est marquée comme telle et reste à vérifier |
| **Enrichissement contrôlé** | chaque échange peut alimenter la mémoire, avec un niveau de confiance ; une information venue du web n'est mémorisée qu'après validation et consentement |
| **Fiabilité par l'infrastructure** | droits minimaux, validation humaine imposée par code, JSON strict entre agents, isolation réseau — quel que soit le modèle |
| **Agnosticisme** | modèle, logiciel et matériel sont remplaçables |
| **Souveraineté** | cible : inférence entièrement locale. Un modèle distant reste un choix de routage, utilisable pendant le développement |

---

## Fonctions du socle

| Fonction | Ce qu'elle fait | État |
|---|---|---|
| **Orchestratrice** | interlocutrice principale : écoute, challenge la demande, valide le plan (intention, action, rapport), rédige la spécification dans Git, délègue, traduit le résultat des agents en rapport lisible. **Elle ne modifie jamais l'infrastructure elle-même** | en cours |
| **Panthéon d'agents** | un agent par domaine : supervision en lecture seule, développement en sandbox, déploiement d'applications, maintenance d'infrastructure. Validation humaine sur le déploiement et l'infrastructure — voir [Panthéon Agentique](concepts/08-pantheon-agentique.md) | en cours : agents déployés |
| **Communication asynchrone** | une file par agent, file de messages en échec, événements de progression. Motif : une délégation qui code, teste et corrige dépasse les délais d'un appel synchrone | prévu |
| **Projets et discussions** | rattachement et promotion des discussions (principe ci-dessus), historique conservé et retrouvable ; droits par projet (masquage, invitations), demandes de rattachement validées par un adulte, journal intime par personne | opérationnel : discussions côté serveur, projets = dépôts Git, droits et journal |
| **Mémoire** | voir la section suivante | en cours : couches déployées, ingestion à construire |
| **Permissions** | rôles et niveaux de confidentialité ci-dessus ; alertes par mail, SMS ou interface | en cours : rôles et authentification unique (SSO) opérationnels ; confidentialité de la mémoire et alertes prévues |
| **Connaissance externe sûre** | acquisition web isolée et nettoyée ([Sas Paranoïaque](concepts/04-sas-paranoiaque.md)), requêtes leurres ([Ghost Search](concepts/06-ghost-search.md)), validation croisée avant ingestion ([Tribunal Sémantique](concepts/05-tribunal-semantique.md)) | en cours : sas d'acquisition opérationnel (métamoteur auto-hébergé, pages réduites en texte sans script, adresses internes refusées) ; requêtes leurres et tribunal prévus |
| **Filtre anti-fuite** | avant tout appel à un service distant : autoriser, anonymiser ou bloquer — voir [DLP Filter](concepts/07-dlp-filter.md) | prévu |
| **Inférence** | un modèle par agent via le routeur ; bascule entre modèle distant et modèle local par simple routage ; mesure comparative de qualité et de coût | opérationnel : modèle local par défaut sur le GPU du serveur (appels d'outils fiables), modèles distants au choix pour le raisonnement long |
| **Gouvernance** | coût par token et par projet, budgets par clé ; journal des requêtes, des routages et des blocages ; analyse a posteriori | en cours : coûts et budgets opérationnels |
| **Industrialisation** | recette reproductible, environnements multi-locataires, architecture de référence | prévu |

---

## Briques fonctionnelles

| Brique | Ce qu'elle fait | État |
|---|---|---|
| **Discussion** | interface web multi-modèles, avec coût affiché et historique ; aucune clé dans le navigateur ; connexion obligatoire, profil et contexte adaptés à chaque personne (date et heure comprises) | opérationnel |
| **Recherche** | la mémoire d'abord ; le web via le sas si l'information manque, sources classées par fiabilité et citées ; données de prévision pour la météo ; consentement avant mémorisation | en cours : recherche web opérationnelle, mémoire à construire |
| **Arbitre** | un modèle externe de haut niveau, interrogé par les agents via la file de messages, **après anonymisation** par le filtre anti-fuite | prévu |
| **Développement d'outils à la demande** | un besoin exprimé en discussion devient un projet ; un agent le code et le teste en sandbox ; un autre le déploie après validation humaine | en cours : environnements de développement pilotés par agents |
| **Automatisation déterministe** | moteur de workflows déclenché par les agents, et pouvant les solliciter à une étape définie | prévu |
| **Outils métier** | bureautique, graphisme, etc., exposés aux agents comme outils | prévu, à plus long terme |
| **Voix et présence** | synthèse et reconnaissance vocales, speech-to-speech, vision ; à terme, un robot de compagnie open source pour une présence physique dans le lieu de vie | en cours : reconnaissance et synthèse vocales locales sur CPU (dictée envoyée, réponse lue) ; speech-to-speech, vision et robot prévus |

---

## Mémoire : deux axes complémentaires

### Les cinq couches de stockage (RAG 5D)

| # | Couche | Rôle | Exemple |
|---|---|---|---|
| 1 | Dépôt Git | source de vérité versionnée | Forgejo |
| 2 | Base relationnelle | faits horodatés, références des fichiers stockés, droits, métadonnées | PostgreSQL |
| 3 | Base vectorielle | proximité sémantique | Qdrant |
| 4 | Base graphe | relations complexes ou transverses | Neo4j |
| 5 | Graphe de notes | visualisation humaine, synchronisée depuis les autres couches | Obsidian |

Détail : [RAG 5D](concepts/03-rag-5d.md).

### Les types de mémoire (5 + 1)

| Type | Contenu | Couches |
|---|---|---|
| Sémantique | faits et connaissances stables | vectorielle + relationnelle |
| Épisodique | événements datés, conversations, décisions | relationnelle |
| Procédurale | rôles des agents, modèles, prompts, workflows | Git |
| Personnelle et intime | journal, échanges confidentiels, isolés par niveau de confidentialité | vectorielle + relationnelle |
| Graphe | relations entre projets, décisions, conséquences | graphe |
| **+1 : historisation brute** | transcripts complets des échanges, pour l'audit, le rejeu et le sourçage | Git |

Chaque information porte un jeu de **tags** fixé par l'administrateur (auteur, dates, type de mémoire, provenance, format, niveau de confiance, confidentialité, projet, statut de validation…). Les agents ne peuvent pas en créer.

---

## Matériel

L'implémentation de référence tourne sur un nœud unique, avec des GPU d'entrée de gamme — voir [Infrastructure POC](../deploy/infrastructure.md). La répartition visée attribue **une famille de tâches par carte** : modèle de langage, embedding, voix et vision. Chaque carte porte ses propres modèles, ce qui isole les charges.

---

## Trajectoire

| Temps | Choix |
|---|---|
| **1. Assembler** | briques open source existantes, pour aller vite |
| **2. Rendre fonctionnel** | socle complet, puis briques ; les facilités du développement (modèles distants, étapes manuelles) sont levées une à une |
| **3. Redévelopper, éventuellement** | certaines briques réécrites par les agents de la plateforme, pour les performances, l'adéquation au besoin et la maintenance — **seulement une fois la solution fonctionnelle** |

---

Voir aussi : [Vision](vision.md) · [Pitch](pitch.md) · [Architecture](architecture.md) · [Feuille de route](roadmap.md)
