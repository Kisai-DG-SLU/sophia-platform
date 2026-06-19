# Automation Deterministe : Separation des Moteurs

Le module d'**Automation Deterministe** definit la separation stricte entre l'orchestration cognitive, qui releve des agents d'IA, et l'automatisation des processus, qui releve de moteurs deterministes.

L'objectif est de ne pas confier a un systeme probabiliste (un modele de langage) l'execution de processus metier qui necessitent une fiabilite absolue.

---

## Probleme

Les modeles de langage sont des systemes probabilistes. Meme avec un taux de reussite eleve, ils conservent une probabilite non nulle d'erreur, de hors-sujet ou d'hallucination.

Pour des taches de nature creative ou exploratoire, cette variabilite est acceptable. Pour des processus metier reproductibles (envoi de notifications, mise a jour de bases, declenchement de flux de validation), elle ne l'est pas.

Confier l'automatisation de processus a un agent d'IA revient a introduire de l'incertitude la ou l'organisation attend de la certitude.

---

## Principe

SophIA separe strictement deux types d'execution :

**L'orchestration cognitive**, assuree par les agents du Pantheon Agentique. Elle est basee sur des modeles de langage et gere les taches qui necessitent raisonnement, adaptation et comprehension contextuelle. Son resultat est probabiliste et soumis a validation.

**L'automatisation deterministe**, assuree par un moteur de workflows. Elle execute des processus definis, immuables et reproductibles. Son resultat est binaire : le processus s'execute correctement ou echoue avec une cause identifiable.

Un agent peut declencher un workflow deterministe, mais il n'en controle pas l'execution. Le workflow s'execute selon ses regles internes, sans intervention du modele.

---

## Fonctionnement

### Definition des workflows

Les workflows sont definis de maniere explicite, via un langage de programmation visuelle ou une configuration codee en dur. Chaque workflow precise :

- les evenements declencheurs
- les etapes d'execution
- les conditions de branchement
- les actions en cas d'erreur
- les notifications et journalisations

### Execution

L'execution d'un workflow est entierement deterministe :

- les etapes s'enchainent dans l'ordre defini
- les conditions sont evaluees par des operateurs logiques, pas par un modele
- les actions sont executees par des connecteurs predefinis
- l'echec d'une etape interrompt le workflow et declenche la procedure d'erreur definie

### Interaction avec les agents

Un agent peut declencher un workflow par l'intermediaire de l'orchestrateur. La demande est transmise au moteur d'automatisation, qui l'execute sans intervention supplementaire du modele. L'agent recoit le resultat une fois l'execution terminee.

L'inverse est egalement possible : un workflow peut, a une etape definie, solliciter un agent pour une tache de raisonnement avant de poursuivre son execution deterministe.

---

## Position dans l'architecture

Le moteur d'automatisation opere dans un namespace dedie, isole des namespaces d'inference et de memoire. Il est accessible depuis `sophia-core` via une interface securisee.

Technologies possibles : n8n, Node-RED, StackStorm, Temporal, ou tout moteur de workflows repondant aux exigences d'isolation et de determinisme.

---

## Objectif

Garantir que les processus metier reproductibles sont executes de maniere fiable et previsible, independamment de l'etat ou de la performance des modeles d'IA. L'automatisation deterministe et l'orchestration cognitive sont complementaires : la premiere assure la fiabilite des flux, la seconde apporte l'intelligence la ou elle est necessaire.
