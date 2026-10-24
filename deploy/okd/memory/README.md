# Mémoire — service d'embedding (`sophia-memory`)

Première brique de la mémoire (RAG) : un service qui transforme du texte en vecteurs, pour l'indexation dans la base vectorielle et la recherche. Il tourne **dans le cluster, sur CPU** : aucun document ne sort pour être vectorisé.

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Modèle | **BAAI/bge-m3** (1 024 dimensions, multilingue), vecteurs normalisés | bon en français et entre langues ; un seul modèle pour toute la mémoire |
| Modèle dans l'image | téléchargé **au build** (jeton Hugging Face passé en argument de build), chargé depuis `/models/bge-m3` | le pod démarre sans accès à Internet ; la révision du modèle suit l'image |
| Serveur | FastAPI + sentence-transformers, PyTorch CPU | |
| Sondes | `/health` : prêt après 30 s, vivant après 60 s | le chargement du modèle prend du temps au démarrage |
| Ressources | 1 CPU et 2 Gi demandés, 2 CPU et 4 Gi au plus | le modèle tient en mémoire sans GPU (la carte reste au modèle de langage) |

**Changer de modèle change la dimension des vecteurs** : tout le contenu déjà indexé est à revectoriser. Le modèle se choisit donc avant la première ingestion.

## Contrat

Le code du service n'est pas fourni ; son contrat :

| Route | Rôle |
|---|---|
| `GET /health` | état, modèle, dimension |
| `POST /v1/embeddings` | API compatible OpenAI (`input` : texte ou liste) |
| `POST /embed` | lot de textes (forme historique) |

Port 8080, sans authentification : le service ne doit être joignable que depuis les composants de la mémoire et de l'ingestion (NetworkPolicy du namespace).

## Fichiers

| Fichier | Contenu |
|---|---|
| `01-embedding-deployment.yaml` | Deployment du service ; valeurs par défaut entre `${…:-…}` |
| `01-memory-metadata.sql` | schéma `sophia.memory_metadata` : métadonnées de chaque souvenir (propriétaire, type, projet, confidentialité, provenance, validation), à côté du point dans la base vectorielle |

## Variables

| Variable | Défaut |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | `sophia-memory` |
| `${EMBEDDING_IMAGE}` | image construite dans le registre interne |
| `${EMBEDDING_MODEL_PATH}` | `/models/bge-m3` |
| `${EMBEDDING_REPLICAS}` | 1 |
| `${EMBEDDING_CPU_REQUEST}`, `${EMBEDDING_CPU_LIMIT}` | 1, 2 |
| `${EMBEDDING_MEM_REQUEST}`, `${EMBEDDING_MEM_LIMIT}` | 2Gi, 4Gi |

## Procédure (l'administrateur)

1. Image : build Docker du service, avec le jeton Hugging Face en argument de build (Secret du build, jamais dans le dépôt).
2. `envsubst` sur `01-embedding-deployment.yaml` (ou valeurs par défaut), `--dry-run=server`, puis `apply`.
3. Vérifier : pod prêt, `GET /health` donne la dimension 1 024, un `POST /v1/embeddings` depuis un pod autorisé rend un vecteur.

**Suite** : stockage propre au service et ingestion des documents ; le volume d'un cache éventuel se dimensionnera sur la première ingestion réelle, pas avant.
