# Module École — documentation

## Ce que fait le module

- **Parcours** par niveau (du primaire à la fin du collège) et par matière : leçons, travaux pratiques à la maison, défis, étoiles et badges ; ≈ 800 activités publiées aujourd'hui.
- **Entraînements de calcul mental** sur une liste de calculs écrite dans le contenu (`faits:`), avec la même répétition espacée, le même chronomètre et la reprise des ratés que les tables : 17 entraînements, 314 calculs, qui reprennent les méthodes et les exemples de chaque fiche. Pas de générateur aléatoire, pour rester fidèle aux nombres de chaque leçon.
- **Figures de géométrie** : 29 figures SVG dans 15 leçons, insérées après le passage qu'elles illustrent, sans modifier le texte.
- **Mode relecture** pour l'administrateur : tout est ouvert, rien n'est compté, un bandeau le dit dans chaque lieu ; un enfant garde ses verrous. Ce n'est pas une barrière de sécurité (tout le contenu est déjà dans la page), mais le moyen de valider ce qu'on demande de valider.
- **Avatar** commun à la discussion et à l'école (un dessin, ou une petite photo).
- **Journal de progression** de l'enfant, et un **livret en lecture seule** pour les parents.
- **Fiches d'exercices** (énoncé, corrigé, auto-évaluation) et vidéos en lien.
- **Carnet de notes** de l'école réelle, recopié par l'enfant : notes, bulletins, moyennes, import d'un tableur, courbes ; au primaire, des **compétences** (non acquis, partiellement, acquis, dépassé), sans note ni comparaison.
- **« Demander à Sophia »** : un indice sur l'activité en cours, et l'ouverture de l'école depuis la discussion (bouton dans la réponse, lien construit par le serveur).
- **Dictée sur ardoise** et **fiche de lecture** photographiées, lues par le modèle local (vision).
- Outil `carnet_scolaire` dans la discussion : il ne lit que le journal de l'enfant qui parle ; le verdict (félicitations, encouragements…) est **calculé par le serveur**.

- **Publication des contenus sans reconstruction d'image** : le conteneur `contenus` synchronise les dépôts en lecture seule chaque minute et garde la version en ligne si la nouvelle est invalide (incident corrigé, voir les leçons).

