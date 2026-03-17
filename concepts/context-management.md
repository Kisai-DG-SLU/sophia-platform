# Context Management

Le **Context Management** définit la manière dont SOPHIA construit, contrôle et limite le contexte fourni aux modèles d'intelligence artificielle.

Dans la plupart des systèmes actuels, le contexte est constitué de manière implicite à partir :

- de l'historique du chat
- d'un RAG approximatif
- d'instructions système
- de quelques outils disponibles

Cette approche fonctionne pour des usages simples, mais devient rapidement instable dans des systèmes complexes.

SOPHIA considère donc le **contexte comme une ressource critique qui doit être explicitement gérée**.

---

## Problème

Les modèles de langage souffrent de plusieurs limitations structurelles :

- **fenêtre de contexte limitée**
- **perte d'information progressive**
- **pollution du contexte par des éléments non pertinents**
- **difficulté à distinguer les instructions importantes**
- **dépendance excessive à l'historique conversationnel**

Dans les systèmes multi-agents, ces problèmes sont amplifiés :

- accumulation de contexte inutile
- duplication d'information
- perte de cohérence entre agents

Sans contrôle explicite, le système devient :

- lent
- instable
- imprévisible

---

## Principe

Le Context Management repose sur une idée simple :

> Le contexte envoyé au modèle doit être **construit intentionnellement**, et non hérité passivement d'une conversation.

Le système assemble dynamiquement le contexte à partir de plusieurs sources.

---

## Sources de contexte

Le contexte d'une requête peut être constitué de plusieurs éléments.

### Instructions système

Définissent le rôle de l'agent et les règles générales.

Exemples :

- rôle de l'assistant
- contraintes de sécurité
- style de réponse attendu

---

### Spécifications du projet

Les spécifications décrivent les objectifs du projet.

Elles proviennent généralement du **Brain**.

Exemples :

- objectifs
- contraintes techniques
- décisions d'architecture

---

### Mémoire

Certaines informations persistantes peuvent être injectées depuis la mémoire.

Exemples :

- décisions passées
- connaissances indexées
- résultats de recherches

---

### État de la tâche

Le contexte peut inclure l'état courant d'une tâche :

- étape en cours
- résultat intermédiaire
- historique limité des actions

---

### Outils disponibles

Les capacités disponibles doivent être connues du modèle.

Exemples :

- accès à un repository
- outils MCP
- accès à un workspace

---

## Construction du contexte

Le contexte est construit dynamiquement par l'orchestrateur.

Le processus typique est :

1. identification du projet concerné
2. récupération des specs pertinentes
3. récupération éventuelle de mémoire
4. sélection des outils disponibles
5. construction du prompt final

Cette construction permet de **minimiser le bruit et maximiser la pertinence**.

---

## Limitation volontaire du contexte

Un principe important de SOPHIA est de **limiter volontairement le contexte**.

Plus de contexte ne signifie pas nécessairement de meilleures réponses.

Un contexte trop large peut provoquer :

- dilution de l'information importante
- erreurs d'interprétation
- augmentation du coût et de la latence

Le système privilégie donc un contexte :

- ciblé
- structuré
- limité

---

## Relation avec les autres concepts

Le Context Management est étroitement lié à plusieurs autres mécanismes de l'architecture :

### Workspace Management

Le workspace fournit l'environnement d'exécution mais ne constitue pas une source de contexte durable.

---

### Project Model

Le project model permet d'identifier les sources de contexte pertinentes pour un projet donné.

---

### Tribunal Sémantique

Le tribunal sémantique valide les connaissances avant leur intégration dans la mémoire.

Cela garantit que les informations injectées dans le contexte sont fiables.

---

## Objectif

L'objectif du Context Management est de garantir que :

- les modèles disposent des bonnes informations
- le contexte reste maîtrisé
- les agents restent prévisibles
- le système reste scalable

Dans SOPHIA, le contexte n'est pas un effet de bord d'une conversation.

Il devient **un composant architectural à part entière**.
