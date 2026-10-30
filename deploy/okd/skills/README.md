# Outils locaux — serveurs MCP sans Internet (`sophia-skills`)

La zone « outils » de l'[architecture](../../../docs/architecture.md) : des serveurs MCP que l'interface (et les agents) proposent au modèle, et qui **calculent** au lieu de laisser le modèle estimer — positions, distances, cartes, images. Aucun n'a de sortie vers Internet : leurs données sont préparées depuis le nœud et montées en lecture seule.

| Zone | Ce qu'on y met | Sortie réseau |
|---|---|---|
| [`sophia-dmz`](../dmz/) | ce qui va chercher dehors : recherche web, lecture de pages, météo | Internet (80/443) seulement |
| **`sophia-skills`** | **outils locaux** : géographie, images (règles de protection), sources officielles téléchargées, fichiers de la personne | **aucune vers Internet** (DNS ; modèles d'image ; pour l'outil « fichiers » : le fournisseur d'identité et le port interne de Fichiers) |
| [`sophia-inference`](../inference/) | les modèles : texte, voix, générateur et classifieur d'images | aucune |

```
interface (API des discussions) ──MCP :8000──→ sophia-geo    (lieu, distance, carte)   ← /data/geo (lecture seule)
                                └─MCP :8000──→ sophia-image  (image) ──→ sophia-image-gen (sophia-inference)
modules (ex. cuisine) ──────────MCP :8000──→ sophia-image seulement      générateur :1234, classifieur :8001
```

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace-guardrails.yaml` | `ResourceQuota`, `LimitRange` |
| `01-network.yaml` | tout refusé ; entrée : l'interface → 8000 (pods `sophia-mcp: "true"`), un module → `sophia-image` seul ; sortie : DNS, `sophia-image` → `sophia-image-gen` |
| `02-storage.yaml` | PV local `/var/mnt/models/skills` (même volume que les modèles, dossier à part) et PVC `pvc-skills-data`, lus en lecture seule |
| `03-geo.yaml` | `sophia-geo` : outils `lieu`, `distance`, `carte` |
| `04-image.yaml` | `sophia-image` : outil `image` ; modèles dans [`../inference/06-image.yaml`](../inference/06-image.yaml) |
| `fetch-geo-data.sh`, `geo_build.py` | données géographiques, préparées sur le nœud dans un conteneur jetable ; l'ancienne version reste en place si la préparation échoue |

Chaque serveur MCP porte l'étiquette `sophia-mcp: "true"`, écoute sur 8000 (`/mcp`, *streamable HTTP*, sans état) et répond sur `/health` ; l'interface l'ajoute à sa liste de serveurs MCP.

## Contrat commun : annonces et affichage

Le code des serveurs n'est pas fourni ; leur contrat :

- chaque outil déclare dans ses métadonnées MCP **son annonce** (`sophia/annonce` : icône, libellé, argument à montrer — « 📍 Lieu : Lyon ») : l'interface l'affiche pendant la réponse sans connaître l'outil à l'avance ;
- `sophia/injecte` : paramètres que **l'interface** remplit elle-même, jamais le modèle (ex. `protected` = compte protégé, tiré de la session) ;
- `sophia/delai_s` : délai d'attente de l'outil (file d'attente comprise) ;
- un résultat peut porter `_affichage` (`image/png` en base64 ou `image/svg+xml`, avec un titre) : l'interface **vérifie** le contenu puis l'insère tel quel dans la réponse ; le modèle ne reçoit que la description, pas l'image ;
- un échec est un `error` lisible, que le modèle rapporte tel quel ;
- `sophia/jeton` : l'outil agit sous l'identité de la personne et exige son jeton relayé ; l'interface ne l'envoie qu'aux serveurs de sa liste fermée, et ne propose jamais ces outils au modèle : elle les appelle elle-même après la décision des règles ([Relais de l'identité](../../../docs/concepts/12-relais-identite.md)) ;
- `sophia/contenu` : le résultat contient le contenu d'un document de la personne ; l'interface ne le donne qu'à un modèle local et le retire de tout autre appel ([Modèles par rôle](../../../docs/concepts/13-modeles-par-role.md)).

## Géographie — `sophia-geo`

| Outil | Rôle |
|---|---|
| `lieu` | ville, commune ou code postal : nom, pays, région, coordonnées, population, source ; plusieurs résultats si le nom est ambigu |
| `distance` | distance à vol d'oiseau (grand cercle) entre deux lieux ; un lieu peut aussi être donné par ses coordonnées (ci-dessous) |
| `carte` | carte SVG **exacte** (contours réels, lieux à leurs coordonnées), trajet et distances en option, style « simple » ou « bd » (carte ancienne façon bande dessinée) |

Données ouvertes : communes françaises (API officielle des communes), GeoNames (villes de plus de 1 000 habitants, noms français), contours des pays Natural Earth. ≈ 230 Mo téléchargés, ≈ 8 Mo gardés. Mise à jour : relancer `fetch-geo-data.sh`, puis redémarrer `sophia-geo`.

Les lieux que l'outil reçoit passent d'abord par les gardes de l'interface : un lieu tiré par le modèle n'est retenu que s'il figure dans le message de la personne ou s'il est le nom d'un lieu enregistré (voir [l'interface](../apps/chat-interface/README.md)).

**Lieux par commune et code postal, ou par coordonnées** (en service) :

- la forme « Commune (code postal) », celle qu'envoie l'interface, ne retient que les communes de ce code postal : « Exempleville (00000) » répond « introuvable » plutôt que de désigner un homonyme ailleurs ;
- `distance` et `carte` acceptent un lieu de la forme `{"nom": …, "latitude": …, "longitude": …}`. C'est **le serveur de l'interface** qui l'insère, à la place du nom d'un lieu enregistré, comme ses autres arguments réservés ; un objet lieu venu du modèle est refusé. La réponse rend le **nom** du lieu et sa commune, **jamais ses coordonnées**, et la carte ne l'étiquette pas d'une adresse.

**Base d'adresses locale** (codée et relue, pas encore en service), pour géocoder une fois l'adresse d'un lieu enregistré dans un profil :

- données ouvertes de la base d'adresses nationale, par département, préparées sur le nœud par `fetch-geo-data.sh --ban <départements>` ; la liste des départements est donnée au lancement et **n'est écrite dans aucun fichier versionné** ; base SQLite avec un index plein texte, ouverte en lecture seule ; l'ancienne base reste en place si la préparation échoue ;
- **route de candidats hors MCP** (`POST /api/adresse/candidats`), que seul le serveur de l'interface appelle à l'enregistrement d'un lieu, jamais le modèle : l'adresse est dans le corps de la requête, jamais dans l'adresse, un journal ou un message d'erreur ;
- classement déterministe (code postal saisi, numéro exact puis le plus proche dans la voie, puis le rang plein texte) ; **c'est la personne qui choisit** parmi les candidats ; un département non chargé répond une liste vide, et l'interface se rabat sur la commune ;
- mise à jour à la main, au plus une fois par mois : un lieu n'est géocodé qu'à son enregistrement, et ses coordonnées sont gardées avec lui.

Hors du pays couvert, un *plus code* (Open Location Code) saisi par l'administrateur est décodé en local par l'interface, sans rien envoyer dehors. Les outils et la météo travaillent sur la commune et ses coordonnées, jamais sur l'adresse.

## Images — `sophia-image`

Outil `image` : la demande de la personne (en français, telle quelle) et la consigne anglaise écrite par le modèle, un style (`illustration`, `coloriage`, `aquarelle`, `bd`, `photo`) ; 512 × 512, une génération à la fois sur CPU (une dizaine de secondes, une seconde demande attend).

**Contrôles déterministes, dans le serveur et pas dans le modèle :**

1. **avant** : des règles vérifient **la demande et la consigne** (le modèle ne peut pas glisser un contenu que la personne n'a pas demandé) ; sujet sexuel avec un enfant ou un âge mineur : **toujours refusé** ; sujet sexuel avec une personne réelle nommée : refusé ; pour un **compte protégé** (enfant) : rien de sexuel, ni nudité, violence, armes, horreur, drogue, alcool ; une consigne négative est imposée à chaque génération ;
2. **après** : pour un compte protégé, chaque image passe au classifieur ; au-dessus du seuil, nouvel essai avec une autre graine, puis refus ; **si le classifieur est indisponible, rien n'est montré** à un compte protégé ;
3. **à l'affichage** : l'interface vérifie à nouveau le contenu reçu.

Le nom et la licence du modèle accompagnent chaque image. Licence de SDXL-Turbo : usage **non commercial** (voir [`../inference/`](../inference/)).

## Fichiers de la personne — `mcp-fichiers`

État : en service (recherche) et déployé (lecture du contenu, recette à faire) ; le code et les manifestes de l'installation de référence ne sont pas publiés, leur contrat et leurs règles le sont ici. Module : [Bureautique](../../../docs/modules/bureautique/documentation.md).

| Outil | Rôle |
|---|---|
| `chercher_fichiers` | éléments trouvés par le nom (ou les plus récents), avec chemin, date, type, « modifiable », jamais d'URL |
| `details_fichier` | un élément et son chemin lisible |
| `lire_fichier` | texte d'un document, extrait sans exécution (archives XML bornées, PDF en texte seul), tronqué, marqué `contenu_sensible` |

Route HTTP à côté du MCP : `GET /api/resume`, le résumé de Fichiers pour le volet « Quoi de neuf ? » de l'interface (fichiers partagés avec la personne, modifiés depuis 14 jours, 20 au plus ; Fichiers n'expose pas la date du partage). Même jeton relayé et même audience que les outils ; 401 sans jeton valide. En service, contrôlée sans jeton ; l'appel par l'interface est prévu.

- **Lecture seule, sous l'identité de la personne** : jeton relayé par l'interface, vérifié (signature, émetteur, expiration, audience, client d'origine, groupes), puis **échangé** contre un jeton émis pour l'outil ; Fichiers l'introspecte et applique ses propres droits. Aucun compte de service qui lit tout. Une session MCP par appel ; aucun jeton journalisé (journal du client HTTP ramené à WARNING, pour que la recherche de la personne n'y figure pas).
- **Réseau** : entrée depuis l'interface seulement ; sortie vers le DNS, le fournisseur d'identité (clés publiques et échange) et le port interne réservé de Fichiers (GET seulement), **rien d'autre**.
- **Build dans un namespace à part** (`sophia-skills-build`) : l'outil reçoit les jetons de la famille, donc aucun agent ne doit pouvoir changer sa BuildConfig ou son image. Ce namespace n'a **aucun RoleBinding vers un compte d'agent** ; quota d'un build à la fois ; aucune entrée.
- **EgressFirewall du build en refus final** : Services et pods du cluster, **l'API du cluster** (nœuds du plan de contrôle, sur le port de l'API ; sans cette règle, le build reste bloqué au clonage, faute de pouvoir mettre à jour son état), PyPI ; rien d'autre.
- **Leçon : démarrer dans l'image de base même.** Une image minimale peut manquer de la base des fuseaux horaires : un fuseau nommé lève alors une exception à l'import, et le pod boucle au démarrage (stratégie `Recreate` : l'outil est coupé). Remèdes : la base des fuseaux comme dépendance figée, un import qui ne casse pas le serveur (la route concernée répond 503, le reste continue), un contrôle d'import dans le Containerfile qui fait échouer le **build** plutôt que le pod, et des tests sans base système.
- **Image de base** déjà munie de Python, **importée par le registre interne** (ImageStream en `referencePolicy: Local`, figée par empreinte) : le pod de build ne tire rien chez l'éditeur et n'installe aucun paquet système. **Dépendances Python figées par empreinte** (`--require-hashes`, roues binaires seules). Source binaire (`git archive` du commit), aucun déclencheur : une nouvelle image ne remplace le pod qu'après une nouvelle empreinte commitée et appliquée.

## Variables

| Variable | Rôle |
|---|---|
| `${MODULE_APP}` | étiquette `app` d'un module autorisé à joindre l'outil `image` (un bloc par module) |
| `${NODE_ADDR}` | adresse d'administration du nœud (préparation des données) |
| `${GEO_SRC_DIR}`, `${IMAGE_SRC_DIR}` | dossiers du code des serveurs (builds binaires) |

## Procédure (l'administrateur)

1. Données : `fetch-geo-data.sh` et `geo_build.py` copiés sur le nœud, puis `sudo bash fetch-geo-data.sh`.
2. Modèles d'image : voir [`../inference/`](../inference/).
3. `00` à `04` : `--dry-run=server`, puis `apply` ; builds : `oc start-build sophia-geo` et `sophia-image` (`--from-dir`).
4. Interface : ajouter `http://sophia-geo.sophia-skills.svc:8000/mcp` et `http://sophia-image.sophia-skills.svc:8000/mcp` à sa liste de serveurs MCP.
5. Vérifier : `/health` des deux serveurs à `ok` ; depuis l'interface, « distance Paris – Lyon » (≈ 392 km, outil `distance`) et une image en compte protégé.
