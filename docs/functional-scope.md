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
| **Déterministe ou modèle** | le code orchestre, le modèle réfléchit, les règles décident : un processus métier s'exécute dans un moteur déterministe ; un agent peut le déclencher, pas le piloter ; un workflow peut solliciter le modèle à une étape définie — voir [Automation Déterministe](concepts/09-automation-deterministe.md) |
| **Deux couches** | en haut, l'interface : identité, gardes, réponses courtes, validations humaines ; en bas, les agents, exécutants joints par le seul répartiteur. Le modèle et la mémoire sont des services partagés par les deux couches — voir [Panthéon Agentique](concepts/08-pantheon-agentique.md) |
| **Répondre juste** | toute affirmation est sourcée dans la mémoire ; une inférence non vérifiée est marquée comme telle et reste à vérifier |
| **Enrichissement contrôlé** | chaque échange peut alimenter la mémoire, avec un niveau de confiance ; une information venue du web n'est mémorisée qu'après validation et consentement |
| **Fiabilité par l'infrastructure** | droits minimaux, décision par des règles sans modèle, validation humaine imposée par code, sortie contrainte, isolation réseau — quel que soit le modèle |
| **Agnosticisme** | modèle, logiciel et matériel sont remplaçables |
| **Souveraineté** | cible : inférence entièrement locale. Un modèle distant n'est qu'une dérogation de développement, choisie par routage — voir [Inférence et matériel](concepts/11-inference-materiel.md) |

---

## Fonctions du socle

