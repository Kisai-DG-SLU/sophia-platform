# SOPHIA : Exemple de Deploiement

Ce repertoire contient un exemple de deploiement de l'architecture SophIA (actuellement sur **OKD**, la distribution Kubernetes d'OpenShift).

La configuration fournie correspond a l'environnement de Proof of Concept utilise lors du developpement initial du projet.

Elle demontre comment les differents composants de l'architecture SophIA peuvent etre deployes sur une plateforme Kubernetes.

---

## Objectif

Ce repertoire a pour but de :

- fournir une disposition de deploiement de reference
- illustrer comment les composants de la plateforme sont organises
- documenter l'architecture des namespaces
- permettre l'experimentation et la reproduction locale du systeme
- dimensionner et preparer le stockage persistant : voir [stockage persistant](stockage-persistant.md)

Cette configuration n'est pas destinee a etre une distribution prete pour la production. Elle sert d'exemple d'infrastructure utilise pour l'experimentation et la documentation.

---

## Plateforme

L'environnement de deploiement de reference utilise :

- OKD (OpenShift Kubernetes Distribution)
- services conteneurises
- isolation par namespaces
- segmentation reseau via NetworkPolicies Kubernetes

La structure de deploiement suit les principes architecturaux decrits dans `docs/architecture.md`.

---

## Modele de namespaces

Le deploiement exemple utilise une architecture de namespaces segmentee. Les namespaces typiques incluent :

| Namespace        | Role                                      |
|------------------|-------------------------------------------|
| sophia-core      | services d'orchestration                  |
| sophia-inference | execution locale de modeles               |
| sophia-memory    | base vectorielle                          |
| sophia-git       | depots de projets                         |
| sophia-skills    | outils MCP                                |
| sophia-dmz       | acquisition web controlee                 |
| sophia-sandbox   | environnements de developpement           |
| sophia-test      | environnements de validation              |
| sophia-apps      | interfaces utilisateur                    |

Cette disposition illustre l'architecture Hub and Spoke utilisee par la plateforme.

---

## Remarques importantes

Cet exemple de deploiement reflete la configuration utilisee pour l'environnement d'experimentation de l'auteur. Il peut inclure des politiques de securite simplifiees, des hypotheses d'infrastructure locale et des configurations specifiques au developpement.

Avant tout deploiement reel, les organisations doivent adapter la configuration a leur propre infrastructure et exigences de securite.

---

## Ameliorations futures

A l'avenir, la couche de deploiement pourra inclure :

- des charts Helm reproductibles
- des packages Kustomize
- un bootstrap automatise de cluster
- des architectures de reference pour differentes echelles de deploiement

---

## Statut

Experimental.

Ce repertoire documente l'infrastructure utilisee pour valider les concepts architecturaux decrits dans ce depot.
