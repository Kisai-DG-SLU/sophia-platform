# Stockage persistant : préparation de l'hôte

Les manifestes de ce dépôt déclarent des `PersistentVolume` de type `local:`. Un volume local ne crée rien : il désigne un chemin du système de fichiers du nœud, qui doit donc déjà exister et être monté au moment où le manifeste est appliqué.

Si le point de montage est absent, le pod reste `Pending` indéfiniment, et aucune erreur ne désigne la vraie cause. C'est le piège le plus courant de ce type de volume, et la raison pour laquelle la préparation de l'hôte est une étape à part entière.

## Règle : un volume logique dédié par donnée qui grossit

Une donnée qui grossit (base relationnelle, base vectorielle, stockage objet, bus) a son **volume logique XFS dédié**, monté sous `/var/mnt/<nom>`, et non un répertoire de `/var` du nœud :

- elle ne remplit pas `/var`, dont dépendent le système, le registre d'images et les journaux du nœud ;
- elle **s'agrandit à chaud**, sans arrêt ni copie (voir plus bas) ;
- son occupation est **mesurée et alertée** à 80 % puis 90 % par l'exporteur du nœud ([`okd/monitoring/`](okd/monitoring/)), qui suit `/var` et chaque montage de `/var/mnt`.

## Ce que chaque composant demande

Deux questions distinctes, et la seconde est celle qu'on oublie : le composant a-t-il besoin d'un stockage persistant, et si oui, de combien. La taille ne se déduit pas du besoin, elle se justifie.

État vérifié le 25/10/2026, par lecture du cluster.

| Composant | Namespace | Persistant | Taille | Support | Base de la taille |
|---|---|---|---|---|---|
| PostgreSQL 18 (toutes les bases) | `${NS_CORE}` | oui | 20Gi | **volume logique dédié** | environ 190 Mo de données à la migration ; hypothèse haute à un an sous 9 Go sans rétention, environ 2 Go avec ; voir `okd/core/postgres18/` |
| Qdrant | `${NS_MEMORY}` | oui | 20Gi | **volume logique dédié** | 6 à 8 Ko par segment ; l'optimisation demande jusqu'à deux fois la place ; collection encore vide |
| Stockage objet S3 (SeaweedFS) | `sophia-storage` | oui | 200Gi | **volume logique dédié** | documents de la bureautique et leurs versions (corbeille de 30 jours) ; voir `okd/storage/` |
| RabbitMQ | `${NS_CORE}` | oui | 5Gi | répertoire du nœud, lié nommément (`claimRef` + `volumeName`) | événements des délégations et lettres mortes ; voir `okd/core/rabbitmq/` |
| Forgejo | `${NS_GIT}` | oui | 50Gi | **volume logique dédié** | dépôts et base SQLite locale |
| Neo4j | `${NS_MEMORY}` | oui | 10Gi | répertoire du nœud, 0 réplique | graphe à construire, aucune donnée ; image figée, en attente |
| Service d'embedding | `${NS_MEMORY}` | oui | 5Gi | répertoire du nœud | cache et modèle, pas de corpus |
| Espace de travail | `${NS_APPS}` | oui | 20Gi | répertoire du nœud, consommateur arrêté | préproduction, notebooks, webapps, API |
| LiteLLM | `${NS_CORE}` | non | `emptyDir` | sans stockage | configuration et journaux, rien à conserver (ses données sont dans PostgreSQL) |
| Assistant de code (Dionysos) | `${NS_AGENTS}` | non | `emptyDir` + dépôt Git privé | restauré à chaque création du pod | configuration et historique repoussés régulièrement vers un dépôt dédié (voir `okd/hermes-system/`) |

L'ancienne instance PostgreSQL 15 vivait dans un répertoire de `/var` ; la base vectorielle aussi, partagée avec d'autres services. Toutes deux ont été déplacées sur leur volume dédié, et les anciens répertoires sont gardés une semaine pour un retour arrière avant d'être supprimés.

Les namespaces sont variables pour que l'exemple soit réutilisable :

| Variable | Rôle |
|---|---|
| `${NS_CORE}` | orchestration, base relationnelle, routage |
| `${NS_MEMORY}` | base vectorielle, graphe, embeddings |
| `${NS_GIT}` | dépôt de code et de spécifications |
| `${NS_APPS}` | interfaces et environnements de travail |
| `${NS_AGENTS}` | système d'agents |