| Fonction | Ce qu'elle fait | État |
|---|---|---|
| **Orchestratrice** | deux rôles. **L'interface**, interlocutrice principale : écoute, comprend la demande, répond aux demandes simples par des outils, recueille les validations ; pour le reste, elle devient **demandeur** du répartiteur. **Le planificateur**, pour les objectifs ouverts : un workflow qui découpe l'objectif une décision à la fois, fait valider chaque étape par des règles et l'exécuter par le répartiteur, puis traduit le résultat en rapport lisible ; le plan validé est versionné dans Git. **Aucun des deux ne modifie l'infrastructure lui-même** | en cours : interface opérationnelle pour les demandes simples, devenue le cockpit ; demandeur et planificateur prévus |
| **Panthéon d'agents** | un agent par domaine, des exécutants joints par le seul **répartiteur**, qui décide par des règles sans modèle : supervision en lecture seule, développement en autonomie, à terme dans un cluster virtuel éphémère par projet, déploiement limité aux applications, maintenance de la plateforme. Approbation du plan puis de chaque commande sur le déploiement et l'infrastructure — voir [Panthéon Agentique](concepts/08-pantheon-agentique.md) | en cours : répartiteur en service, développement en recette ; supervision, déploiement et maintenance prévus |
| **Communication asynchrone** | un workflow durable par délégation (Temporal, dont le répartiteur est le seul client), événements de progression publiés sur un bus (RabbitMQ) par le répartiteur seul, messages en échec en lettres mortes. Motif : une délégation qui code, teste et corrige dépasse les délais d'un appel synchrone | opérationnel : workflows et événements ; le bus n'a plus de files ni de comptes d'agents ; consommateurs des événements prévus |
| **Projets et discussions** | rattachement et promotion des discussions (principe ci-dessus), historique conservé et retrouvable ; droits par projet (masquage, invitations), demandes de rattachement validées par un adulte, journal intime par personne | opérationnel : discussions côté serveur, projets = dépôts Git, droits et journal |
| **Mémoire** | un service appelé par l'interface comme par les agents, chacun selon ses droits ; l'écriture en mémoire long terme revient au service mémoire, sous les règles des tags et du tribunal. Voir la section suivante | en cours : embedding et collection avec son schéma (18 étiquettes) en service, stockage objet en service ; API mémoire conçue ; ingestion et graphe à reconstruire |
| **Permissions** | rôles et niveaux de confidentialité ci-dessus ; alertes par mail, SMS ou interface | en cours : rôles et authentification unique (SSO) opérationnels ; modèles imposés par le serveur selon le rôle ([Modèles par rôle](concepts/13-modeles-par-role.md)) ; confidentialité de la mémoire et alertes prévues |
| **Connaissance externe sûre** | acquisition web isolée et nettoyée ([Sas Paranoïaque](concepts/04-sas-paranoiaque.md)), requêtes leurres ([Ghost Search](concepts/06-ghost-search.md)), validation croisée avant ingestion ([Tribunal Sémantique](concepts/05-tribunal-semantique.md)) | en cours : sas d'acquisition opérationnel (métamoteur auto-hébergé, pages réduites en texte sans script, adresses internes refusées) ; requêtes leurres et tribunal prévus |
| **Observabilité et réaction** | métrologie, règles d'alerte ; une alarme devient une demande au répartiteur, qui lance un workflow « incident » : collecte, diagnostic, plan, notification, exécution approuvée, aucune action automatique au départ — voir [Observabilité](concepts/10-observabilite.md) | en cours : métrologie de la plateforme et des services, règles d'alerte (remplissage des volumes compris), exporteur du nœud (carte graphique, garde-fou VPN), état mesuré de chaque composant et contrôle des miroirs ([module Visualisation](modules/visualisation/README.md)) en service ; alertes filtrées envoyées à l'administrateur hors de la plateforme, copie journalisée par le répartiteur ; registre des incidents et workflow « incident » prévus |
| **Filtre anti-fuite** | avant tout appel à un service distant : autoriser, anonymiser ou bloquer — voir [DLP Filter](concepts/07-dlp-filter.md) | prévu |
| **Inférence** | un modèle par agent via le routeur ; bascule entre modèle distant et modèle local par simple routage ; mesure comparative de qualité et de coût | opérationnel : modèle local par défaut sur le GPU du serveur (appels d'outils fiables) pour l'interface et les modules ; agents sur le modèle local par un alias de fond, places de la carte réparties selon l'heure, priorités CPU et quotas en service — voir [Inférence et matériel](concepts/11-inference-materiel.md) |
| **Gouvernance** | coût par token et par projet, budgets par clé ; journal des requêtes, des routages et des blocages ; analyse a posteriori | en cours : coûts et budgets opérationnels ; une clé par usage ; rétentions décidées ; conformité (RGPD, AI Act, ISO 27001) conçue |
| **Industrialisation** | recette reproductible, environnements multi-locataires, architecture de référence | prévu |

---

## Briques fonctionnelles

| Brique | Ce qu'elle fait | État |
|---|---|---|
| **Discussion** | interface web multi-modèles, avec coût affiché et historique ; aucune clé dans le navigateur ; connexion obligatoire, profil et contexte adaptés à chaque personne (date et heure comprises) | opérationnel, dans son namespace ; avis de nouvelle version ; thèmes visuels au choix (clair et sombre) et thèmes du calendrier (fêtes le jour même, saisons, anniversaire), polices et bibliothèques embarquées, sans CDN ; fichiers de la personne retrouvés, ouverts et lus (modèle local seulement) depuis la discussion |
| **Cockpit** | la discussion devient la coquille de toutes les interactions : un accueil pour parler à Sophia (avatar en hologramme qui montre la réflexion, l'outil appelé et la parole), un volet des modules choisis par le serveur selon le rôle, chaque application affichée au centre avec son propre visuel, un volet « Quoi de neuf ? » fait de résumés déterministes fournis par chaque application ; Sophia ouvre elle-même le bon module et la bonne page | en cours : coquille, accueil, états de Sophia, cuisine, école et visualisation au centre en service et vérifiés ; messagerie, visio et bureautique au centre, document ouvert depuis la bureautique et première version de « Quoi de neuf ? » en service, en recette ; ouverture sans clic prête, en cours de mise en service ; résumés des applications, accès par le cockpit seul (exception pour l'administrateur) et espace de supervision du développement prévus — voir [interface de discussion](../deploy/okd/apps/chat-interface/README.md) |
| **Lieux** | des lieux enregistrés dans chaque profil (lieux du foyer, lieux personnels) pour la météo, les distances, les cartes et les activités proches ; un lieu n'est retenu que s'il est dit par la personne ou enregistré, le dernier lieu dit vaut pour la suite de la discussion | en cours : gardes sur les lieux tirés par le modèle et lieu courant de la discussion en service ; lieux du profil (un invité n'a que les lieux qu'il nomme) et géocodage local des lieux enregistrés prévus |
| **Recherche** | la mémoire d'abord ; le web via le sas si l'information manque, sources classées par fiabilité et citées ; données de prévision pour la météo ; consentement avant mémorisation | en cours : recherche web opérationnelle, mémoire à construire |
| **Arbitre** | un modèle externe de haut niveau, interrogé par les agents via la file de messages, **après anonymisation** par le filtre anti-fuite | prévu |
| **Développement d'outils à la demande** | un besoin exprimé en discussion devient un projet ; un agent le code et le teste en sandbox ; un autre le déploie après validation humaine | en cours : environnements de développement pilotés par agents |
| **Automatisation déterministe** | moteur de workflows déclenché par les agents, et pouvant les solliciter à une étape définie | prévu |
| **Outils métier** | bureautique, graphisme, etc., exposés aux agents comme outils | en cours : bureautique (fichiers, édition en ligne) en service, outil MCP des fichiers sous l'identité de la personne, affichée dans le cockpit ([module Bureautique](modules/bureautique/README.md)) ; écriture par Sophia dans le document ouvert prévue ; chat permanent et visio du foyer en service, en recette, la visio par le navigateur seulement ([module Communication](modules/communication/README.md)) ; courrier reporté ; graphisme plus tard |
| **Voix et présence** | synthèse et reconnaissance vocales, speech-to-speech, vision ; à terme, un robot de compagnie open source pour une présence physique dans le lieu de vie | en cours : reconnaissance et synthèse vocales locales sur CPU (dictée envoyée, réponse lue au fil de l'écriture, synthèse en flux du service) ; speech-to-speech, vision et robot prévus |

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

L'implémentation de référence tourne sur un nœud unique, avec des GPU d'entrée de gamme — voir [Infrastructure POC](../deploy/infrastructure.md). La répartition visée attribue **une famille de tâches par carte** : modèle de langage, embedding, voix et vision. Chaque carte porte ses propres modèles, ce qui isole les charges. Aujourd'hui, une seule carte porte le modèle de langage, partagé entre la discussion, les modules et les agents ; voix, images et embedding tournent sur CPU — voir [Inférence et matériel](concepts/11-inference-materiel.md).

---

## Trajectoire

| Temps | Choix |
|---|---|
| **1. Assembler** | briques open source existantes, pour aller vite |
| **2. Rendre fonctionnel** | socle complet, puis briques ; les facilités du développement (modèles distants, étapes manuelles) sont levées une à une |
| **3. Redévelopper, éventuellement** | certaines briques réécrites par les agents de la plateforme, pour les performances, l'adéquation au besoin et la maintenance — **seulement une fois la solution fonctionnelle** |

---

Voir aussi : [Vision](vision.md) · [Pitch](pitch.md) · [Architecture](architecture.md) · [Feuille de route](roadmap.md)
