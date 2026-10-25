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

## Recettes

Chaque dossier décrit un composant : ses choix et leurs raisons, ses gabarits (variables `${…}`), ses Secrets (noms et clés, jamais de valeur), une procédure pas à pas avec les contrôles attendus, et le retour arrière.

| Dossier | Contenu |
|---|---|
| [`okd/host/wireguard/`](okd/host/wireguard/) | accès par VPN seulement, filtre du nœud et son garde-fou |
| [`okd/cluster/`](okd/cluster/) | classes de priorité et quotas par namespace |
| [`okd/monitoring/`](okd/monitoring/) | observabilité minimale : métriques, règles d'alerte, exporteur du nœud |
| [`okd/core/`](okd/core/) | routeur de modèles, base relationnelle, bus d'événements, workflows durables, répartiteur |
| [`okd/inference/`](okd/inference/) | modèles locaux : texte et vision sur GPU, voix et images sur CPU |
| [`okd/memory/`](okd/memory/) | embedding et schéma de la mémoire vectorielle |
| [`okd/storage/`](okd/storage/) | stockage objet S3 commun |
| [`okd/identity/`](okd/identity/), [`okd/ingress/`](okd/ingress/) | identité et SSO, certificats |
| [`okd/apps/`](okd/apps/), [`okd/skills/`](okd/skills/), [`okd/dmz/`](okd/dmz/) | interface, outils MCP locaux, sas web |
| [`okd/hermes-system/`](okd/hermes-system/) | agents du panthéon et assistant de code |

## Méthode d'application

La même pour toutes les recettes ; son but est de ne jamais casser ce qui tourne :

1. **Un ordre des étapes écrit d'avance**, par ordre d'impact : d'abord ce qui n'a aucun effet (classes, quotas, Secrets, objets nouveaux), puis ce qui ne touche aucun utilisateur, enfin ce qui redémarre un service utilisé, au moment où personne ne s'en sert. Un manifeste qui dépend d'un prérequis attend ce prérequis, pour ne redémarrer un pod qu'une fois.
2. **Un `oc diff` relu en entier avant chaque `oc apply`.** Il ne doit montrer que le changement voulu ; un écart sans rapport signale une dérive entre le dépôt et le cluster, à réaligner d'abord.
3. **Une étape à la fois**, chacune avec son contrôle attendu, relu après l'application, et son retour arrière prêt avant.
4. **Le vrai chemin** pour vérifier : la Route, le SSO, le routeur de modèles, l'image construite, et pas seulement le code.
5. **Les Secrets par l'entrée standard** (`printf … | oc create secret generic … --from-env-file=/dev/stdin`), jamais en argument d'une commande, où la liste des processus les montrerait ; aucune valeur n'est affichée.
6. **Un réglage commun s'essaie sur un seul composant** avant les autres.
7. **Aucune suppression implicite** : un objet retiré d'un gabarit se retire du cluster par une étape à part, contrôlée.

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
| sophia-identity  | identité et SSO (Keycloak)                |
| sophia-storage   | stockage objet S3 commun                  |

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
