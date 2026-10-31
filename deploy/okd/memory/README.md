# Mémoire — embedding et schéma (`sophia-memory`)

Les briques de la mémoire (RAG) en service : un service qui transforme du texte en vecteurs, et le schéma de la collection vectorielle. Tout tourne **dans le cluster, sur CPU** : aucun document ne sort pour être vectorisé. Le modèle de la connaissance est décrit dans la fiche [RAG 5D](../../../docs/concepts/03-rag-5d.md) ; ce dossier en donne l'état réel et la recette.

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Modèle | **BAAI/bge-m3** (1 024 dimensions, multilingue), vecteurs normalisés | bon en français et entre langues ; un seul modèle pour toute la mémoire |
| Modèle dans l'image | téléchargé **au build** (jeton Hugging Face passé en argument de build), chargé depuis `/models/bge-m3` | le pod démarre sans accès à Internet ; la révision du modèle suit l'image |
| Serveur | FastAPI + sentence-transformers, PyTorch CPU | |
| Sondes | `/health` : prêt après 30 s, vivant après 60 s | le chargement du modèle prend du temps au démarrage |
| Ressources | 1 CPU et 2 Gi demandés, 2 CPU et 4 Gi au plus | le modèle tient en mémoire sans GPU (la carte reste au modèle de langage) |
| Base vectorielle | Qdrant, **image figée par empreinte**, `Recreate`, classe `sophia-agents`, `enableServiceLinks: false`, sur un **volume logique XFS dédié** (20 Go au départ, monté sous `/var/mnt`), PV et PVC désignés l'un l'autre | hors de `/var` du nœud, qu'il partageait avec d'autres services ; s'agrandit à chaud (`lvextend -r`) ; l'optimisation de Qdrant demande jusqu'à deux fois la place pendant qu'elle tourne ; alerte de remplissage à 80 % et 90 % ([`../monitoring/`](../monitoring/)) |

**Changer de modèle change la dimension des vecteurs** : tout le contenu déjà indexé est à revectoriser. Le modèle se choisit donc avant la première ingestion.

## Contrat

Le code du service n'est pas fourni ; son contrat :

| Route | Rôle |
|---|---|
| `GET /health` | état, modèle, dimension |
| `POST /v1/embeddings` | API compatible OpenAI (`input` : texte ou liste) |
| `POST /embed` | lot de textes (forme historique) |