Prévu : l'école sur sa propre adresse, hors de l'origine de la discussion (voir [l'interface](../../../deploy/okd/apps/chat-interface/README.md)), une touche virgule pour les calculs à décimaux et à fractions, version de partage avec une voix de synthèse libre enregistrée, outils MCP de progression et d'ouverture, carnet servi en MCP avec un jeton signé limité à l'enfant.

## Architecture

```
navigateur ─VPN─→ interface de discussion (SSO) ── /ecole/ ──→ pod école (namespace des applications)
                                                                 ├ site      : nginx, GET/HEAD seulement
                                                                 └ contenus  : synchronisation Git chaque minute
                                                                                 → bascule atomique d'un lien « current »
API des discussions : progression, carnet, photos (base de l'interface) ; indices et lecture des photos par sophia-local
```

| Élément | Choix |
|---|---|
| Pod | une image, **deux conteneurs**, ni Route ni connexion propre : seuls les pods de l'interface le joignent (NetworkPolicy) |
| `site` | nginx sans privilèges, `GET`/`HEAD` seulement, en-têtes stricts ; sert le moteur et un **contenu de secours intégré à l'image** |
| `contenus` | récupère en SSH (clé de déploiement en lecture seule, seul secret du pod) un dépôt de contenus public et un privé facultatif, **vérifie**, reconstruit, puis bascule d'un coup un lien `current` dans un volume partagé ; contenu invalide ou dépôt injoignable : la version en ligne reste, l'erreur est publiée dans un fichier d'état |
| Build | Docker en deux étapes (UBI 9, Node.js) ; seul un changement du **moteur** demande un build, les contenus passent par Git |
| Identité | même oauth2-proxy et même Keycloak que la discussion ; rôles : administrateur, responsables (parents), protégés (enfants) |
| Données | progression et carnet dans la base de l'interface (table d'événements, profil) ; personne n'écrit dans le journal d'un autre |
| Ouverture depuis la discussion | l'analyse d'intention (modèle, schéma JSON) reconnaît « école » ; une **politique déterministe** autorise l'action `ouvrir_ecole` ; le lien est construit par le serveur à partir de l'index de l'école, le navigateur vérifie sa forme |

### Format des contenus

`contenus/<matière>/<niveau>/<module>/`, un fichier YAML par module et par niveau. Types d'activités : leçon (Markdown avec en-tête YAML), TP, défi QCM, « clique sur le mot », « je complète », dictée sur ardoise, fiche de lecture. Champs obligatoires : `id`, `type`, `titre`, `notions`, `source`, `licence`, `redistribuable`.

Le build **refuse** tout contenu invalide : bonne réponse absente des choix, notion inconnue, licence manquante. Le dépôt privé ajoute des modules sans rien remplacer ; seul ce qui est marqué `redistribuable: true` entre dans la version de partage, qui ne garde que des liens vers le reste.

## Règles : le modèle formule, le serveur décide

- Le serveur calcule les verdicts et les moyennes ; le modèle ne fait que **formuler**.
- **« Un indice, jamais la réponse », imposé deux fois** : l'activité est lue côté serveur depuis son identifiant (jamais depuis la requête), et le modèle ne reçoit pas la réponse quand il n'en a pas besoin ; puis un contrôle déterministe vérifie que sa sortie ne contient pas la réponse (choix, résultat en chiffres ou en lettres, mot dicté) — sinon, l'indice écrit dans l'activité ou un indice générique.
- **Vision** : le modèle recopie l'ardoise **sans connaître les mots attendus**, pour ne pas « corriger » l'enfant à sa place ; sortie en schéma JSON, vérifiée ; en cas d'échec, l'enfant saisit à la main.
- **Protection des enfants** : aucune comparaison entre enfants, carnet privé ; photos effacées dès la correction par un parent, et au plus tard 7 jours après l'envoi ; sécurité des travaux pratiques écrite dans les contenus (piles de 4,5 V au plus, ni prise, ni flamme, ni produit ménager, un adulte présent pour tout ce qui chauffe).

## Mesures

- ≈ 800 activités publiées (806) ; un module de physique-chimie relu en entier : 19 leçons, 13 TP, 19 défis, ≈ 120 questions vérifiées contre des corrigés de référence, aucune contradiction.
- 91 tests automatisés (contenus, build, progression, synchronisation, parcours dans le navigateur, relecture).
- Pod : nginx limité à 64 Mi, synchronisation à 256 Mi.

## Leçons

- **PID 1 et processus zombies** : depuis git 2.47, chaque `git fetch` lance `git maintenance --auto --detach`. Le processus détaché est rattaché au PID 1 du conteneur — ici un processus Node.js, qui ne récolte pas les orphelins. Un zombie par synchronisation, jusqu'à la limite de 4 096 PID : « unable to fork », la synchronisation s'arrête (la version en ligne, elle, reste servie). Correctif à la source : `git -c maintenance.autoDetach=false -c gc.autoDetach=false`, la maintenance se fait alors sur place, et un test qui vérifie l'absence de `--detach` dans la trace de git (il échoue sans le correctif). Défense en profondeur proposée, pas encore appliquée : `shareProcessNamespace: true`, pour que le conteneur `pause` soit PID 1 et récolte les orphelins. Un simple redémarrage ne fait que repousser l'incident.
- **Bascule atomique et contenu de secours** : une synchronisation en panne ne casse jamais le site.
- **UID arbitraire d'OpenShift** : `ssh` exige une entrée dans `/etc/passwd` — d'où `chmod g+w /etc/passwd` dans l'image et des chemins donnés au groupe 0.
- **Séparer moteur et contenus** : les contenus évoluent par Git, vérifiés avant publication, sans reconstruire l'image.
- **Le moteur avant les contenus** : un contenu qui utilise un nouveau champ ne se publie qu'après le build du moteur qui le comprend ; sinon la synchronisation refuse tout le contenu (« opération inconnue ») et ne publie plus rien, la version en ligne restant servie.
- **Une image écrite doit devenir une image** : un crochet non refermé dans le texte (« [EF) ») faisait d'une figure un lien. Le build refuse désormais une image de leçon qui ne devient pas une `<img>`.
- **L'axe de symétrie se trace après la forme** remplie, sinon elle le cache ; avant les petits codages, que ses tirets cacheraient.
- **Droits de redistribution portés par chaque ressource** : la version de partage se construit d'elle-même, sans tri à la main.
