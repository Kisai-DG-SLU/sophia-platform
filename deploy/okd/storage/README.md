# Stockage objet S3 commun (`sophia-storage`)

Un stockage objet compatible S3, commun à la plateforme : l'application de fichiers de la bureautique d'abord, puis la mémoire (RAG) et les modules, chacun avec son identité et son seau. Le logiciel est **SeaweedFS** en mode `weed mini` : maître, volume, filer et passerelle S3 dans un seul processus, prévu pour un nœud en production. MinIO, envisagé d'abord, n'est plus maintenu (dépôt archivé, plus d'image publiée).

```
navigateur (VPN) ──PUT présigné──▶ Route (reencrypt) ──┐
application de fichiers ──────────────────────────────┤──▶ Service s3 :9000 (TLS) ──▶ pod s3 :8443
Job d'initialisation ──────────────────────────────────┘        sortie : DNS seulement
```

| Usage | Adresse |
|---|---|
| Interne (services) | `https://s3.sophia-storage.svc:9000`, TLS par certificat de service OKD (autorité : ConfigMap annoté `inject-cabundle`, clé `service-ca.crt`) |
| Externe (navigateur, VPN seulement) | `https://${S3_HOST}`, Route reencrypt |

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Logiciel | SeaweedFS `weed mini`, **image figée par empreinte**, `IfNotPresent` | maintenu, un seul processus sur un nœud ; un redémarrage ne tire jamais une autre version |
| Volume | volume logique XFS dédié, PV local et PVC **désignés l'un l'autre** (`claimRef` + `volumeName`), `Retain` | les données survivent à la suppression des objets ; aucune autre PVC ne prend ce volume ; XFS s'agrandit à chaud |
| Déploiement | `Recreate`, une réplique | volume `ReadWriteOnce` : jamais deux SeaweedFS sur le même répertoire |
| Exposition | la passerelle S3 seule, en TLS (8443) ; maître, filer, volume, gRPC, administration et la passerelle en HTTP restent **internes au pod** | weed écoute aussi en HTTP dans le pod : la NetworkPolicy n'ouvre que le port TLS |
| Fonctions fermées | WebDAV, Iceberg, Lance ; seaux créés par l'administration seulement (`-s3.autoCreateBucket=false`) ; pas de suppression d'un seau non vide | la surface exposée se limite à l'API S3 utile |
| Administration interne | gardée, protégée par mot de passe (variable `WEED_ADMIN_PASSWORD`, Secret `s3-admin`) | sans elle, le travailleur de maintenance (nettoyage, rééquilibrage) tourne en boucle sur une connexion refusée ; une variable plutôt qu'un argument, qu'on lirait dans la liste des processus du nœud |
| Identités | une identité `admin`, puis **une par application, limitée à son seau** (`Read:fichiers`, `Write:fichiers`…) ; aucune identité anonyme | une application ne voit ni ne crée d'autre seau |
| Seau `fichiers` | versioning activé, CORS limitée à l'origine de l'application de fichiers (GET, PUT, HEAD), politique `ProtegerVersions` | le navigateur envoie directement par PUT présigné ; une écriture ou une suppression reste réversible |
| Corbeille | cycle de vie `corbeille-30-jours` : une version non courante expire 30 jours après avoir été remplacée (`NoncurrentDays: 30`), un marqueur de suppression resté seul est retiré (`ExpiredObjectDeleteMarker`) ; la version courante n'expire jamais | une suppression ou un écrasement se rattrape pendant 30 jours, sans que les anciennes versions remplissent le volume ; la tâche quotidienne de `weed mini` l'exécute |
| Politique de seau | refus explicite, pour l'identité de l'application seule, de suspendre le versioning, de changer la CORS, le cycle de vie ou la politique, et de supprimer une version | sans elle, le droit `Write` de SeaweedFS couvrirait tout cela ; avec le principal `*`, l'admin serait bloqué aussi, sans retour possible |
| Réseau | `default-deny` en **entrée et en sortie** ; entrée 8443 depuis le routeur, le namespace de l'espace de travail et le Job d'initialisation ; sortie DNS seulement | le stockage n'a besoin ni d'Internet ni d'un autre service |
| Télémétrie | `-master.telemetry=false` | objectif 100 % local ; de toute façon, la sortie fermée l'aurait empêchée de partir |
| Liens de service | `enableServiceLinks: false`, sur le pod et sur le Job | voir les leçons : sans cela, le pod ne démarre pas |
| Ressources | 100m et 256 Mi demandés, 2 CPU et 2 Gi au plus ; quota du namespace 3 CPU, 3 Gi, 4 pods | le stockage est un service de fond, sans pointe attendue |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace.yaml` | namespace, `ResourceQuota`, `LimitRange` |
| `01-storage.yaml` | PV local et PVC désignés l'un l'autre |
| `02-seaweedfs.yaml` | Deployment, Service TLS (certificat de service), ConfigMap de l'autorité de service |
| `03-network.yaml` | refus par défaut en entrée et en sortie, entrée de la passerelle, DNS, sortie du Job |
| `04-route.yaml` | Route reencrypt, délai de 900 s pour les gros fichiers |
| `05-init-job.yaml` | réglage rejouable du seau : versioning, CORS, politique |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${S3_HOST}` | nom DNS de l'API S3, résolu vers l'adresse du VPN | `s3.apps.example.org` |
| `${FILES_ORIGIN}` | origine exacte de l'application de fichiers (CORS) | `https://files.apps.example.org` |
| `${WORKSPACE_NAMESPACE}` | namespace de l'application de fichiers | `workspace` |
| `${NODE_NAME}` | nœud qui porte le volume (`oc get nodes`) | `node-0` |
| `${S3_MOUNT_POINT}` | point de montage du volume sur le nœud | `/var/mnt/s3` |
| `${S3_SIZE}` | taille du PV et de la PVC | `200Gi` |
| `${S3_PRIORITY_CLASS}` | classe de priorité des services de fond ([`../cluster/`](../cluster/)) | `sophia-agents` |
| `${SEAWEEDFS_VERSION}`, `${SEAWEEDFS_DIGEST}` | version et empreinte de l'image SeaweedFS | `4.48`, `sha256:…` |
| `${AWSCLI_VERSION}`, `${AWSCLI_DIGEST}` | version et empreinte de l'image du client S3 du Job | `2.37.9`, `sha256:…` |

Le Job contient des variables du shell (`$A`) : la substitution nomme donc ses variables, `envsubst '${S3_HOST} ${FILES_ORIGIN} …'`, et jamais un `envsubst` sans liste, qui viderait aussi `$A`.

## Secrets (jamais versionnés)

| Secret | Namespace | Clés |
|---|---|---|
| `s3-config` | `sophia-storage` | `s3.json` : identités `admin` et une par application, avec leurs clés |
| `s3-admin` | `sophia-storage` | `access-key`, `secret-key` (identité admin, pour le Job), `admin-password` (administration interne) |
| `s3-tls` | `sophia-storage` | créé par OKD (annotation du Service) |

Les valeurs sont générées sur place et passent **par un tube**, jamais par `--from-literal`, qui les mettrait dans les arguments d'`oc`, visibles par `ps`. `printf` est une commande interne du shell : ses arguments ne sont pas visibles.

## Procédure (l'administrateur)

Depuis un clone propre et à jour du dépôt interne ; chemins relatifs à `deploy/okd/storage/`. Une étape à la fois ; chaque `oc apply` est précédé d'un `oc diff` relu en entier.

1. **Volume sur le nœud** : volume logique, XFS, point de montage, ligne dans `/etc/fstab`, montage, puis contexte SELinux des conteneurs (`chcon -t container_file_t ${S3_MOUNT_POINT}`) ; procédure et pièges dans [`../../stockage-persistant.md`](../../stockage-persistant.md). Attendu : `findmnt ${S3_MOUNT_POINT}` montre le volume en `xfs`, `df -h` la taille prévue.
2. **Namespace et volume** : `00-namespace.yaml`, `01-storage.yaml`. Attendu : `s3-data` est `Pending` (`WaitForFirstConsumer`) ou `Bound` sur `pv-sophia-s3`.
3. **Secrets**, valeurs générées sur place, jamais affichées ni écrites dans un fichier :
   ```bash
   export A_K=$(openssl rand -hex 12) A_S=$(openssl rand -hex 24) F_K=$(openssl rand -hex 12) F_S=$(openssl rand -hex 24) ADM_PW=$(openssl rand -hex 24)
   python3 -c 'import json,os; e=os.environ; print(json.dumps({"identities":[{"name":"admin","credentials":[{"accessKey":e["A_K"],"secretKey":e["A_S"]}],"actions":["Admin","Read","List","Tagging","Write"]},{"name":"fichiers","credentials":[{"accessKey":e["F_K"],"secretKey":e["F_S"]}],"actions":["Read:fichiers","Write:fichiers","List:fichiers","Tagging:fichiers"]}]}))' | oc -n sophia-storage create secret generic s3-config --from-file=s3.json=/dev/stdin
   printf 'access-key=%s\nsecret-key=%s\nadmin-password=%s\n' "$A_K" "$A_S" "$ADM_PW" | oc -n sophia-storage create secret generic s3-admin --from-env-file=/dev/stdin
   unset A_K A_S F_K F_S ADM_PW
   ```
   Attendu : deux Secrets, avec 1 et 3 clés.
4. **Réseau, puis SeaweedFS** : `03-network.yaml`, puis `02-seaweedfs.yaml` et `oc -n sophia-storage rollout status deploy/s3`. Attendu : pod prêt ; le journal annonce la passerelle S3 en HTTPS sur 8443, sans erreur fatale. Quelques « connection refused » du travailleur de maintenance au démarrage sont normaux : il attend l'administration.
5. **Route** : `04-route.yaml`.
6. **Réglage du seau** : `05-init-job.yaml`, puis `oc -n sophia-storage wait --for=condition=complete job/s3-init` et son journal. Attendu : `"Status": "Enabled"` pour le versioning, la règle CORS avec `${FILES_ORIGIN}`, la politique `ProtegerVersions`, puis la règle `corbeille-30-jours`. La première exécution du cycle de vie vient au passage quotidien de la tâche de maintenance. Pour rejouer : supprimer le Job, puis l'appliquer de nouveau.
7. **Contrôle par le vrai chemin**, depuis un poste du VPN : `curl -s -o /dev/null -w '%{http_code}\n' https://${S3_HOST}/fichiers/`. Attendu : **`403`** : la Route, le TLS de bout en bout et la passerelle répondent, et l'accès anonyme est refusé.

Les clés de l'identité de l'application sont recopiées dans le Secret de l'application, dans son namespace, à son propre déploiement : lues dans `s3-config` vers des variables du shell, sans affichage, passées par un tube, puis `unset`.

**Contrôles faits avant la mise en service**, sur un binaire de la même version avec les mêmes options : l'identité de l'application écrit, lit et liste ses versions (deux écritures d'une clé donnent deux versions) ; elle ne crée pas de seau, ne touche pas un autre seau et ne peut pas défaire les protections ; une lecture anonyme reçoit 403 ; un PUT présigné passe ; le préflight CORS est accepté pour l'origine de l'application et refusé pour une autre ; un seau non vide ne se supprime pas.

## Retour arrière

Tant que rien ne dépend du stockage : supprimer la Route, le Job et `02-seaweedfs.yaml`. Les données restent sur le volume (PV en `Retain`). Ensuite, chaque consommateur a ses données dedans : un retour arrière se limite à revenir à la version précédente d'un gabarit, puis `oc apply`.

## Leçons

- **Liens de service** : Kubernetes injecte pour chaque Service du namespace des variables comme `S3_PORT=tcp://<adresse>:9000`. SeaweedFS lit les variables d'environnement comme des options (`S3_PORT` → `-s3.port`) : le pod est parti en `CrashLoopBackOff` (`invalid value "tcp://…" for … s3.port`). Correctif : `enableServiceLinks: false`. Un essai local, sans Service, ne pouvait pas le montrer.
- **Une option se vérifie dans l'aide de la version déployée** : `-telemetry=false`, repris d'un message du journal, n'existe pas en mode mini (« flag provided but not defined ») et a provoqué un second `CrashLoopBackOff` ; l'option est `-master.telemetry=false`. Toutes les options du Deployment sont maintenant contrôlées dans `weed mini -h`.
- **Secrets par tube** : une première version créait `s3-admin` avec `--from-literal`, donc avec les valeurs dans les arguments d'`oc`. Corrigé avant usage.
- **Refus par défaut en sortie aussi** : la télémétrie annoncée au démarrage n'aurait pas pu sortir ; c'est la sortie fermée, pas l'option, qui garantit le 100 % local.

## Suite

- **Nouveau consommateur** (mémoire, modules) : une identité dans `s3-config`, limitée à son seau ; une entrée dans `03-network.yaml` ; une politique de seau comme `ProtegerVersions` si le seau est versionné.
- **Plusieurs nœuds** : des `weed volume` ajoutés au maître, ou des composants séparés.
- **Montée de version** : une nouvelle empreinte dans `02-seaweedfs.yaml`, options relues dans `weed mini -h` de cette version, puis `oc diff` et `apply` ; les données restent compatibles.
