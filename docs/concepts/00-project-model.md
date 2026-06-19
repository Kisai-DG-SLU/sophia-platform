# Project Model

Le **Project Model** definit la maniere dont SophIA structure et identifie les unites de travail.

Dans SophIA, tout est considere comme un projet. Cela inclut par exemple un projet de developpement logiciel, une etude de recherche, une activite professionnelle, un objectif personnel ou une initiative strategique.

Le modele projet permet de donner une structure commune a ces activites.

---

## Principe

Un projet SophIA est defini par trois elements distincts :

- **Brain**
- **Repository**
- **Workspace**

Ces trois elements ont des roles differents et ne doivent jamais etre confondus.

---

## Brain

Le **Brain** contient la memoire et la structure intellectuelle du projet. Il est stocke dans un depot dedie.

Le Brain contient generalement :

- les specifications (`specs`)
- la configuration du projet
- la memoire durable (`_memory`)
- les decisions d'architecture

Le Brain est la source de verite documentaire. Il ne contient jamais de code execute.

---

## Repository

Le **Repository** contient les artefacts de travail : code source, notebooks, jeux de donnees, documents generes.

Le repository correspond generalement a un depot Git. Il represente le livrable du projet.

---

## Workspace

Le **Workspace** est l'environnement d'execution temporaire. Il est ephemere, reproductible et isole.

Il peut etre un repertoire local, un environnement sandbox ou un pod Kubernetes. Le workspace peut etre detruit et recree sans perte d'information.

---

## Structure minimale d'un projet

Un projet SophIA contient au minimum :

```
project.yaml
_config/
_memory/
specs/
```

Le fichier `project.yaml` sert de manifeste du projet. Il permet a l'orchestrateur d'identifier l'identite du projet, son Brain, son repository et son agent par defaut.

---

## Identite du projet

Chaque projet possede un identifiant unique. Exemple :

```
organization/project_10/component_name
```

Cet identifiant permet de retrouver les ressources associees, de resoudre le Brain et de localiser le repository.

---

## Agents et projets

Les agents operent toujours dans le contexte d'un projet. Ils peuvent lire les specifications, modifier le repository et executer des taches dans le workspace.

Le projet constitue l'unite de travail fondamentale du systeme.

---

## Objectif

Le Project Model permet de structurer les activites, separer memoire et execution, rendre les projets reproductibles et faciliter le travail des agents.

Dans SophIA, le projet devient l'element central qui relie la connaissance, l'execution, les outils et les objectifs.
