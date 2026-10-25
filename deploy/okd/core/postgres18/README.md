# PostgreSQL 18 — instance commune (`sophia-core`)

Toutes les bases de la plateforme vivent dans **une instance PostgreSQL 18** : routeur de modèles, moteur de workflows, fournisseur d'identité, interface de discussion, modules, gestion de fichiers de la bureautique, schéma de la mémoire. Elle a remplacé une instance PostgreSQL 15, migrée base par base.

**Pourquoi la 18** : la gestion de fichiers de la bureautique range ses éléments dans un chemin `ltree` dont les étiquettes contiennent des tirets, que PostgreSQL n'accepte qu'à partir de la version 16 ; sur la 15, la création d'un dossier échouait (erreur 500), alors que les migrations passaient. Plutôt que garder une dette de version, toutes les bases sont passées à la dernière version stable.

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Une instance | toutes les bases, un rôle propriétaire par base | une seule montée de version, une seule sauvegarde, un seul volume à surveiller |
| Rôles | **aucun superutilisateur réseau** : chaque base a son rôle propriétaire (routeur de modèles, mémoire, validations humaines, chaque application) ; `postgres` reste superutilisateur, **par le socket local du pod seulement** | une application compromise ne lit que sa base ; l'ancien rôle superutilisateur partagé n'est pas recréé |
| Image | sclorg PostgreSQL 18, **figée par empreinte**, `IfNotPresent` ; un build de quelques jours, pas le tout dernier | un redémarrage ne tire jamais une autre version ; recul sur l'image |
| Extensions | vérifiées dans les couches de l'image avant de l'adopter (`ltree`, `pg_trgm`, `unaccent`, `pgcrypto`, `uuid-ossp`, `btree_gin`, `vector`…) ; les extensions « trusted » sont créées par le propriétaire de la base | aucune montée bloquée par une extension absente, aucun superutilisateur pour les créer |
| Volume | **volume logique XFS dédié** (20 Go au départ), monté sous `/var/mnt`, PV local et PVC désignés l'un l'autre, `Retain` | hors de `/var` du nœud ; s'agrandit à chaud (`lvextend -r`) ; alerte à 80 % et 90 % ([`../../monitoring/`](../../monitoring/)) |
| Déploiement | `Recreate`, sondes `pg_isready`, `enableServiceLinks: false`, classe `sophia-chat` | volume `ReadWriteOnce` ; la discussion dépend de la base |
| Entrée | une seule règle (`03-network.yaml`) pour tous les consommateurs | lisible d'un coup d'œil ; l'éditeur de documents n'y a pas accès |
| Rétention | journal détaillé du routeur de modèles : 30 jours ; moteur de workflows : 30 jours ; audit de la mémoire : 1 an ; conversations, applications et souvenirs : aucune | les journaux techniques ne grossissent pas sans fin ; les données des personnes restent à elles |

## Fichiers