**Ces tailles sont des recommandations de départ, pas des normes.** Elles conviennent à un POC et se révisent avec le besoin. La croissance s'estime **par usage prévu** (par appel au modèle, par échange, par document), avec des hypothèses basse, moyenne et haute, et non d'après le volume actuel, presque nul. Ce qui compte, c'est que la taille soit écrite et que sa base soit elle-même vérifiable.

## À vérifier avant de commencer

| Contrainte | Conséquence |
|---|---|
| `storageClassName` vide ou `local-storage` sans provisionneur | aucun provisionnement automatique : le PV se crée à la main |
| PV et PVC désignés l'un l'autre (`claimRef` + `volumeName`) | aucune autre PVC ne prend le volume |
| `persistentVolumeReclaimPolicy: Retain` | supprimer le PV ne touche pas aux données |

## Procédure

Sur le nœud qui portera le pod :

```bash
sudo vgs ${VG_NAME}
sudo lvcreate -L ${LV_SIZE} -n ${LV_NAME} ${VG_NAME}
sudo mkfs.xfs /dev/${VG_NAME}/${LV_NAME}
sudo mkdir -p ${MOUNT_POINT}
echo "/dev/${VG_NAME}/${LV_NAME} ${MOUNT_POINT} xfs defaults 0 0" | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount ${MOUNT_POINT}
sudo chcon -t container_file_t ${MOUNT_POINT}
findmnt ${MOUNT_POINT} && df -h ${MOUNT_POINT}
```

Le premier contrôle donne la place libre du groupe de volumes. Le `chcon` donne au point de montage le contexte SELinux des conteneurs : sans lui, le pod démarre mais ne peut pas écrire.

Les variables à fournir :

| Variable | Rôle |
|---|---|
| `${VG_NAME}` | groupe de volumes existant sur le nœud |
| `${LV_NAME}` | nom du volume logique |
| `${LV_SIZE}` | taille, par exemple `20G` |
| `${MOUNT_POINT}` | chemin de montage, sous `/var/mnt`, repris dans le champ `local.path` du PV |

## Vérification

`findmnt` doit montrer le volume en `xfs` sur le point de montage, et `df -h` la taille prévue. Ensuite, appliquer le `PersistentVolume`, puis la `PersistentVolumeClaim`, et lire l'état :

```bash
oc get pvc
```

`Bound` : le stockage est en place. `Pending` après le montage : le `capacity` du PV est inférieur à la demande de la PVC, ou le `storageClassName` ne correspond pas.

## Agrandir un volume

Un volume logique XFS **s'agrandit à chaud**, monté et en service :

```bash
sudo lvextend -r -L +10G ${VG_NAME}/${LV_NAME}
df -h ${MOUNT_POINT}
```

`-r` agrandit le système de fichiers dans la foulée. Pour un volume `local`, la taille déclarée du PV et de la PVC n'est qu'une étiquette : le pod voit la place réelle. On met quand même à jour `capacity` dans le dépôt, pour qu'il reste exact ; c'est sans effet sur le pod.

Un **répertoire de `/var`**, lui, ne s'agrandit pas : le déplacer sur un volume dédié demande un arrêt et une copie (arrêter le pod, copier en gardant les droits, comparer les tailles, basculer le PV, relancer, garder l'ancien répertoire quelques jours). C'est le moment de le faire tant que la donnée est petite.

## Dimensionner un volume de modèles

Un volume de modèles se dimensionne sur le poids du fichier à la quantification choisie, plus la marge pour une seconde variante du même ordre de grandeur. Le calcul se fait sur la mesure réelle du téléchargement, jamais sur une estimation.

## Ce que l'inventaire révèle

Un inventaire fait une seule fois révèle des accidents que l'affichage des pods ne montre jamais : un volume préparé sur l'hôte sans manifeste, un manifeste sans consommateur, un volume lié à un chemin inexistant, une classe supprimée encore référencée, un nom qui ne correspond plus à ce que la ressource sert.

Aucun de ces états n'apparaît dans `oc get pods`. Ils apparaissent dès qu'on demande la liste des volumes et la liste des demandes, et qu'on les compare.
