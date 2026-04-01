# Architecture et Workflow de Développement Assisté (SophIA / OpenCode)

## 1. Philosophie et Vue d'Ensemble
Le module de développement assisté de SophIA repose sur l'utilisation d'**OpenCode** au sein de Pods éphémères sur OKD 4.21. 
L'objectif est de fournir à l'IA un environnement de travail (Station de Travail Pilotée) structuré, sécurisé, et parfaitement interfacé avec les outils locaux (Zed via SSH) et le gestionnaire de versions (Forgejo miroir vers GitHub).

**Principes fondamentaux :**
* **Isolation stricte :** Le code de production et la mémoire de l'IA sont physiquement séparés.
* **Traçabilité maîtrisée :** L'historique Git public (GitHub) est 100% imputable à l'utilisateur (humain), tandis que le travail brut de l'IA reste auditable en interne.
* **Centralisation :** Aucune configuration manuelle par projet. Tout est géré par un Config-Hub central.

---

## 2. Architecture du Pod Éphémère (Le Triptyque)
Chaque projet lancé génère un Pod OpenCode dédié. Le système de fichiers interne est organisé en trois zones de montage distinctes pour contraindre le périmètre de l'IA :

| Chemin Interne | Droits | Source Git | Rôle & Contenu |
| :--- | :--- | :--- | :--- |
| `/mnt/rules` | **ReadOnly** | `sophia-brain` | **Le Code Civil :** Règles globales, modèles BMAD, prompt système. Inaltérable par l'IA. |
| `/mnt/specs` | **ReadWrite** | `structure-Brain/<projet>` | **La Mémoire :** Spécifications du projet, journal de bord de l'IA, historique des prompts. |
| `/mnt/prod` | **ReadWrite** | `repo-projet-x` | **L'Usine :** Le code source du livrable. Aucune donnée IA ne doit y résider. |

---

## 3. Confinement de l'IA et Sécurité
Pour empêcher l'IA d'écrire sa mémoire ou ses logs de réflexion dans le répertoire de production (`/mnt/prod`), deux verrous invisibles sont mis en place :

1. **Routage via Tools CLI :**
   L'agent IA (interfaçant avec LiteLLM) n'a pas accès aux commandes d'écriture brutes (`echo`, `cat`) avec des chemins relatifs. Il utilise des outils dédiés (ex: `write_code(file, content)` et `write_memory(file, content)`) qui forcent l'écriture dans les chemins absolus respectifs (`/mnt/prod/` et `/mnt/specs/`).
2. **Le filet de sécurité Git (`.git/info/exclude`) :**
   Au démarrage du Pod, le script d'initialisation injecte des règles restrictives (ex: `*.memory`, `*.log`) dans le fichier `.git/info/exclude` du dépôt de prod. Ce fichier agit comme un `.gitignore` mais n'est jamais versionné, bloquant tout commit accidentel de fichiers IA sans polluer le dépôt public.

---

## 4. Accès et Configuration (Le Config-Hub)
Le Pod est un consommateur de ressources. Il hérite de son environnement au démarrage.

* **Environnement Conda/Pixi :** Automatiquement activé via un script `.bashrc_sophia` stocké dans le volume partagé du Config-Hub. L'environnement `sophia-brain` est la norme.
* **Connexion Zed / SSH :** * Un **Secret OKD** injecte la clé publique SSH de l'utilisateur.
  * Un **Service OKD** (`ClusterIP`) attribue une IP interne stable au Pod du projet.
  * Un script local Mac (`sophia-up`, versionné dans `sophia-brain/pc-client`) déploie le Pod et met à jour automatiquement le fichier `~/.ssh/config` du Mac pour permettre une connexion immédiate via Zed.

---

## 5. Le Workflow Git (Identité et CI/CD)
Pour répondre aux exigences de dev et de sauvegarde, la mécanique Git s'articule autour de Forgejo et de ses Actions CI/CD.

### Étape 1 : Développement et Tests (Interne)
1. L'IA (ou l'utilisateur via Zed) travaille dans le `/mnt/prod` sur des branches éphémères (`feat/*`, `fix/*`).
2. Les commits de l'IA utilisent la métadonnée d'identité interne : `Author: SophIA <sophia@local>`.
3. Le push sur Forgejo déclenche un runner (Pixi) qui exécute les tests unitaires.

### Étape 2 : L'Entonnoir de Validation (Le Masque)
1. Si les tests réussissent, une Pull Request automatisée est créée vers la branche `testing`.
2. La fusion de la PR exécute un **Squash & Merge**.
3. **Réécriture de l'auteur :** Lors du Squash, l'identité "SophIA" est écrasée. Le commit résultant sur la branche `testing` est signé exclusivement par : le validateur humain.

### Étape 3 : Production et Mirroring (Externe)
1. La branche `testing` (désormais propre et signée) est testée fonctionnellement par l'utilisateur (via Jupyter Lab ou autre interface).
2. Validation finale via un Fast-Forward merge de `testing` vers `main`.
3. **Miroir GitHub :** Forgejo pousse uniquement les branches `testing` et `main` vers GitHub. L'historique de brouillon de l'IA reste sur l'infrastructure privée.
