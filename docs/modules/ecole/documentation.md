# Module École — documentation

## Ce que fait le module

- **Parcours** par niveau (du primaire à la fin du collège) et par matière : leçons, travaux pratiques à la maison, défis, étoiles et badges ; ≈ 800 activités publiées aujourd'hui.
- **Entraînements de calcul mental** sur une liste de calculs écrite dans le contenu (`faits:`), avec la même répétition espacée, le même chronomètre et la reprise des ratés que les tables : 17 entraînements, 314 calculs, qui reprennent les méthodes et les exemples de chaque fiche. Pas de générateur aléatoire, pour rester fidèle aux nombres de chaque leçon.
- **Figures de géométrie** : 29 figures SVG dans 15 leçons, insérées après le passage qu'elles illustrent, sans modifier le texte.
- **Mode relecture** pour l'administrateur : tout est ouvert, rien n'est compté, un bandeau le dit dans chaque lieu ; un enfant garde ses verrous. Ce n'est pas une barrière de sécurité (tout le contenu est déjà dans la page), mais le moyen de valider ce qu'on demande de valider.
- **Avatar** commun à la discussion et à l'école (un dessin, ou une petite photo) : le dessin choisi est rangé en image réduite dans le profil de la discussion, comme une photo, et les profils existants ont été migrés ; l'école garde le catalogue des dessins. L'ancien chemin `/ecole/` de la discussion est devenu une redirection vers l'adresse de l'école. L'assistant a dans l'école un avatar qui lui est propre, servi par l'école et suivi par l'avis de nouvelle version.
- **Journal de progression** de l'enfant, et un **livret en lecture seule** pour les parents.
- **Fiches d'exercices** (énoncé, corrigé, auto-évaluation) et vidéos en lien.
- **Carnet de notes** de l'école réelle, recopié par l'enfant : notes, bulletins, moyennes, import d'un tableur, courbes ; au primaire, des **compétences** (non acquis, partiellement, acquis, dépassé), sans note ni comparaison.
- **« Demander à Sophia »** : un indice sur l'activité en cours, et l'ouverture de l'école depuis la discussion (bouton dans la réponse, lien construit par le serveur).
- **Dictée sur ardoise** et **fiche de lecture** photographiées, lues par le modèle local (vision). La dictée est lue par la voix de synthèse locale, avec une phrase d'amorce (« Écris sur ton ardoise : … »), et la photo de l'ardoise est montrée à la vérification ; « Réécouter » demande une nouvelle synthèse. Sur Safari d'iOS, qui ne joue un son que s'il part d'un geste, un seul élément audio sert à toute la voix et il est débloqué pendant le clic. En service, en recette (écoute sur tablette).
- Outil `carnet_scolaire` dans la discussion : il ne lit que le journal de l'enfant qui parle ; le verdict (félicitations, encouragements…) est **calculé par le serveur**.

- **Avis de nouvelle version** : une tablette reste ouverte des jours ; le build écrit une empreinte du moteur (`version.json`, servi sans cache) et chaque synchronisation une empreinte du contenu. La page compare au chargement et au retour sur l'onglet, et affiche un bandeau « Recharger », jamais pendant un exercice ou une dictée, jamais de rechargement d'elle-même. Une leçon publiée sans build déclenche aussi l'avis.
- **Navigateurs anciens** (Safari 15.4 et plus) : avant toute écriture, le build analyse le moteur en ES2021 et refuse une liste d'API et de règles CSS absentes de Safari 15 ; un moteur refusé fait échouer le build sans effacer la version construite, et l'image en service reste.
- **Publication des contenus sans reconstruction d'image** : le conteneur `contenus` synchronise les dépôts en lecture seule chaque minute et garde la version en ligne si la nouvelle est invalide (incident corrigé, voir les leçons).

Prévu : une touche virgule pour les calculs à décimaux et à fractions, version de partage avec une voix de synthèse libre enregistrée, outils MCP de progression et d'ouverture, carnet servi en MCP avec un jeton signé limité à l'enfant.

## Architecture

```
navigateur ─VPN─→ adresse de l'école (Route, TLS) ──→ pod école (namespace des applications)
                                                       ├ oauth2-proxy : connexion propre (client SSO de l'école, sans les invités)
                                                       ├ site         : nginx, GET/HEAD seulement
                                                       └ contenus     : synchronisation Git chaque minute
                                                                          → bascule atomique d'un lien « current »
        └── appels de l'école ──→ API des discussions, préfixe /api/store/school/ seulement (CORS pour l'origine exacte de l'école)
            progression, carnet, photos (base de l'interface) ; indices, lecture des photos et voix par les modèles locaux
```

