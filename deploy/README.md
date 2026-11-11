# SOPHIA : Exemple de Déploiement

Ce répertoire contient un exemple de déploiement de l'architecture SophIA (actuellement sur **OKD**, la distribution Kubernetes d'OpenShift).

La configuration fournie correspond à l'environnement de Proof of Concept utilisé lors du développement initial du projet.

Elle démontre comment les différents composants de l'architecture SophIA peuvent être déployés sur une plateforme Kubernetes.

---

## Objectif

Ce répertoire a pour but de :

- fournir une disposition de déploiement de référence
- illustrer comment les composants de la plateforme sont organisés
- documenter l'architecture des namespaces
- permettre l'expérimentation et la reproduction locale du système
- dimensionner et préparer le stockage persistant : voir [stockage persistant](stockage-persistant.md)

Cette configuration n'est pas destinée à être une distribution prête pour la production. Elle sert d'exemple d'infrastructure utilisé pour l'expérimentation et la documentation.

---

## Plateforme

L'environnement de déploiement de référence utilise :

- OKD (OpenShift Kubernetes Distribution)
- services conteneurisés
- isolation par namespaces
- segmentation réseau via NetworkPolicies Kubernetes

La structure de déploiement suit les principes architecturaux décrits dans `docs/architecture.md`.

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
| [`okd/memory/`](okd/memory/) | embedding et schéma de la mémoire vectorielle ; [service mémoire](okd/memory/memoire/README.md) (versions, validation, droits, audit, extraction isolée) |
| [`okd/storage/`](okd/storage/) | stockage objet S3 commun |
| [`okd/office/`](okd/office/) | bureautique : fichiers de chacun et édition des documents (La Suite Drive, Collabora) |
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

## Modèle de namespaces

Le déploiement exemple utilise une architecture de namespaces segmentée. Les namespaces typiques incluent :

| Namespace        | Rôle                                      |
|------------------|-------------------------------------------|
| sophia-core      | services d'orchestration                  |
| sophia-inference | exécution locale de modèles               |
| sophia-memory    | base vectorielle                          |
| sophia-git       | dépôts de projets                         |
| sophia-skills    | outils MCP                                |
| sophia-dmz       | acquisition web contrôlée                 |
| sophia-sandbox   | environnements de développement           |
| sophia-test      | environnements de validation              |
| sophia-apps      | modules                                   |
| sophia-interface | interface de discussion                   |
| sophia-workflow  | outil de visualisation                    |
| sophia-workspace | bureautique                               |
| sophia-messagerie | chat permanent (Matrix), en recette      |
| sophia-visio     | visioconférence (Jitsi Meet), en recette  |
| sophia-skills-build | builds des outils MCP, sans compte d'agent |
| namespace des agents | panthéon et assistant de code         |
| sophia-identity  | identité et SSO (Keycloak)                |
| sophia-storage   | stockage objet S3 commun                  |

Cette disposition illustre l'architecture Hub and Spoke utilisée par la plateforme.

---

## Remarques importantes

Cet exemple de déploiement reflète la configuration utilisée pour l'environnement d'expérimentation de l'auteur. Il peut inclure des politiques de sécurité simplifiées, des hypothèses d'infrastructure locale et des configurations spécifiques au développement.

Avant tout déploiement réel, les organisations doivent adapter la configuration à leur propre infrastructure et exigences de sécurité.

---

## Améliorations futures

À l'avenir, la couche de déploiement pourra inclure :

- des charts Helm reproductibles
- des packages Kustomize
- un bootstrap automatisé de cluster
- des architectures de référence pour différentes échelles de déploiement

---

## Statut

Expérimental.

Ce répertoire documente l'infrastructure utilisée pour valider les concepts architecturaux décrits dans ce dépôt.
