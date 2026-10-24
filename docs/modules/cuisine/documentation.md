# Module Cuisine — documentation

## Ce que fait le module

- **Catalogue** amorcé depuis un ancien tableur du foyer (78 recettes : 40 à proposer, 38 en archive), fiche avec nombre de convives réglable. Par défaut, seules les recettes « à proposer » et **de saison** sont montrées (21 jours de tolérance aux bords de saison).
- **Deux notes** : celle de la recette (estimée par le modèle ou reprise de la source) et celle **du foyer**, qui seule décide de la rotation — une recette revient si elle a 8/10 ou plus et n'a pas été faite depuis 6 semaines ; sous 6/10, elle est exclue ; au plus 3 créneaux de rotation par semaine.
- **Planning par personne** : plusieurs plats par créneau, plat industriel ou hors catalogue, repas pris à l'extérieur (cantine), mode vacances, menus des enfants en entrée / plat / légume. Un repas devient « passé » après 14 h ou 22 h.
- **Génération de recettes sous règles** : une réserve permanente de nouveautés (28), une génération « avec ce que j'ai », 60 essais par jour au plus ; les recettes inspirées du web citent leurs sources.
- **Aliments bannis** ou **dévalués** (un poids qui s'efface en 8 semaines), score de satiété, tris.
- **Repas de fête** : menu par service, propositions, courses.
- **Courses** agrégées par rayon, coches partagées entre les membres du foyer, historique annulable ; un onglet transmet la liste validée au [module Courses](../courses/README.md), qui remplit le panier d'un drive.
- **Import** d'une recette depuis un lien ou un texte collé : le modèle la met en fiche, des règles la contrôlent, le foyer relit un aperçu avant l'enregistrement.
- **Photo du plat** générée localement par l'outil MCP `image` de la plateforme.
- **Dans la discussion** : « on mange quoi ce soir ? » est répondu par l'assistant, à partir du planning.

Prévu : une table des ingrédients (saison par mois, prix, calories) pour **calculer** coût, calories et saison au lieu de les estimer.

## Architecture

```
navigateur ─VPN─→ routeur ─→ [ oauth2-proxy │ application ]   (namespace des applications)
                                   │            │  base dédiée ─→ PostgreSQL partagé
                                   │            │  LiteLLM (sophia-local, JSON strict)
                                   │            │  outil MCP image (sophia-skills)
                                   │            │  sas web (recherche, lecture de pages)
                                   │            └─ MCP du module Courses (liste fermée d'outils)
interface de discussion ─MCP (lecture)─→ application
module Courses ─────────MCP (écriture limitée)─→ application
```

| Élément | Choix |
|---|---|
| Pod | deux conteneurs : **oauth2-proxy** (SSO Keycloak, PKCE) et l'application (FastAPI, gabarits Jinja2, htmx), qui n'écoute que sur `127.0.0.1` ; l'identité arrive par l'en-tête posé par le proxy, une requête sans cet en-tête est refusée |
| Image | UBI minimal, Python 3.12, non root, rien d'écrit sur disque, `seccomp` `RuntimeDefault`, capacités retirées |
| Données | une **base dédiée** dans le PostgreSQL partagé, rôle propre, schéma créé au démarrage ; photos stockées en base ; aucun volume persistant |
| Variabilité | calculée sur des champs d'identité de la recette (cuisson, ingrédient principal, accompagnements), sans base vectorielle |
| Accès | deux groupes du realm : accès complet, comptes protégés (lecture seule, jamais de génération de photo) |
| Délais | 300 s au proxy et à la Route : le modèle local met plusieurs dizaines de secondes |
| Réseau | liste fermée : entrée du routeur vers le proxy, de l'interface vers le MCP de lecture, du module Courses vers le MCP d'écriture ; sortie vers le routeur de modèles, le fournisseur d'identité, PostgreSQL, l'outil `image`, le sas web, le module Courses, le DNS |
| Build | BuildConfig Docker depuis la forge interne, déclencheur d'image sur le Deployment ; un CronJob à droits minimaux lance un build par nouveau commit |

### Serveurs MCP exposés

| Serveur | Ouvert à | Outils | Droits |
|---|---|---|---|
| lecture | l'interface de discussion seule | `menu_du_jour`, `menu_semaine`, `recette`, `liste_courses` | lecture ; l'identité est **injectée par l'interface** (`sophia/injecte`), seuls les membres du foyer sont servis ; aucune donnée de santé ni réglage n'en sort |
| drive | le module Courses seul | `listes_drive`, `marquer_commandee` | lire les listes validées, marquer une liste commandée |

En sens inverse, le module appelle le MCP du module Courses avec une **liste fermée d'outils** et des arguments qu'il construit lui-même.

### Usages du modèle

Tous par le routeur de modèles, avec une clé virtuelle propre et l'identité de la personne (`x-litellm-end-user-id`), en **JSON strict** :

| Usage | Température |
|---|---|
| génération d'une recette | 0,9 |
| import d'une recette (mise en fiche) | 0,1 |
| consigne courte en anglais pour la photo, longueur contrôlée | — |

## Règles : le modèle propose, les règles décident

Une recette générée est un JSON ; un validateur déterministe tranche :

- schéma, unités, mode de cuisson, protéine, saison, **un seul** ingrédient principal ;
- aliments interdits, comparés **en mots entiers** (un interdit ne déclenche pas sur un mot qui le contient) ;
- plafonds : 450 à 650 kcal, préparation ≤ 20 min, total ≤ 40 min, ≤ 5 € par portion, note estimée ≥ 6,5 ;
- titre inédit, au plus 7 recettes par protéine, et **différente d'au moins 2 critères sur 4** de chaque recette existante ;
- aliments dévalués pris en compte.

Un rejet repart au modèle **avec ses motifs**, 3 essais au plus ; chaque essai est journalisé (acceptée, rejetée, erreur, durée).

Autres contrôles autour des sorties du modèle :

- **recherche web** : la requête est construite par des règles, jamais par le modèle ; au plus 2 pages lues, tronquées à 2 500 caractères, sur une **liste blanche de sites de recettes**, par le sas web (seule sortie vers Internet, indirecte) ; sans sas, la génération continue sans inspiration ;
- les **sources citées** doivent être des pages réellement lues ;
- à l'**import**, un ingrédient absent de la source est écarté et signalé « à vérifier » ;
- les interdits ne visent que les recettes **inventées**, pas les plats saisis ni les imports.

**Données de santé** : jamais versionnées ni envoyées au modèle ; seules des contraintes nutritionnelles générales passent.

## Mesures

- Premier essai réel sur le modèle local : 3 recettes acceptées en 5 min.
- Photo d'un plat : ≈ 30 s (CPU) ; import d'une recette : 1 à 2 min.
- Application : 20 m CPU et 96 Mi demandés, 500 m et 256 Mi au plus.
- Tests : pytest contre un vrai PostgreSQL, et un faux module Courses.

## Leçons

- Le prototype précédent **confiait les contrôles au modèle** : interdits présents, plafonds dépassés, vocabulaire qui dérive. Ce qui marche : le modèle propose, des règles décident, et le rejet motivé repart au modèle.
- Une liste d'interdits comparée en sous-chaîne donne de faux positifs : comparer en mots entiers.
- L'amorce du catalogue est **versionnée** et réappliquée par numéro de version : une erreur de colonne dans le script de normalisation s'est corrigée en rejouant une version.
- Un webhook de la forge vers l'API du cluster était bloqué par le pare-feu de sortie (adresses privées refusées) : remplacé par un CronJob à droits minimaux, un build par nouveau commit, jamais de reconstruction en boucle d'un build en échec.
- Les sites de recettes rendus en JavaScript ne se lisent pas sans navigateur : repli par texte collé ; piste, lire leurs données structurées (`ld+json`).