Port 8080, sans authentification : le service ne doit être joignable que depuis le routeur (NetworkPolicy du namespace, prête : voir « État »).

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace-guardrails.yaml` | quota du namespace sur les limits (8 CPU, 16 Gi, 10 pods) et valeurs par défaut des conteneurs |
| `01-embedding-deployment.yaml` | Deployment du service ; valeurs par défaut entre `${…:-…}` |
| `01-memory-metadata.sql` | schéma `sophia.memory_metadata` : métadonnées de chaque souvenir (propriétaire, type, projet, confidentialité, provenance, validation), à côté du point dans la base vectorielle |
| `qdrant-schema.py` | collection et index de payload de la base vectorielle ; idempotent, ne supprime ni ne modifie rien |

## Variables

| Variable | Défaut |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | `sophia-memory` |
| `${QDRANT_SERVICE}` | Service de la base vectorielle |
| `${EMBEDDING_IMAGE}` | image construite dans le registre interne |
| `${EMBEDDING_MODEL_PATH}` | `/models/bge-m3` |
| `${EMBEDDING_REPLICAS}` | 1 |
| `${EMBEDDING_CPU_REQUEST}`, `${EMBEDDING_CPU_LIMIT}` | 1, 2 |
| `${EMBEDDING_MEM_REQUEST}`, `${EMBEDDING_MEM_LIMIT}` | 2Gi, 4Gi |

## Procédure (l'administrateur)

0. Garde-fous : `00-namespace-guardrails.yaml`, `--dry-run=server`, `apply`, puis `oc describe quota -n ${SOPHIA_MEMORY_NAMESPACE}`.
1. Image : build Docker du service, avec le jeton Hugging Face en argument de build (Secret du build, jamais dans le dépôt).
2. `envsubst` sur `01-embedding-deployment.yaml` (ou valeurs par défaut), `--dry-run=server`, puis `apply`.
3. Vérifier : pod prêt, `GET /health` donne la dimension 1 024, un `POST /v1/embeddings` depuis un pod autorisé rend un vecteur.

## Schéma de la collection vectorielle

Une collection (1 024 dimensions, distance cosinus, celles du modèle d'embedding) et un index de payload par étiquette. Le schéma compte **18 étiquettes, sous leur nom français** ; 17 sont indexées :

| Type d'index | Étiquettes |
|---|---|
| `keyword` | `utilisateur`, `type_memoire`, `stockage`, `provenance`, `format`, `confidentialite`, `projet`, `theme`, `mots_cles`, `priorite`, `statut_arbitrage` |
| `float` | `confiance` |
| `integer` | `version` |
| `datetime` | `date_creation`, `date_maj`, `date_validation`, `date_expiration` |

`source`, champ libre, n'est pas indexée. Qdrant n'impose pas de schéma : l'index accélère le filtre, il ne valide rien. La **validation des valeurs** (listes fermées, cohérence des dates) revient au service mémoire, seul rédacteur prévu.

`qdrant-schema.py` (bibliothèque standard seule) lit d'abord, puis, avec `--apply`, crée ce qui manque. Un index déjà présent avec un autre type est signalé (code de sortie 1), jamais changé. Il s'arrête si la collection a d'autres dimensions.

```bash
oc -n ${SOPHIA_MEMORY_NAMESPACE} port-forward svc/${QDRANT_SERVICE} 16333:6333
```

Dans un second terminal :

```bash
python3 qdrant-schema.py --url http://127.0.0.1:16333
python3 qdrant-schema.py --url http://127.0.0.1:16333 --apply
```

Attendu : la collection, puis 17 lignes `[à faire]` ; avec `--apply`, 17 lignes `(créé)` ; une relance ne change rien. Retour arrière, sans perte sur une collection vide : `DELETE /collections/<collection>/index/<champ>` pour chaque champ.

## Accès par le routeur de modèles

L'ingestion et le service mémoire appellent l'embedding par l'alias **`sophia-embedder`** du routeur ([`../core/`](../core/)), jamais le service directement : mêmes clés restreintes et mêmes journaux que les modèles de langage. Une clé qui en a besoin reçoit l'alias par `add-model-to-keys.py`. Contrôle : un appel `/v1/embeddings` sur l'alias rend un vecteur de 1 024 valeurs.

## État

| Brique | État |
|---|---|
| Embedding (bge-m3, CPU) et alias `sophia-embedder` | **en service** |
| Collection vectorielle et ses 17 index | **en service**, vide : rien n'est encore ingéré |
| Base vectorielle sur son volume dédié | **en service** : déplacée quand la collection était encore vide (copie contrôlée octet pour octet, ancien répertoire gardé une semaine pour un retour arrière) |
| Quota et valeurs par défaut du namespace | **en service** |
| Graphe (Neo4j) | **à 0 réplique** : il n'a jamais démarré. Il reviendra avec une image officielle figée par empreinte et un mot de passe dans un Secret, jamais dans le manifeste |
| Ingestion | **suspendue** (CronJob `suspend: true`), à reconstruire : build reproductible et image figée, lecture des documents dans le stockage objet, aucun mot de passe dans une URL, écriture par le service mémoire |
| Service mémoire | **prêt à installer** : code éprouvé au banc et relu, procédure relue ; pas encore appliqué (voir ci-dessous) |
| Réseau du namespace | **cible, prête** : la base vectorielle répond aujourd'hui sans clé, et le namespace n'a pas encore de NetworkPolicy ; la fermeture (clé, refus par défaut, une règle par flux, EgressFirewall) fait partie de l'installation du service mémoire |

## Le service mémoire : conçu, prêt à installer, pas encore en service

La mémoire est un **service**, comme le modèle : appelé par l'interface et par les agents selon leurs droits, et **seul rédacteur**. Son code est écrit et éprouvé au banc (105 tests), relu trois fois ; sa procédure d'installation est prête et relue. **Rien n'est appliqué sur le cluster** : aucun document n'est encore dans la mémoire, et la discussion répond toujours que la mémoire n'est pas disponible.

### Ce qu'il fait

| Route | Rôle |
|---|---|
| `rechercher` | rend les morceaux **validés**, non expirés, lisibles par l'appelant |
| `proposer` | dépose un document court |
| `moi` | niveaux permis à l'appelant, s'il valide, bornes |
| `depots`, `depots/{id}/fichiers`, `depots/{id}/notes` | dépôt groupé : un dépôt reçoit plusieurs fichiers ou notes, un par requête (le fichier en corps brut, sans multipart) |
| `mes_depots` | ce que la personne a déposé, avec son état (en attente, validé, refusé) |
| `a_valider`, `a_valider/compte`, `valider` | la liste à valider, son compte pour « Quoi de neuf ? », la validation ou le refus d'un document ou d'un dépôt entier |

Un document est découpé en morceaux (2 000 caractères, recouvrement de 200) et vectorisé par l'alias `sophia-embedder` du routeur, donc **dans le cluster**. L'analyse est synchrone (quelques minutes au pire) : le relais du chat attend en conséquence.

### Règles

- **Identité prouvée**, jamais déclarée par le modèle : jeton OIDC relayé pour une personne, jeton de compte de service pour un agent.
- **Niveaux de confidentialité** : `public`, `famille`, `personnel`, `intime`, `admin`. `personnel` et `intime` ne sont lisibles que par leur auteur ; l'administration lit `admin` en plus des niveaux communs ; un invité ne lit que `public`. Les agents sont limités à `public` tant que l'interface ne leur transmet pas l'identité de la personne. Le filtre de droits est **ajouté par le service** à toute requête ; le modèle ne peut pas l'élargir.
- **Validation par une seule personne** (décision du foyer, pour le moment) : un document versé dans la mémoire n'est utilisé qu'une fois **validé par l'administrateur du foyer**, désigné par son identifiant technique dans un réglage, et non par un groupe : un autre membre du groupe d'administration ne valide rien. Ce que cette personne verse est validé d'office. Le service refuse de démarrer si le réglage manque ou n'a pas la forme attendue. Ce qui vient du web passera par le [Tribunal Sémantique](../../../docs/concepts/05-tribunal-semantique.md).
- **Confidentialité devant le valideur** : pour les documents `personnel` et `intime` des autres, la liste à valider ne montre que l'auteur, le niveau, la date et le poids : ni nom de fichier, ni extrait, ni contenu ; le valideur peut valider ou refuser, sans pouvoir lire ensuite. **Limite** : cette règle protège l'interface, pas l'administration technique ; le journal d'audit relie un dépôt à son auteur (sans contenu ni nom de fichier).
- **Confiance** : 0 tant qu'un document n'est pas validé (et au refus), 1 une fois validé ; seul l'état de validation décide de l'usage.
- **Refus** : les vecteurs sont supprimés, et la fiche ne garde ni nom ni vecteur du document. Les originaux ne sont pas gardés.
- **Bornes** : taille par fichier et par dépôt, nombre de documents en attente et gardés par personne, longueur de texte par document, deux envois et deux extractions à la fois (au-delà, « occupé »).
- **Journal** : chaque écriture et chaque refus, avec identifiants, poids et nombre de morceaux ; jamais de contenu, de chemin ni de nom.

### Extraction isolée

Lire un PDF ou un document bureautique, c'est exécuter un analyseur sur un fichier inconnu. La première version le faisait dans un sous-processus du service : la relecture a montré qu'il pouvait lire l'environnement de son parent (`/proc/<parent>/environ`), donc les clés de la base vectorielle et du routeur, et le jeton du pod. **L'extraction tourne donc dans un pod à part**, de la même image, **sans Secret, sans jeton de compte de service, sans sortie réseau** et sans espace de processus partagé ; le service lui envoie les octets. Dans ce pod, chaque fichier est lu par un sous-processus borné (mémoire, temps de calcul, durée), sans écriture de fichier ni création de processus ; le type est déduit des octets, jamais du nom ; documents bureautiques lus sans DTD ; archives bornées en nombre d'entrées. Formats : texte, Markdown, PDF avec du texte, documents bureautiques ; les images viendront plus tard. Une épreuve d'isolement, lancée depuis le pod d'extraction, fait partie de l'installation.

### Réseau de la zone

Avec le service, la zone mémoire se ferme : clé d'API sur la base vectorielle, télémétrie coupée ; refus par défaut en entrée **et** en sortie, puis une règle par flux (base vectorielle ouverte au seul service mémoire, embedding au seul routeur, service mémoire au chat, extraction au seul service mémoire) ; EgressFirewall limité aux réseaux internes. Le service utilise sa propre clé du routeur, limitée à l'alias d'embedding.

### Côté cockpit (décisions du foyer)

- **Une page « Mémoire »** pour déposer des documents, **tout un dossier** d'un coup quand l'appareil le permet. Sur iOS, choisir un dossier n'est possible qu'à partir d'iOS 18.4 : sur une tablette plus ancienne, on prend plusieurs fichiers d'un coup, sinon un fichier à la fois.
- **La liste à valider** est sur la même page, avec une alerte dans « Quoi de neuf ? ».
- La page est en conception chez l'interface ; sans elle, le service peut être installé, mais personne ne peut encore déposer.

### Ensuite

Installation du service et fermeture de la zone ; page « Mémoire » ; reconstruction de l'ingestion (lecture dans le stockage objet avec l'auteur de chaque document, écriture par `proposer`) ; façade MCP pour les agents ; le graphe.
