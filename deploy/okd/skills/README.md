# Outils locaux — serveurs MCP sans Internet (`sophia-skills`)

La zone « outils » de l'[architecture](../../../docs/architecture.md) : des serveurs MCP que l'interface (et les agents) proposent au modèle, et qui **calculent** au lieu de laisser le modèle estimer — positions, distances, cartes, images. Aucun n'a de sortie vers Internet : leurs données sont préparées depuis le nœud et montées en lecture seule.

| Zone | Ce qu'on y met | Sortie réseau |
|---|---|---|
| [`sophia-dmz`](../dmz/) | ce qui va chercher dehors : recherche web, lecture de pages, météo | Internet (80/443) seulement |
| **`sophia-skills`** | **outils locaux** : géographie, images (règles de protection), sources officielles téléchargées | **aucune** (DNS ; modèles d'image) |
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
- un échec est un `error` lisible, que le modèle rapporte tel quel.

## Géographie — `sophia-geo`

| Outil | Rôle |
|---|---|
| `lieu` | ville, commune ou code postal : nom, pays, région, coordonnées, population, source ; plusieurs résultats si le nom est ambigu |
| `distance` | distance à vol d'oiseau (grand cercle) entre deux lieux |
| `carte` | carte SVG **exacte** (contours réels, lieux à leurs coordonnées), trajet et distances en option, style « simple » ou « bd » (carte ancienne façon bande dessinée) |

Données ouvertes : communes françaises (API officielle des communes), GeoNames (villes de plus de 1 000 habitants, noms français), contours des pays Natural Earth. ≈ 230 Mo téléchargés, ≈ 8 Mo gardés. Mise à jour : relancer `fetch-geo-data.sh`, puis redémarrer `sophia-geo`.

## Images — `sophia-image`

Outil `image` : la demande de la personne (en français, telle quelle) et la consigne anglaise écrite par le modèle, un style (`illustration`, `coloriage`, `aquarelle`, `bd`, `photo`) ; 512 × 512, une génération à la fois sur CPU (une dizaine de secondes, une seconde demande attend).

**Contrôles déterministes, dans le serveur et pas dans le modèle :**

1. **avant** : des règles vérifient **la demande et la consigne** (le modèle ne peut pas glisser un contenu que la personne n'a pas demandé) ; sujet sexuel avec un enfant ou un âge mineur : **toujours refusé** ; sujet sexuel avec une personne réelle nommée : refusé ; pour un **compte protégé** (enfant) : rien de sexuel, ni nudité, violence, armes, horreur, drogue, alcool ; une consigne négative est imposée à chaque génération ;
2. **après** : pour un compte protégé, chaque image passe au classifieur ; au-dessus du seuil, nouvel essai avec une autre graine, puis refus ; **si le classifieur est indisponible, rien n'est montré** à un compte protégé ;
3. **à l'affichage** : l'interface vérifie à nouveau le contenu reçu.

Le nom et la licence du modèle accompagnent chaque image. Licence de SDXL-Turbo : usage **non commercial** (voir [`../inference/`](../inference/)).

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
