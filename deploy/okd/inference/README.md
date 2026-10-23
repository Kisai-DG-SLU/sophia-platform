# Inférence locale — texte, vision, voix et images (`sophia-inference`)

Un modèle de langage qui lit aussi les images, servi par le GPU du serveur, une voix (reconnaissance et synthèse) et un générateur d'images servis par son CPU, routés par le routeur de modèles comme les modèles distants : **même interface, bascule par simple choix du modèle, aucune donnée ne sort du cluster.** Le namespace n'a **aucune sortie réseau** : les modèles sont déposés depuis le nœud, à des révisions et empreintes figées.

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Modèle de texte | **Qwen3.5-9B**, GGUF **Q6_K** (7,5 Go, Apache 2.0) | **appels d'outils fiables** (MCP, skills, multi-agent) : tau2-bench ≈ 87, contre ≈ 36 pour un modèle de taille voisine essayé d'abord ; tient sur une carte de 16 Go avec du contexte |
| Serveur | llama.cpp (`llama-server`), version figée | API compatible OpenAI, appels d'outils (`--jinja`), discussions en parallèle, cache de prompt |
| Contexte | cache en 8 bits et partagé : 245 760 tokens, 61 440 par discussion | modèle hybride (8 couches d'attention complète sur 32) : ≈ 17 Kio de cache par token en 8 bits ; même mémoire que 131 072 tokens en 16 bits |
| Vision | module `mmproj` du même modèle (F16, 0,9 Go) sur le GPU (`--mmproj`), 2 048 tokens au plus par image | lire un devoir, une photo, un document sans quitter le serveur ; la borne tient la mémoire et le temps |
| Raisonnement interne | coupé par défaut (`--reasoning off`), réactivable par requête | mesuré : même fiabilité des outils, boucles deux fois plus rapides |
| Image | construite dans le cluster, CUDA compatible avec le pilote du nœud | l'image officielle visait une version de CUDA plus récente que le pilote |
| Accès au GPU | conteneur privilégié, bibliothèque du pilote (`libcuda.so.1`) montée depuis l'hôte, **sans** ressource `nvidia.com/gpu` | sur ce nœud, le crochet du *container toolkit* de l'opérateur NVIDIA échoue ; le *device plugin* est désactivé |
| Reconnaissance vocale | **Parakeet TDT 0.6B v3** (ONNX int8), CPU | ≈ 5 % d'erreurs en français, 0,4 à 0,6 s par phrase |
| Synthèse vocale | **Pocket TTS** (modèle français, int8), CPU | premier son en 75 ms, 4,6 fois plus vite que le temps réel ; le GPU reste au texte |
| Génération d'images | **stable-diffusion.cpp**, SDXL-Turbo en 1 étape + décodeur TAESDXL, CPU, 512 × 512 | une dizaine de secondes par image sans GPU ; la carte reste au texte. **Licence de SDXL-Turbo : usage non commercial** — à remplacer par un modèle à licence ouverte pour un usage commercial |
| Contrôle des images | classifieur d'images (Apache 2.0) après chaque génération | un contrôle déterministe autour de la sortie du modèle, en plus des règles appliquées avant |

## Mesures (carte d'entrée de gamme de 16 Go, CPU Xeon de 2016)

| Mesure | Résultat |
|---|---|
| Appels d'outils (bon outil, arguments JSON valides, résultat exploité) | 8/8 |
| Une discussion | 16,4 tokens/s, premier token 0,3 s |
| Quatre discussions simultanées | 9,9 tokens/s chacune, 39 au total |
| Boucle d'outil (recherche, météo, rappel), sans raisonnement | 4 à 21 s |
| Information cachée dans ≈ 97 000 tokens | retrouvée (à 15 % et à 60 %) |
| Lecture d'un très long prompt | ≈ 420 tokens/s (97 000 tokens ≈ 4 min) |

## Volume des modèles (préalable sur le nœud)

Les modèles vivent sur un volume logique dédié, créé une fois sur le nœud selon [`../../stockage-persistant.md`](../../stockage-persistant.md) — `LV_NAME=lv-models`, `LV_SIZE=200G`, `MOUNT_POINT=/var/mnt/models`, XFS, montage persistant —, puis exposé par `01-storage.yaml` (PV local `Retain`, lié nommément à `pvc-models`, monté en lecture seule). 200 Go d'emblée : un volume local ne s'agrandit pas, et il porte texte, vision, voix, images et les données des outils (`/var/mnt/models/skills`, voir [`../skills/`](../skills/)).

```bash
sudo lvs ${VG_NAME}                       # lv-models présent
df -h /var/mnt/models                     # monté, XFS
ls -lZ /var/mnt/models                    # étiquette container_file_t
```

## Vision

Le module de vision (`mmproj-F16.gguf`) est pris au même dépôt et à la même révision que le modèle, déposé depuis le nœud avec son empreinte, puis chargé par `--mmproj`. L'interface réduit les photos à 2 048 px sur leur plus grand côté avant l'envoi ; le routeur de modèles déclare l'alias `supports_vision`. Repli si la mémoire du GPU sature : `--no-mmproj-offload` (vision sur CPU, plus lente).

## Génération d'images (`sophia-image-gen`)

Deux conteneurs dans un pod de `sophia-inference`, sans sortie réseau :

| Conteneur | Rôle | Port |
|---|---|---|
| `sd-server` | stable-diffusion.cpp (MIT) : SDXL-Turbo + TAESDXL, quantifié en `q8_0`, API `/sdapi/v1/txt2img` | 1234 |
| `nsfw` | classifieur des images produites (`POST /classer` → probabilité), un seul fil de calcul | 8001 |

Seul le serveur MCP `image` de `sophia-skills` peut joindre ce pod ([`../skills/`](../skills/), règles de protection) : ni l'interface, ni le routeur de modèles. Le code des deux images n'est pas fourni ; leur contrat est ci-dessus. Modèles : `fetch-image-models.sh`, depuis le nœud (≈ 7,3 Go, révisions et SHA-256 figés).

## Le service vocal (`sophia-voice`)

Le code n'est pas fourni ; son contrat (API OpenAI, routée par le routeur de modèles) :

| Route | Rôle |
|---|---|
| `POST /v1/audio/transcriptions` | audio des navigateurs (webm/opus, mp4/aac, wav) → texte |
| `POST /v1/audio/speech` | texte → WAV ; voix sur liste blanche, inconnue → voix par défaut |
| `GET /v1/voices`, `GET /health` | voix disponibles, état |

Règles : **nombres, heures, dates et opérations écrits en lettres avant la synthèse** (le modèle ne lit pas les chiffres) ; Markdown, liens, emojis et annonces d'outils retirés ; audio ≤ 10 Mo et ≤ 120 s, texte ≤ 2 000 caractères ; un traitement à la fois par modèle. Côté interface : la phrase dictée est envoyée, et la réponse est lue à voix haute, phrase par phrase.

Voix : celles du catalogue du modèle, ou une voix convertie depuis un enregistrement sous licence libre (`export-voices.sh`, sur le nœud, avec la version « clonage » du modèle). Jamais la voix d'une personne sans son accord.

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace-guardrails.yaml` | `PriorityClass`, `ResourceQuota`, `LimitRange` |
| `01-storage.yaml` | volume local des modèles, monté en lecture seule |
| `02-build.yaml` | image du serveur de texte |
| `03-llama-server.yaml` | serveur de texte (GPU) et Service |
| `04-network.yaml` | tout refusé, sauf le routeur de modèles vers les deux services |
| `05-voice.yaml` | build et déploiement du service vocal (CPU) |
| `06-image.yaml` | builds, déploiement, Service et entrée réseau du générateur d'images et de son classifieur (CPU) |
| `fetch-voice-models.sh`, `export-voices.sh` | modèles et voix, déposés depuis le nœud |
| `fetch-image-models.sh` | modèles d'image et classifieur, déposés depuis le nœud |
| `bench.py` | banc d'essai : appels d'outils, débit seul et à quatre — **contre le serveur seul, jamais en production** |

## Procédure (l'administrateur)

0. Volume `lv-models` créé et monté sur le nœud (ci-dessus).
1. Modèle de texte et module de vision déposés sur le nœud (`curl` à une révision figée, `sha256sum -c`, étiquette SELinux `container_file_t`) ; modèles vocaux : `fetch-voice-models.sh` ; modèles d'image : `fetch-image-models.sh`.
2. Images : `oc start-build` du serveur de texte, du service vocal, du générateur et du classifieur d'images.
3. `00`, `01`, `04`, puis `03`, `05` et `06` : `--dry-run=server`, puis `apply`.
4. Routeur de modèles : alias de texte et de voix, puis ajout des alias aux clés virtuelles restreintes.

**Limites :** 4 discussions à la fois (une cinquième attend) ; 61 440 tokens par discussion, au-delà la discussion est résumée (échanges les plus anciens) et un fichier trop gros est refusé avec un message clair ; voix d'un petit modèle sur CPU, correcte mais peu expressive.
