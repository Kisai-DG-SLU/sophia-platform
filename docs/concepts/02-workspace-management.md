# Workspace Management

Le **Workspace Management** definit la maniere dont SophIA gere les environnements de travail des agents et des utilisateurs.

L'objectif est de garantir la reproductibilite, l'isolation et la tracabilite.

---

## Probleme

Dans les systemes bases sur des agents, les environnements de travail peuvent devenir chaotiques : dependances implicites, chemins locaux dependants de la machine, melange entre memoire, code et execution.

Cela rend les systemes difficiles a maintenir et a reproduire.

---

## Principe

SophIA separe strictement trois elements :

### Brain

Le **Brain** contient la memoire et les specifications du projet.

Exemples :

- depot Brain d'un projet de developpement
- depot Brain d'un projet d'architecture

Contenu :

- specifications
- decisions d'architecture
- configuration du projet

---

### Repository

Le repository contient le travail reel : code, notebooks, ressources.

---

### Workspace

Le workspace est un environnement d'execution temporaire, ephemere, isole et reproductible. Il peut etre local, dans un pod Kubernetes ou dans un environnement sandbox.

---

## Regle fondamentale

Le workspace n'est jamais la source de verite. La source de verite est toujours le Brain (memoire) et le repository (code).

---

## Integration avec les agents

Les agents operent dans ces workspaces. Ils peuvent lire les specifications dans le Brain, modifier le repository et executer des taches dans le workspace.

---

## Objectif

Garantir que les projets restent reproductibles, que les environnements restent propres et que les agents ne dependent pas d'un etat local cache.
