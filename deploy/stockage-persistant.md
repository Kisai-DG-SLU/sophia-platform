# Stockage persistant : preparation de l'hote

Les manifestes de ce depot declarent des `PersistentVolume` de type `local:`. Un volume local ne cree rien : il designe un chemin du systeme de fichiers du noeud, qui doit donc deja exister et etre monte au moment ou le manifeste est applique.

Si le point de montage est absent, le pod reste `Pending` indefiniment, et aucune erreur ne designe la vraie cause. C'est le piege le plus courant de ce type de volume, et la raison pour laquelle la preparation de l'hote est une etape a part entiere.

## Ce que chaque composant demande

Deux questions distinctes, et la seconde est celle qu'on oublie. Le composant a-t-il besoin d'un stockage persistant, et si oui, de combien. La taille ne se deduit pas du besoin, elle se justifie.

Etat verifie le 27/09/2026, par lecture du cluster.

| Composant | Namespace | Persistant | Taille | Etat | Base de la taille |
|---|---|---|---|---|---|
| PostgreSQL | `${NS_CORE}` | oui | 10Gi | lie | 4 utilisateurs, journaux, droits. Non extensible, minimum de depart |
| Forgejo | `${NS_GIT}` | oui | 50Gi | lie | depots et base SQLite locale, 6 Mo aujourd'hui |
| Qdrant | `${NS_MEMORY}` | oui | 20Gi | lie | points x dimensions x 4 octets, a calculer des que l'ingestion produit |
| Neo4j | `${NS_MEMORY}` | oui | 10Gi | lie, non monte | graphe a construire, aucune donnee |
| Service d'embedding | `${NS_MEMORY}` | oui | 5Gi | lie | cache et modele, pas de corpus |
| Espace de travail | `${NS_APPS}` | oui | 20Gi | lie, consumer arrete | preproduction, notebooks, webapps, API |
| LiteLLM | `${NS_CORE}` | non | `emptyDir` | sans stockage | configuration et journaux, rien a conserver |
| RabbitMQ | `${NS_CORE}` | prevu | 5Gi demandes | en attente | files inter-agents, a la creation |
| Agent de controle | `${NS_AGENTS}` | prevu | 2Gi demandes | en attente | regles du controle, a la creation |

Les namespaces sont variables pour que l'exemple soit reutilisable :

| Variable | Role |
|---|---|
| `${NS_CORE}` | orchestration, base relationnelle, routage |
| `${NS_MEMORY}` | base vectorielle, graphe, embeddings |
| `${NS_GIT}` | depot de code et de specifications |
| `${NS_APPS}` | interfaces et environnements de travail |
| `${NS_AGENTS}` | systeme d'agents |

**Ces tailles sont des recommandations de depart, pas des normes.** Elles convenience a un POC et se revisent avec le besoin. Aucune base de la colonne de droite n'est verifiee pour un systeme en production, et les journaux comme les permissions ne sont pas encore en place : une base de dix tables a l'etat quasi vide ne dit rien de sa taille dans deux ans. Ce qui compte ici, c'est que la taille soit ecrite, et que sa base soit elle-meme verifiable.

## A verifier avant de commencer

| Contrainte | Consequence |
|---|---|
| `storageClassName: ""` | aucune StorageClass n'est selectionnee, le PV est resolu par son nom |
| StorageClass `no-provisioner` | aucun provisionnement automatique, le PV se cree a la main |
| `ALLOWVOLUMEEXPANSION: false` | un volume ne s'agrandit pas, la taille se choisit une fois pour toutes |

## Procedure

Quatre etapes, sur le noeud qui portera le pod.

```bash
# 1. Volume logique dans le groupe de volumes existant
sudo lvcreate -L ${LV_SIZE} -n ${LV_NAME} ${VG_NAME}

# 2. Formatage
sudo mkfs.xfs /dev/${VG_NAME}/${LV_NAME}

# 3. Point de montage
sudo mkdir -p ${MOUNT_POINT}

# 4. Persistance du montage, puis montage
echo "/dev/${VG_NAME}/${LV_NAME} ${MOUNT_POINT} xfs defaults 0 0" | sudo tee -a /etc/fstab
sudo mount ${MOUNT_POINT}
```

Les variables a fournir :

| Variable | Role |
|---|---|
| `${VG_NAME}` | groupe de volumes existant sur le noeud |
| `${LV_NAME}` | nom du volume logique |
| `${LV_SIZE}` | taille, par exemple `200G` |
| `${MOUNT_POINT}` | chemin de montage, repris dans le champ `local.path` du PV |

## Verification

```bash
df -h ${MOUNT_POINT}
```

La ligne attendue affiche la taille du volume sur le point de montage. C'est le seul controle utile : si la taille est la bonne, le PV peut etre applique.

Ensuite, appliquer le `PersistentVolume`, puis la `PersistentVolumeClaim`, et lire l'etat :

```bash
oc get pvc
```

`Bound` : le stockage est en place. `Pending` apres le montage : le `capacity` du PV est inferieur a la demande de la PVC, ou le `storageClassName` ne correspond pas.

## Agrandir un volume

Quand l'expansion est interdite, la croissance n'est pas un redimensionnement, c'est un remplacement. La procedure suppose que le PV est en `Retain`, ce qui est le cas dans cet exemple.

1. Preparer un second systeme de fichiers sur l'hote, plus grand, a un nouveau point de montage
2. Creer un second PV pointant dessus, avec une capacite superieure a la demande de la PVC
3. Arreter le pod : le PV passe `Released` et ses donnees restent sur l'hote, grace a `Retain`
4. Supprimer la PVC, puis la recreer avec la taille superieure : elle se lie au nouveau PV
5. Copier les donnees de l'ancien chemin vers le nouveau, cote hote
6. Relancer le pod, puis liberer l'ancien volume une fois la copie verifiee

Les etapes 4 et 5 ne se resolvent pas seules. La copie se fait a la main, sur le noeud, et rien dans le cluster ne verifie qu'elle est terminee. C'est la raison de la marge a prevoir dans le tableau plus haut.

## Dimensionner un volume de modeles

Un volume de modeles se dimensionne sur le poids du fichier a la quantification choisie, plus la marge pour une seconde variante de meme ordre de grandeur.

La marge n'est pas un confort. L'expansion etant interdite, un volume trop petit ne se corrige pas en ajoutant de l'espace, il se corrige en remplacant le volume, avec un arret et une copie complete. Le calcul se fait donc sur la mesure reelle du telechargement, jamais sur une estimation.

## Ce que l'inventaire revele

Un inventure fait une seule fois revele des accidents que l'affichage des pods ne montre jamais : un volume prepare sur l'hote sans manifeste, un manifeste sans consommateur, un volume lie a un chemin inexistant, une classe supprimee encore referencee, un nom qui ne correspond plus a ce que la ressource sert.

Aucun de ces etats n'apparait dans `oc get pods`. Ils apparaissent des qu'on demande la liste des volumes et la liste des demandes, et qu'on les compare.
