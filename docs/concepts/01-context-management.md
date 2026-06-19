# Context Management

Le **Context Management** definit la maniere dont SophIA construit, controle et limite le contexte fourni aux modeles d'intelligence artificielle.

Dans la plupart des systemes actuels, le contexte est constitue de maniere implicite a partir de l'historique du chat, d'un RAG approximatif, d'instructions systeme et de quelques outils disponibles. Cette approche fonctionne pour des usages simples mais devient rapidement instable dans des systemes complexes.

SophIA considere le contexte comme une ressource critique qui doit etre explicitement geree.

---

## Probleme

Les modeles de langage souffrent de plusieurs limitations structurelles :

- fenetre de contexte limitee
- perte d'information progressive
- pollution du contexte par des elements non pertinents
- difficulte a distinguer les instructions importantes
- dependance excessive a l'historique conversationnel

Dans les systemes multi-agents, ces problemes sont amplifies : accumulation de contexte inutile, duplication d'information, perte de coherence entre agents.

Sans controle explicite, le systeme devient lent, instable et imprevisible.

---

## Principe

Le Context Management repose sur une idee simple : le contexte envoye au modele doit etre construit intentionnellement, et non herite passivement d'une conversation.

Le systeme assemble dynamiquement le contexte a partir de plusieurs sources.

---

## Sources de contexte

### Instructions systeme

Definissent le role de l'agent et les regles generales : role de l'assistant, contraintes de securite, style de reponse attendu.

### Specifications du projet

Les specifications decrivent les objectifs du projet. Elles proviennent generalement du Brain.

### Memoire

Certaines informations persistantes peuvent etre injectees depuis la memoire : decisions passees, connaissances indexees, resultats de recherches.

### Etat de la tache

Le contexte peut inclure l'etat courant d'une tache : etape en cours, resultat intermediaire, historique limite des actions.

### Outils disponibles

Les capacites disponibles doivent etre connues du modele : acces a un repository, outils MCP, acces a un workspace.

---

## Construction du contexte

Le contexte est construit dynamiquement par l'orchestrateur. Le processus typique est :

1. identification du projet concerne
2. recuperation des specifications pertinentes
3. recuperation eventuelle de memoire
4. selection des outils disponibles
5. construction du prompt final

Cette construction permet de minimiser le bruit et maximiser la pertinence.

---

## Limitation volontaire du contexte

Un principe important de SophIA est de limiter volontairement le contexte. Plus de contexte ne signifie pas necessairement de meilleures reponses.

Un contexte trop large peut provoquer une dilution de l'information importante, des erreurs d'interpretation, et une augmentation du cout et de la latence.

Le systeme privilegie donc un contexte cible, structure et limite.

---

## Relation avec les autres concepts

Le Context Management est etroitement lie a plusieurs autres mecanismes de l'architecture :

- Le **Workspace Management** fournit l'environnement d'execution mais ne constitue pas une source de contexte durable.
- Le **Project Model** permet d'identifier les sources de contexte pertinentes pour un projet donne.
- Le **Tribunal Semantique** valide les connaissances avant leur integration dans la memoire.
- Le **RAG 5D** constitue la structuration de la memoire exploitable comme source de contexte.

---

## Objectif

L'objectif du Context Management est de garantir que les modeles disposent des bonnes informations, que le contexte reste maitrise, que les agents restent previsibles et que le systeme reste scalable.

Dans SophIA, le contexte n'est pas un effet de bord d'une conversation. Il devient un composant architectural a part entiere.