| Élément | Choix |
|---|---|
| Pod | une image, **trois conteneurs** (connexion, site, contenus), une Route vers son oauth2-proxy ; le Service interne n'est joint que par les pods de l'interface (index des contenus, catalogue des avatars) |
| `site` | nginx sans privilèges, `GET`/`HEAD` seulement, en-têtes stricts ; sert le moteur et un **contenu de secours intégré à l'image** |
| `contenus` | récupère en SSH (clé de déploiement en lecture seule, seul secret du pod) un dépôt de contenus public et un privé facultatif, **vérifie**, reconstruit, puis bascule d'un coup un lien `current` dans un volume partagé ; contenu invalide ou dépôt injoignable : la version en ligne reste, l'erreur est publiée dans un fichier d'état |
| Build | Docker en deux étapes (UBI 9, Node.js) ; seul un changement du **moteur** demande un build, les contenus passent par Git |
| Identité | son **propre oauth2-proxy** (confiance dans les en-têtes `X-Forwarded-*` limitée au routeur, comme pour la discussion) et son propre client Keycloak, même realm que la discussion ; rôles : administrateur, responsables (parents), protégés (enfants) ; pas d'invités. Pourquoi : une école servie sous l'origine de la discussion aurait tous les droits de la personne sur la discussion. La CSP de l'école n'autorise que l'origine de la discussion ; la reconnexion passe par la connexion de la discussion, avec retour vers l'école. Voir [l'interface](../../../deploy/okd/apps/chat-interface/README.md) |
| Données | progression et carnet dans la base de l'interface (table d'événements, profil) ; personne n'écrit dans le journal d'un autre |
| Ouverture depuis la discussion | l'analyse d'intention (modèle, schéma JSON) reconnaît « école » ; une **politique déterministe** autorise l'action `ouvrir_ecole` ; le lien, vers l'adresse de l'école, est construit par le serveur à partir de l'index de l'école ; le navigateur en fait un bouton, et la consigne du modèle ne contient aucune adresse. Dans le cockpit, la bascule sur l'école, à la bonne matière, se fait sans bouton : en service, en recette ; le bouton reste hors du cockpit |
| Cockpit | l'école n'accepte d'être affichée que par l'interface : `frame-ancestors 'self' <origine de l'interface>` remplace l'ancien refus total (`X-Frame-Options: DENY`) ; l'origine est donnée au build, aucun domaine n'est dans le dépôt. Elle envoie le signal `sophia.pret` (identifiant `ecole`) à la seule origine de l'interface, une fois le profil et le journal reçus. Sur un appareil sans session dans l'école, la connexion refuse d'être affichée dans un cadre : « Se reconnecter » ouvre la connexion dans un onglet, une fois par appareil. Elle envoie aussi son **contexte de page** (`sophia.contexte` : la matière et le thème de la séance, identifiants de l'index revérifiés par le serveur ; ni niveau, ni note, ni prénom, ni texte libre), pour le volet « Demander à Sophia » (en service, en recette). En service, vérifié sur ordinateur ; en recette sur téléphone et tablette ancienne ([contrat d'intégration](../README.md#intégrer-un-module-au-cockpit)) |
| « Quoi de neuf ? » | l'école est un site statique : toutes les données de la personne sont dans l'interface. Une route de résumé dans l'école devrait rappeler l'interface, une boucle inutile ; c'est donc **l'interface qui calcule le résumé de l'école**, au même format et sans modèle : pas de jeton relayé, pas de mappeur d'audience, pas d'entrée réseau nouvelle. Les **nouveautés** sont datées par l'interface, qui garde la date de première apparition de chaque activité (le stockage de l'école repart de zéro à chaque image et ses contenus sont clonés sans historique : elle ne sait pas dater une activité de façon fiable) ; le fichier d'état de l'école lui signale une publication. Première version (notes des 7 derniers jours, nouveautés du contenu sur 14 jours, un enfant ne voyant que son niveau) : en service, en recette |

### Format des contenus

`contenus/<matière>/<niveau>/<module>/`, un fichier YAML par module et par niveau. Types d'activités : leçon (Markdown avec en-tête YAML), TP, défi QCM, « clique sur le mot », « je complète », dictée sur ardoise, fiche de lecture. Champs obligatoires : `id`, `type`, `titre`, `notions`, `source`, `licence`, `redistribuable`.

Le build **refuse** tout contenu invalide : bonne réponse absente des choix, notion inconnue, licence manquante. Le dépôt privé ajoute des modules sans rien remplacer ; seul ce qui est marqué `redistribuable: true` entre dans la version de partage, qui ne garde que des liens vers le reste.

## Version publique

- **Un dépôt public à part**, qui ne contient que le **site construit** (aucun moteur source, aucun contenu privé), avec un miroir vers une page statique hébergée ; une racine qui accueille les cours publics, filtrés par une **liste versionnée des cours autorisés**.
- **Publication par un script**, sur l'accord de l'administrateur : il construit, puis **vérifie** l'absence de données privées (une liste de mots interdits gardée dans le dépôt privé, jamais recopiée ailleurs ; les cours hors liste refusés), montre le résumé, et ne pousse que sur confirmation. Une relance sans changement ne publie rien.
- **La page publique est figée** ; la discussion, outil interne, ne l'ouvre jamais.
- L'ancienne adresse publique garde une redirection qui conserve le fragment, puis son dépôt est archivé.

## Règles : le modèle formule, le serveur décide

- Le serveur calcule les verdicts et les moyennes ; le modèle ne fait que **formuler**.
- **« Un indice, jamais la réponse », imposé deux fois** : l'activité est lue côté serveur depuis son identifiant (jamais depuis la requête), et le modèle ne reçoit pas la réponse quand il n'en a pas besoin ; puis un contrôle déterministe vérifie que sa sortie ne contient pas la réponse (choix, résultat en chiffres ou en lettres, mot dicté) — sinon, l'indice écrit dans l'activité ou un indice générique.
- **Vision** : le modèle recopie l'ardoise **sans connaître les mots attendus**, pour ne pas « corriger » l'enfant à sa place ; sortie en schéma JSON, vérifiée ; en cas d'échec, l'enfant saisit à la main.
- **Protection des enfants** : aucune comparaison entre enfants, carnet privé ; photos effacées dès la correction par un parent, et au plus tard 7 jours après l'envoi ; sécurité des travaux pratiques écrite dans les contenus (piles de 4,5 V au plus, ni prise, ni flamme, ni produit ménager, un adulte présent pour tout ce qui chauffe).

## Mesures

- ≈ 800 activités publiées (806) ; un module de physique-chimie relu en entier : 19 leçons, 13 TP, 19 défis, ≈ 120 questions vérifiées contre des corrigés de référence, aucune contradiction.
- 119 tests automatisés (contenus, build, progression, synchronisation, parcours dans le navigateur, relecture, compatibilité Safari 15, avis de nouvelle version, publication, affichage dans un faux cockpit).
- Pod : nginx limité à 64 Mi, synchronisation à 256 Mi.
- Tests sans données réelles : des prénoms fictifs dans les tests, jamais ceux des enfants.

## Leçons

- **PID 1 et processus zombies** : depuis git 2.47, chaque `git fetch` lance `git maintenance --auto --detach`. Le processus détaché est rattaché au PID 1 du conteneur — ici un processus Node.js, qui ne récolte pas les orphelins. Un zombie par synchronisation, jusqu'à la limite de 4 096 PID : « unable to fork », la synchronisation s'arrête (la version en ligne, elle, reste servie). Correctif à la source : `git -c maintenance.autoDetach=false -c gc.autoDetach=false`, la maintenance se fait alors sur place, et un test qui vérifie l'absence de `--detach` dans la trace de git (il échoue sans le correctif). Défense en profondeur écartée : `shareProcessNamespace: true` ferait du conteneur `pause` le PID 1, mais les trois conteneurs tournent sous le même UID, et partager les processus exposerait les secrets d'oauth2-proxy aux deux autres. Un simple redémarrage ne fait que repousser l'incident.
- **Bascule atomique et contenu de secours** : une synchronisation en panne ne casse jamais le site.
- **UID arbitraire d'OpenShift** : `ssh` exige une entrée dans `/etc/passwd` — d'où `chmod g+w /etc/passwd` dans l'image et des chemins donnés au groupe 0.
- **Séparer moteur et contenus** : les contenus évoluent par Git, vérifiés avant publication, sans reconstruire l'image.
- **Le moteur avant les contenus** : un contenu qui utilise un nouveau champ ne se publie qu'après le build du moteur qui le comprend ; sinon la synchronisation refuse tout le contenu (« opération inconnue ») et ne publie plus rien, la version en ligne restant servie.
- **Une image écrite doit devenir une image** : un crochet non refermé dans le texte (« [EF) ») faisait d'une figure un lien. Le build refuse désormais une image de leçon qui ne devient pas une `<img>`.
- **L'axe de symétrie se trace après la forme** remplie, sinon elle le cache ; avant les petits codages, que ses tirets cacheraient.
- **Droits de redistribution portés par chaque ressource** : la version de partage se construit d'elle-même, sans tri à la main.
