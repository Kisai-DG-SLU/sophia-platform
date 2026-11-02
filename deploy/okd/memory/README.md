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
| `01-memory-metadata.sql` | schéma `sophia.memory_metadata` : métadonnées de chaque souvenir (propriétaire, type, projet, confidentialité, provenance, validation), à côté du point dans la base vectorielle. **Sans usage** depuis le service mémoire, dont le registre a son propre schéma ; à retirer ou à réaligner |
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
| Collection vectorielle et ses 17 index | **en service**, plus les index du registre (document, lot, rang, version) ; vide jusqu'au premier dépôt |
| Base vectorielle sur son volume dédié | **en service**, avec une clé d'API : déplacée quand la collection était encore vide (copie contrôlée octet pour octet, ancien répertoire gardé une semaine pour un retour arrière) |
| Quota et valeurs par défaut du namespace | **en service** |
| Graphe (Neo4j) | **à 0 réplique** : il n'a jamais démarré. Il reviendra avec une image officielle figée par empreinte et un mot de passe dans un Secret, jamais dans le manifeste |
| Ingestion | **suspendue** (CronJob `suspend: true`), à reconstruire : build reproductible et image figée, lecture des documents dans le stockage objet, aucun mot de passe dans une URL, écriture par le service mémoire ; elle écrivait dans la base vectorielle en direct, ce que la zone fermée refuse désormais |
| Service mémoire | **en service** : originaux et textes dans un seau S3 versionné, registre dans PostgreSQL, textes validés dans la forge, audit en base, extraction isolée ([`memoire/`](memoire/README.md)) |
| Réseau du namespace | **en service** : refus par défaut en entrée et en sortie, une règle par flux, EgressFirewall limité aux réseaux internes, posés avec le service mémoire |

## Le service mémoire

La mémoire est un **service**, comme le modèle : appelé par l'interface et par les agents selon leurs droits, et **seul rédacteur**. Il est **en service** dans l'installation de référence ; son contrat, ses règles et sa mise en service sont dans [`memoire/`](memoire/README.md) :
- **où vit quoi** : originaux et textes extraits dans un seau S3 versionné, `attente/` effaçable et `valide/` protégé ; registre des documents et des versions dans PostgreSQL ; textes validés dans la forge, un dépôt par niveau ; base vectorielle réduite à un index reconstructible ;
- **versions** : un document est une personne et son chemin ; une nouvelle version attend, la version validée précédente reste cherchable ;
- **validation** par une seule personne désignée, documents personnels et intimes des autres réduits à l'auteur, au niveau, à la date et au poids ;
- **droits par niveau** posés par le service, et leurs limites (administrateurs des lieux, miroir) ;
- **audit en base** par un rôle qui ne peut qu'ajouter ;
- **extraction isolée** dans un pod sans secret, sans jeton et sans réseau ;
- la **fermeture de la zone** et une **mise en service générique**, avec ses épreuves.

La page « Mémoire » du cockpit, qui verse, range en versions et valide, est décrite avec le [cockpit](../apps/chat-interface/README.md#page--mémoire-).

### Ensuite

Reconstruction de l'index par un outil d'administration ; façade MCP pour les agents et outil mémoire du chat ; reconstruction de l'ingestion (lecture dans le stockage objet avec l'auteur de chaque document, écriture par `proposer`) ; le graphe.
