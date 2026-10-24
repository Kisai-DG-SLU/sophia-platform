# Project Model

Le **Project Model** définit la manière dont SophIA structure et identifie les unités de travail.

Dans SophIA, tout est considéré comme un projet. Cela inclut par exemple un projet de développement logiciel, une étude de recherche, une activité professionnelle, un objectif personnel ou une initiative stratégique.

Le modèle projet permet de donner une structure commune à ces activités.

---

## Principe

Un projet SophIA est défini par trois éléments distincts :

- **Brain**
- **Repository**
- **Workspace**

Ces trois éléments ont des rôles différents et ne doivent jamais être confondus.

---

## Brain

Le **Brain** contient la mémoire et la structure intellectuelle du projet. Il est stocké dans un dépôt dédié.

Le Brain contient généralement :

- les spécifications (`specs`)
- la configuration du projet
- la mémoire durable (`_memory`)
- les décisions d'architecture

Le Brain est la source de vérité documentaire. Il ne contient jamais de code exécuté.

---

## Repository

Le **Repository** contient les artefacts de travail : code source, notebooks, jeux de données, documents générés.

Le repository correspond généralement à un dépôt Git. Il représente le livrable du projet.

---

## Workspace

Le **Workspace** est l'environnement d'exécution temporaire. Il est éphémère, reproductible et isolé.

Il peut être un répertoire local, un environnement sandbox ou un pod Kubernetes. Le workspace peut être détruit et recréé sans perte d'information.

---

## Structure minimale d'un projet

Un projet SophIA contient au minimum :

```
project.yaml
_config/
_memory/
specs/
```

Le fichier `project.yaml` sert de manifeste du projet. Il permet à l'orchestrateur d'identifier l'identité du projet, son Brain, son repository et son agent par défaut.

---

## Identité du projet

Chaque projet possède un identifiant unique. Exemple :

```
organization/project_10/component_name
```

Cet identifiant permet de retrouver les ressources associées, de résoudre le Brain et de localiser le repository.

---

## Agents et projets

Les agents opèrent toujours dans le contexte d'un projet. Ils peuvent lire les spécifications, modifier le repository et exécuter des tâches dans le workspace.

Le projet constitue l'unité de travail fondamentale du système.

---

## Objectif

Le Project Model permet de structurer les activités, séparer mémoire et exécution, rendre les projets reproductibles et faciliter le travail des agents.

Dans SophIA, le projet devient l'élément central qui relie la connaissance, l'exécution, les outils et les objectifs.
