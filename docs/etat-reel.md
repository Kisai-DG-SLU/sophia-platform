# État réel de SophIA

État au **15/11/2026**, pour l'installation de référence : un serveur physique, un cluster à un nœud, un foyer. Cette page dit, brique par brique, ce qui tourne, ce qui se construit et ce qui reste prévu. Le récit est dans le [pitch](pitch.md) et l'ordre des travaux dans la [feuille de route](roadmap.md).

Trois états :

- **Déployé** : en service dans l'installation de référence. « En recette » précise que le foyer l'éprouve encore sur ses appareils, avant de le dire vérifié.
- **En cours** : décidé et en cours de construction, ou en partie en place.
- **Prévu** : à faire, pas encore commencé.

Une brique n'est dite déployée que si elle tourne **et** que sa recette reproductible, ou sa fiche, est publiée dans ce dépôt.

---

## Socle et sécurité

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Cluster OKD à un nœud sur serveur physique | Déployé | namespaces par zone de sécurité, quotas et classes de priorité par namespace | [`deploy/`](../deploy/README.md), [`okd/cluster/`](../deploy/okd/cluster/README.md) |
| Accès par VPN seulement | Déployé | filtre du VPN sur le nœud, avec un garde-fou qui retire la table et alerte si elle devient illisible | [`okd/host/wireguard/`](../deploy/okd/host/wireguard/README.md) |
| Stockage local persistant | Déployé | volumes locaux désignés, volumes logiques dédiés pour les données qui grossissent | [stockage persistant](../deploy/stockage-persistant.md) |
| Refus par défaut en entrée | Déployé, extension en cours | en place dans les applications, l'orchestration et la mémoire ; les autres namespaces suivent | [sécurité](security.md) |
| Images figées par empreinte et veille des failles | En cours | inventaire, scanner local, alerte ; montée de version décidée, jamais automatique | [sécurité](security.md#améliorations-prévues) |
| Chiffrement du trafic interne | En cours | service par service, par les certificats de service du cluster | [sécurité](security.md) |
| Volumes chiffrés | Prévu | pas encore en place : volumes locaux non chiffrés | [sécurité](security.md#protection-des-données) |
| Double authentification | Prévu | comptes d'administration et responsables | [feuille de route](roadmap.md) |

## Inférence et modèles

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Modèle de langage local sur GPU (texte et vision) | Déployé | modèle local par défaut de l'interface et des modules, sans sortie réseau | [`okd/inference/`](../deploy/okd/inference/README.md), [inférence et matériel](concepts/11-inference-materiel.md) |
| Voix sur CPU (reconnaissance et synthèse) | Déployé | réponse lue à voix haute pendant qu'elle s'écrit | [`okd/inference/`](../deploy/okd/inference/README.md) |
| Génération d'images sur CPU | Déployé | règles de protection avant la génération, classifieur sur chaque image produite | [`okd/inference/`](../deploy/okd/inference/README.md), [`okd/skills/`](../deploy/okd/skills/README.md) |
| Routeur de modèles unifié (LiteLLM) | Déployé | local et distant derrière les mêmes alias, une clé virtuelle par usage, clé maître confinée au routeur | [`okd/core/`](../deploy/okd/core/README.md), [modèles par rôle](concepts/13-modeles-par-role.md) |
| Mesure d'un modèle à experts (carte et mémoire vive) | En cours | avant tout changement de modèle | [feuille de route](roadmap.md) |
| Décodage spéculatif, nouvelle série de mesures | Prévu | | |
| Caméra : objets et visages sur CPU | Prévu | règles de consentement avant tout visage enregistré | |

## Mémoire

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Base vectorielle (Qdrant) et son schéma, service d'embedding | Déployé | volume dédié ; l'embedding passe par le routeur de modèles | [`okd/memory/`](../deploy/okd/memory/README.md) |
| Stockage objet S3 | Déployé | corbeille, seau versionné pour les originaux | [`okd/storage/`](../deploy/okd/storage/README.md) |
| Service mémoire | Déployé | originaux dans un seau versionné, registre des versions, textes validés dans la forge, validation par une seule personne, extraction des fichiers isolée | [`okd/memory/memoire/`](../deploy/okd/memory/memoire/README.md), [RAG 5D](concepts/03-rag-5d.md) |
| Niveaux de confidentialité de la mémoire | En cours | contrôlés pour les personnes dans le service mémoire ; les agents restent au niveau public tant que le répartiteur ne transmet pas la personne servie | [feuille de route](roadmap.md) |
| Page « Mémoire » du dashboard, outil mémoire de la discussion | En cours | page de dépôt et de validation déployée ; consultation depuis la discussion sous l'identité de la personne | [interface](../deploy/okd/apps/chat-interface/README.md) |
| Façade de la mémoire pour les agents | Prévu | | |
| Pipeline d'ingestion | Prévu | documents lus dans le stockage objet, versés par le service mémoire | |
| Dimension graphe | Prévu | bloquée en attendant le choix de l'image et du volume | |

## Agents et orchestration

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Bus d'événements (RabbitMQ) et workflows durables (Temporal) | Déployé | administration derrière le fournisseur d'identité ; consommateurs des événements à faire | [RabbitMQ](../deploy/okd/core/rabbitmq/README.md), [Temporal](../deploy/okd/core/temporal/README.md) |
| Répartiteur des délégations | Déployé | seul client de Temporal et seul éditeur d'événements, décide par des règles sans modèle | [`okd/core/repartiteur/`](../deploy/okd/core/repartiteur/README.md) |
| Agents du panthéon sur le modèle local | Déployé | alias « de fond » qui laisse la priorité à la discussion, une clé du routeur par agent | [`okd/hermes-system/`](../deploy/okd/hermes-system/README.md) |
| Premier agent exécutant (développement) | Déployé, en recette | une mission à la fois | [`okd/hermes-system/`](../deploy/okd/hermes-system/README.md) |
| Interface comme demandeur du répartiteur | En cours | canal de retour pour les validations et les notifications | [feuille de route](roadmap.md) |
| TLS mutuel entre le répartiteur et les exécutants | Prévu | | |
| Délégations vers la supervision, le déploiement et la maintenance | Prévu | approbations à deux niveaux | |
| Planificateur des objectifs ouverts | Prévu | prototype en workflow, comparé à un agent planificateur | |
| Automatisation déterministe (n8n) | Prévu | avec le premier outil qui en a besoin | [automatisation déterministe](concepts/09-automation-deterministe.md) |
| Filtre anti-fuite, Tribunal Sémantique, Ghost Search | Prévu | | [DLP](concepts/07-dlp-filter.md), [Tribunal](concepts/05-tribunal-semantique.md), [Ghost Search](concepts/06-ghost-search.md) |

## Identité

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Fournisseur d'identité unique (Keycloak) | Déployé | une connexion pour toutes les interfaces, groupes du foyer | [`okd/identity/`](../deploy/okd/identity/README.md) |
| Sessions d'authentification côté serveur | Déployé | un stockage clé-valeur réservé, un utilisateur par application | [sessions](../deploy/okd/identity/sessions/README.md) |
| Relais de l'identité jusqu'aux outils et aux applications | Déployé | jeton de la personne, audience par service | [relais de l'identité](concepts/12-relais-identite.md) |
| Date de naissance des comptes, lue par une application | Déployé | client de lecture limité à un groupe, aucune date dans les jetons | [identité](../deploy/okd/identity/README.md#date-de-naissance-des-comptes-lue-par-une-application) |
| Connexion unique pour les outils d'administration (forge, console du cluster) | En cours | | |

## Interface et dashboard

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Interface de discussion | Déployé | namespace dédié, aucune clé dans le navigateur, aucune dépendance externe, modèle imposé par le serveur selon le rôle | [interface](../deploy/okd/apps/chat-interface/README.md) |
| Dashboard : applications au centre, chacune sous sa propre connexion | Déployé | cuisine, école, visualisation et finances vérifiées ; messagerie, visio et bureautique en recette ; courrier et courses ajoutés, en recette | [intégrer un module](modules/README.md#intégrer-un-module-au-dashboard) |
| « Quoi de neuf ? », « Demander à Sophia », ouverture de la bonne page par Sophia | Déployé, en recette | résumés déterministes des applications | [interface](../deploy/okd/apps/chat-interface/README.md) |
| Se déconnecter du dashboard ferme les modules | Déployé, en recette | | [interface](../deploy/okd/apps/chat-interface/README.md) |
| Lieux du foyer et météo | Déployé | la météo ne reçoit que le centre de la commune ; cache de secours vérifié | [interface](../deploy/okd/apps/chat-interface/README.md) |
| Géocodage local des adresses enregistrées | En cours | | |
| Accès aux applications par le dashboard seul | Prévu | exception pour l'administrateur (dépannage) | [modules](modules/README.md) |

## Modules

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Cuisine | Déployé | planning des repas, recettes générées sous règles, courses ; vérifiée dans le dashboard | [Cuisine](modules/cuisine/README.md) |
| École | Déployé | école ludique, indices sans la réponse ; vérifiée sur ordinateur, reconnexion au téléphone en recette | [École](modules/ecole/README.md) |
| Courses | Déployé | choix des produits selon les règles du foyer, panier express ; affichage dans le dashboard en recette | [Courses](modules/courses/README.md) |
| Visualisation | Déployé | état mesuré de chaque composant, contrôle horaire des miroirs des dépôts ; pour l'administrateur | [Visualisation](modules/visualisation/README.md) |
| Applications de gestion (clients, facturation, finances) | Déployé | base commune par domaine, sans API ni copie entre elles | [données partagées](architecture.md#données-partagées-entre-applications) |
| Base commune du foyer (lieux, plus tard les membres) | Prévu | écrite par le dashboard, lue par les modules | [données partagées](architecture.md#données-partagées-entre-applications) |
| Courrier | En cours | affichage dans le dashboard en recette | [feuille de route](roadmap.md) |
| Développement assisté (vibe coding) | En cours | étude : maquettes visuelles des projets de chacun, suivi des agents | [développement assisté](development/opencode-workflow.md) |

## Communication et bureautique

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Bureautique : fichiers et édition en ligne | Déployé, en recette | documents retrouvés, ouverts et lus depuis la discussion sous l'identité de la personne ; API REST de l'éditeur jamais exposée | [Bureautique](modules/bureautique/README.md), [recette](../deploy/okd/office/README.md) |
| Poste au navigateur par enfant (tablettes anciennes) | Déployé, en recette | allumé à la demande, éteint au repos | [Bureautique](modules/bureautique/README.md) |
| Messagerie du foyer (XMPP : Prosody, Converse.js) | Déployé, en recette | salon Famille, notifications Android sans contenu, « dis à » | [recette XMPP](../deploy/okd/office/README.md#messagerie-xmpp-version-définitive), [Communication](modules/communication/README.md) |
| Chiffrement de bout en bout refusé côté serveur | Déployé, en recette | choix du foyer : l'administrateur peut lire les salons | [recette](../deploy/okd/office/README.md#chiffrement-refusé-côté-serveur) |
| Visio (Jitsi Meet, par le navigateur seulement) | Déployé, en recette | média joignable par le VPN seulement | [chat permanent et visio](../deploy/okd/office/README.md#chat-permanent-et-visio) |
| Démontage de l'ancienne messagerie (Matrix) | En cours | lisible jusqu'à la fin de la recette | [Communication](modules/communication/README.md) |

## Exploitation

| Capacité | État | Détail | Recette ou fiche |
|---|---|---|---|
| Supervision minimale | Déployé | métriques des services, règles d'alerte, carte graphique, remplissage des volumes ; alertes filtrées envoyées à l'administrateur hors de la plateforme | [`okd/monitoring/`](../deploy/okd/monitoring/README.md), [observabilité](concepts/10-observabilite.md) |
| Workflow « incident » et registre des incidents | Prévu | de l'alarme au plan approuvé, sans action automatique | [observabilité](concepts/10-observabilite.md) |
| Sauvegarde planifiée et chiffrée | En cours | pas encore en service ; solutions recommandées : chiffrement côté client, copie locale et copie hors site souveraine, essai de restauration | [sécurité](security.md#sauvegarde-et-stockage--solutions-souveraines) |
| Recettes reproductibles par composant | Déployé | gabarits à variables et procédures publiés dans ce dépôt | [`deploy/`](../deploy/README.md) |
| Portabilité d'une installation | En cours | noms et chemins du nœud en variables dans les gabarits ; reste le choix du nœud de chaque volume | [feuille de route](roadmap.md) |
| Contrôle de dérive entre le cluster et les dépôts | En cours | en lecture, déterministe, avec alerte | |
| Procédure d'installation du cluster | Prévu | préalable à la reconstruction du serveur en une journée | |
| Conformité (RGPD, AI Act, ISO 27001) | En cours | conçu : état des lieux mesuré, plan d'action, suivi | [Visualisation](modules/visualisation/README.md) |
| Ouverture à d'autres utilisateurs, déploiements multi-locataires | Prévu | | [feuille de route](roadmap.md) |
