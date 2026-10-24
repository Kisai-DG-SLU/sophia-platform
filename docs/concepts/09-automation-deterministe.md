# Automation Déterministe : séparation des moteurs

Le module d'**Automation Déterministe** définit la séparation stricte entre la réflexion, qui relève des modèles de langage, et l'exécution des processus, qui relève de moteurs déterministes.

L'objectif est de ne pas confier à un système probabiliste (un modèle de langage) l'exécution de processus qui exigent une fiabilité absolue.

---

## Problème

Les modèles de langage sont des systèmes probabilistes. Même avec un taux de réussite élevé, ils gardent une probabilité non nulle d'erreur, de hors-sujet ou d'hallucination.

Pour une tâche créative ou exploratoire, cette variabilité est acceptable. Pour un processus reproductible (envoi de notifications, mise à jour de bases, déclenchement d'une validation, action sur l'infrastructure), elle ne l'est pas.

---

## Principe

**Le code orchestre, le modèle réfléchit, les règles décident.**

- **Réfléchir** est un appel au modèle : comprendre, découper, proposer. Son résultat est probabiliste et soumis à validation.
- **Exécuter** relève d'un moteur déterministe : le processus s'exécute correctement, ou il échoue avec une cause identifiable.
- **L'autonomie d'exécution**, c'est-à-dire une boucle d'agent libre avec des outils, est réservée aux rôles dont c'est le métier, comme le développement (voir [Panthéon Agentique](08-pantheon-agentique.md)).

Un agent peut déclencher un workflow, il n'en pilote pas l'exécution. Et, à l'inverse, **un workflow peut solliciter le modèle à une étape définie** : c'est le motif général de SophIA.

---

## Le workflow sollicite le modèle

Chaque fois qu'il faut réfléchir avant d'agir, le même motif s'applique :

1. **Analyse.** Le modèle reçoit le contexte et rend une réponse **en sortie contrainte** (un schéma imposé) : par exemple « prochaine étape : outil, cible, arguments ».
2. **Décision.** Des règles déterministes valident la réponse : outil de la liste fermée, cible autorisée, arguments bien formés, quota, validation humaine exigée ou non.
3. **Exécution.** Une compétence déterministe fait l'appel, ou le répartiteur transmet la demande à l'agent concerné.
4. **Retour.** Le résultat revient au modèle, qui synthétise ou propose l'étape suivante.

La boucle est **bornée par le code** (nombre d'étapes, durée). Le modèle prend **une décision à la fois**, plutôt qu'un plan entier : un modèle local modeste y suffit, et chaque décision reste contrôlable.

| Usage | Ce que fait le modèle | État |
|---|---|---|
| **Interface de discussion** | comprend la demande et choisit l'outil ; le serveur fabrique l'appel | en service |
| **Délégations** | rien : le répartiteur décide par ses règles, le workflow exécute | en service |
| **Planificateur** des objectifs ouverts | découpe l'objectif, une étape à la fois, entre les outils et les agents | prévu (prototype) |
| **Maintenance** | rédige une proposition (le pourquoi et le manifeste) ; un humain l'approuve, puis chaque commande | prévu |
| **Incidents** | diagnostique à partir d'une collecte déterministe et propose un plan (voir [Observabilité](10-observabilite.md)) | prévu |

---

## Définition des workflows

Les workflows sont écrits explicitement, en code ou par programmation visuelle. Chacun précise :

- les événements déclencheurs
- les étapes d'exécution
- les conditions de branchement, évaluées par des opérateurs logiques et non par un modèle
- les actions en cas d'erreur : l'échec d'une étape interrompt le workflow et déclenche la procédure prévue
- les notifications et la journalisation

---

## Moteurs

| Moteur | Usage | État |
|---|---|---|
| **Temporal** | workflows durables en code : délégations entre agents, puis planificateur et incidents. L'historique de chaque workflow sert de journal | en service pour les délégations |
| **n8n** | automatisations par programmation visuelle (connecteurs, notifications) | prévu, déployé avec le premier outil qui en a besoin ; hors du chemin des délégations |

Le moteur de workflows durables n'a qu'un client applicatif, le répartiteur (`sophia-core`) : aucun agent n'y accède directement.

---

## Objectif

Garantir que les processus reproductibles s'exécutent de manière fiable et prévisible, quel que soit l'état du modèle. Le modèle apporte la compréhension là où elle est nécessaire ; le code et les règles gardent la main sur ce qui est fait.
