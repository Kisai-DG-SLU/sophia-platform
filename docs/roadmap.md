# Feuille de Route SophIA

Le projet SophIA evolue progressivement de l'experimentation infrastructurelle vers une plateforme d'IA souveraine complete. Chaque etape ci-dessous correspond a une ou plusieurs phases du plan de travail ; une etape n'est dite « en service » que lorsqu'elle tourne dans l'installation de reference et que sa recette reproductible est publiee dans `deploy/`.

---

## Etape 0 : Fondations d'infrastructure

En service.

- Serveur bare-metal, cluster OKD a un noeud
- Acces par VPN uniquement ([`deploy/okd/host/wireguard/`](../deploy/okd/host/wireguard/))
- Stockage local persistant ([`deploy/stockage-persistant.md`](../deploy/stockage-persistant.md))
- Namespaces par zone de securite

---

## Etape 1 : Plateforme centrale

En service.

- Routage des modeles par LiteLLM : modeles distants et locaux derriere les memes alias ([`deploy/okd/core/`](../deploy/okd/core/))
- Inference locale : texte et vision sur GPU, voix et images sur CPU, sans sortie reseau ([`deploy/okd/inference/`](../deploy/okd/inference/))
- Identite et SSO : Keycloak pour toutes les interfaces ([`deploy/okd/identity/`](../deploy/okd/identity/))
- Interface de discussion ([`deploy/okd/apps/chat-interface/`](../deploy/okd/apps/chat-interface/))
- Recherche web par un sas isole, premiere brique du Sas Paranoiaque ([`deploy/okd/dmz/`](../deploy/okd/dmz/))
- Outils MCP locaux : geographie, images avec regles de protection ([`deploy/okd/skills/`](../deploy/okd/skills/))
- Plateforme Git et assistant de code persistant ([`deploy/okd/hermes-system/`](../deploy/okd/hermes-system/))

---

## Etape 2 : Agents et memoire

En cours.

- Communication entre agents : RabbitMQ pour les evenements, Temporal pour les delegations durables ([`deploy/okd/core/rabbitmq/`](../deploy/okd/core/rabbitmq/), [`deploy/okd/core/temporal/`](../deploy/okd/core/temporal/))
- Memoire et RAG (architecture 5+1), ingestion des documents
- Automatisation deterministe : un agent declenche un workflow, il ne le pilote pas
- Modules construits sur la plateforme ([`docs/modules/`](modules/))
- Gestion des espaces de travail, modele de projet, gestion de contexte

---

## Etape 3 : Securite et gouvernance

Travail futur.

- Permissions par roles, tribunal semantique
- Pipeline de filtrage DLP
- Chiffrement des volumes, isolation complete de la memoire
- Journalisation d'audit avancee, flux de verification des connaissances

---

## Etape 4 : Ouverture et supervision

Travail futur.

- Ouverture a d'autres utilisateurs
- Tableau de bord systeme, interface de connaissance
- Outils de supervision operationnelle

---

## Etape 5 : Industrialisation

Long terme.

- Packages de deploiement reproductibles
- Architecture de reference pour les organisations
- Support pour les deploiements multi-locataires
