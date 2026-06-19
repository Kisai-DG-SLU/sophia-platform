# Architecture et Workflow de Développement Assisté

## 1. Philosophie et Vue d'Ensemble

Le module de développement assisté de SophIA repose sur l'utilisation d'agents de codage (type OpenCode) au sein de pods éphémères sur une plateforme Kubernetes. L'objectif est de fournir à l'IA un environnement de travail structuré, sécurisé, et interfacé avec les outils de développement et le gestionnaire de versions.

**Principes fondamentaux :**

- Isolation stricte entre le code de production et la mémoire de l'IA
- Traçabilité maîtrisée : l'historique Git public est imputable à l'humain, tandis que le travail brut de l'IA reste auditable en interne
- Centralisation de la configuration via un hub dédié

---

## 2. Architecture du Pod Éphémère (Le Triptyque)

Chaque projet lancé génère un pod agent dédié. Le système de fichiers interne est organisé en trois zones de montage distinctes pour contraindre le périmètre de l'IA :

| Chemin Interne | Droits    | Source                           | Rôle |
|:---|:---|:---|:---|
| `$RULES_DIR`   | ReadOnly  | Dépôt central de règles          | Règles globales, modèles, prompts système. Inaltérable par l'IA. |
| `$SPECS_DIR`   | ReadWrite | Dépôt Brain du projet            | Spécifications, journal de bord, historique des prompts. |
| `$PROD_DIR`    | ReadWrite | Dépôt du projet                  | Code source du livrable. Aucune donnée IA persistée. |

---

## 3. Confinement de l'IA et Sécurité

Deux mécanismes empêchent l'IA d'écrire ses artefacts mémoire dans le répertoire de production :

1. **Routage via outils spécialisés.** L'agent n'a pas accès aux commandes d'écriture brutes. Il utilise des fonctions dédiées qui contraignent l'écriture dans les chemins respectifs (`$PROD_DIR` et `$SPECS_DIR`).

2. **Filtre Git local.** Au démarrage du pod, un script d'initialisation injecte des règles d'exclusion (fichiers mémoire, logs) dans la configuration Git locale du dépôt de production, bloquant tout commit accidentel de fichiers IA.

---

## 4. Accès et Configuration

Le pod hérite de son environnement au démarrage via un hub de configuration central :

- **Environnement logiciel :** activé automatiquement au démarrage du pod
- **Connexion sécurisée :** une clé SSH est injectée via un secret Kubernetes ; un service interne attribue une IP stable au pod ; un script côté client met à jour la configuration SSH locale pour une connexion immédiate depuis l'IDE

---

## 5. Workflow Git

Le cycle de développement s'articule autour d'une plateforme Git interne et de son système de CI/CD.

### Développement et Tests (interne)

1. L'agent travaille dans `$PROD_DIR` sur des branches éphémères (`feat/*`, `fix/*`).
2. Les commits de l'agent utilisent une identité interne dédiée.
3. Le push déclenche un runner qui exécute les tests.

### Validation et masquage des identités

1. Si les tests réussissent, une demande de fusion automatisée est créée vers la branche de validation.
2. La fusion utilise un squash qui réécrit l'auteur : l'identité de l'agent est remplacée par celle du validateur humain.

### Production et miroir externe

1. La branche de validation est testée fonctionnellement par l'utilisateur.
2. Une validation finale fusionne vers la branche principale.
3. Seules les branches validées sont poussées vers le miroir public. L'historique de travail de l'IA reste sur l'infrastructure privée.