| Fichier | Contenu |
|---|---|
| `01-storage.yaml` | PV local et PVC, désignés l'un l'autre |
| `02-instance.yaml` | Deployment et Service `postgres-sophia-18` |
| `03-network.yaml` | entrée 5432, par consommateur |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${PG_MOUNT_POINT}` | point de montage du volume logique | `/var/mnt/postgres-18` |
| `${PG_SIZE}` | taille déclarée (étiquette, pour un volume local) | `20Gi` |
| `${NODE_NAME}` | nœud qui porte le volume | `node-0` |
| `${PG18_DIGEST}` | empreinte de l'image retenue | `sha256:…` |
| `${WORKSPACE_NAMESPACE}` | namespace de la bureautique | `workspace` |

## Secrets (jamais versionnés)

| Secret | Clés |
|---|---|
| `postgres-sophia-18-creds` | `password` : rôle du routeur de modèles, créé par l'image |
| `postgres-18-<rôle>` | `password` : un par rôle créé par `psql` (un nom de Secret n'a pas de `_` : `sophia_rag` → `postgres-18-sophia-rag`) |

Chaque mot de passe est tiré sur place (`openssl rand -hex 24`) et passe par un tube vers `oc create secret … --from-file=password=/dev/stdin`. Le Secret est créé **avant** le rôle, et le rôle seulement si le Secret a réussi (`&&`) : un mot de passe ne se perd jamais.

## Procédure (l'administrateur)

1. **Volume sur le nœud** : volume logique, XFS, point de montage, `/etc/fstab`, montage, `chcon -t container_file_t` ([`../../../stockage-persistant.md`](../../../stockage-persistant.md)). Attendu : `findmnt` montre le volume en `xfs`.
2. **Instance** : le Secret, puis `01-storage.yaml`, `03-network.yaml`, `02-instance.yaml`. Attendu : PVC `Bound`, pod prêt, `select version()` répond `PostgreSQL 18.x`.
3. **Sauvegarde** avant chaque étape : `pg_dumpall --clean --if-exists` vers le poste d'administration ; la dernière ligne doit être `PostgreSQL database cluster dump complete`.

### Migrer une base : le rituel

Pour chaque base, une à la fois :

0. **Contrôler la sortie du consommateur, avant tout arrêt.** L'entrée de la nouvelle instance ne suffit pas : si le namespace du consommateur limite sa **sortie**, sa règle doit aussi ouvrir 5432 vers la nouvelle instance. Deux contrôles : les règles de sortie du namespace, puis **une vraie connexion TCP** depuis le pod du consommateur. Sinon, on s'arrête sans rien couper.
1. **Sauvegarde** de l'ancienne instance.
2. **Rôle copié avec son empreinte SCRAM** (`pg_dumpall --roles-only`, par un tube) : le consommateur garde son mot de passe, seule l'adresse change. Pour un rôle **neuf** (découpage d'une base, fin du superutilisateur partagé), restauration en `--no-owner --role=<propriétaire>`.
3. **Arrêt du consommateur**, pour qu'il n'écrive plus dans l'ancienne instance.
4. **`pg_dump -Fc` puis `pg_restore --exit-on-error`**, puis `analyze`.
5. **Comptage exact** des tables et des lignes des deux côtés (`count(*)` de chaque table, par `query_to_xml`). Pas `n_live_tup` : ces statistiques valent 0 sur une base restaurée ou une instance redémarrée.
6. **Bascule de l'adresse** dans le Secret ou le manifeste du consommateur (seules les clés qui contiennent l'ancien hôte changent, sans affichage), puis redémarrage.
7. **Contrôle par le vrai chemin** : l'application répond et lit ses données.

**Retour arrière d'une base** : remettre l'ancienne adresse et redémarrer le consommateur ; l'ancienne instance a gardé ses données, arrêtées à l'instant de l'arrêt du consommateur.

**Ordre suivi** : les applications d'abord (une coupure d'environ deux minutes chacune), puis le moteur de workflows (aucune exécution en cours), puis le routeur de modèles (avec le schéma de la mémoire et la base des validations humaines, sous leurs nouveaux rôles), et **le fournisseur d'identité en dernier** (arrêté par son CR, `instances: 0`, puis relancé avec la nouvelle adresse).

### Après la migration

- L'ancienne instance passe à **0 réplique**, avec une sauvegarde finale complète ; elle reste en place **7 jours** comme retour arrière.
- Ensuite, suppression par l'administrateur : Deployment, Service, PVC, PV, Secret et règles réseau de l'ancienne instance, répertoire du nœud, règles de sortie des applications vers l'ancienne instance, sauvegardes intermédiaires. La sauvegarde finale est gardée 30 jours de plus.

## Leçons

- **Contrôler la sortie autant que l'entrée.** Une application est partie en `CrashLoopBackOff` (`PoolTimeout`) à sa bascule : l'entrée de la nouvelle instance était prête, mais la règle de **sortie** de l'application n'ouvrait que l'ancienne. D'où l'étape 0 et la connexion TCP réelle. Correctif en avant (sortie élargie), sans perte : l'application n'avait rien écrit.
- **« Testé » ne vaut que pour ce qu'on a testé** : les migrations passaient sur la 15, l'écriture non.
- **Un nom de Secret est un nom DNS** : pas de `_`. Une boucle qui créait le rôle avant le Secret a perdu un mot de passe ; l'ordre est maintenant Secret, puis rôle.

## Montées de version suivantes

PG 18 est maintenue jusqu'en 2030. Méthode retenue : **`pg_upgrade --link`** sur place, par l'image de la version suivante (`POSTGRESQL_UPGRADE=hardlink`), qui embarque les binaires de la version précédente : quelques minutes de coupure, quelle que soit la taille. Le seul retour arrière est la sauvegarde complète faite juste avant. Les compatibilités (fournisseur d'identité, moteur de workflows, routeur de modèles, pilotes des applications) et les extensions se vérifient d'abord.
