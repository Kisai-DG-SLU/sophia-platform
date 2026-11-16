# Sauvegarde chiffrée (`sophia-sauvegarde`)

Les données de la plateforme sont sauvegardées **dans le cluster**, chiffrées avant d'être écrites, dans un seau dédié du [stockage objet commun](../storage/README.md). Le logiciel est **restic** : instantanés datés, dédoublonnage, chiffrement authentifié. Un namespace dédié, sans entrée ni accès Internet, lit les bases PostgreSQL, les copies préparées par la forge, la messagerie XMPP et la base vectorielle, et les Secrets des namespaces. Il écrit le tout dans un dépôt restic. Le cadre général (chiffrement côté client, copie hors site, contrôles) est dans [Sauvegarde et stockage : solutions souveraines](../../../docs/security.md#sauvegarde-et-stockage--solutions-souveraines).

**État dans l'installation de référence** : **en service depuis le 15/11**. Le premier cycle complet a été lancé à la main, l'alerte forcée a été reçue, puis la suspension des tâches a été levée. Le premier cycle de nuit **automatique** a été vérifié le 16/11 : les trois extractions et la nuit réussies, un instantané de nuit dans le dépôt, `restic check` sans erreur, aucune alerte. L'essai de restauration a tourné une fois, à la main ; le premier essai planifié est celui du dimanche suivant.

```text
02:45  extraction-forgejo  (sophia-git)         ──▶ seau export-forge   ──┐
02:50  extraction-prosody  (sophia-messagerie)  ──▶ seau export-prosody ──┤
02:55  extraction-qdrant   (sophia-memory)      ──▶ seau export-qdrant  ──┼─▶ 03:30 sauvegarde-nuit ──┐
       API du cluster : Secrets des namespaces listés ───────────────────┘                           │
PostgreSQL 18 (sophia-core) ──▶ chaque heure à :05, sauvegarde-bases ──────────────────────────────────┼─▶ restic, chiffré
                                                                                                      │   ──▶ seau sauvegardes
dimanche 08:00  essai-restauration : une base restaurée dans un PostgreSQL éphémère, contrôlée, chronométrée
```

Les heures sont celles de Paris (`timeZone: Europe/Paris` des CronJobs).

## Périmètre

| Donnée | Comment | Quand |
|---|---|---|
| Bases PostgreSQL : toutes celles qui acceptent les connexions, hors modèles | `pg_dump` de chaque base par le rôle `sauvegarde`, plus les rôles et objets globaux, **sans les mots de passe des rôles** | chaque heure, à la minute 05 |
| Forge (Forgejo) : base SQLite, `app.ini`, pièces jointes, avatars, LFS et autres données hors dépôts | extraction dans `sophia-git`, déposée dans le seau `export-forge` | extraction à 02:45, chiffrée à 03:30 |
| Messagerie XMPP (Prosody) : ses fichiers de données | archive dans `sophia-messagerie`, déposée dans `export-prosody` | 02:50, chiffrée à 03:30 |
| Base vectorielle (Qdrant) : instantané complet | par l'API de Qdrant, dans `sophia-memory`, déposé dans `export-qdrant` | 02:55, chiffré à 03:30 |
| Secrets des namespaces listés (`${SECRETS_NAMESPACES}`) | lus par l'API, sans les jetons des comptes de service, métadonnées réduites | 03:30 |

**Hors de ce dépôt restic :**
- **les dépôts git de la forge.** Dans l'installation de référence, l'export de Forgejo exclut les dépôts git. Une installation doit prévoir la copie de ses dépôts : voir [les solutions souveraines](../../../docs/security.md#sauvegarde-et-stockage--solutions-souveraines) ;
- **le stockage objet des fichiers et de la mémoire** : la sauvegarde ne lit que les seaux d'export, et son identité n'a aucun droit sur les autres seaux. Une installation prévoit leur copie de la même façon ;
- **le mot de passe du dépôt restic** : les Secrets de `sophia-sauvegarde` ne sont pas exportés. Ce mot de passe se garde hors de la plateforme, en plusieurs exemplaires ;
- **la copie hors site** : voir « Copie hors site », plus bas.

## Choix

| Choix | Valeur | Raison |
|---|---|---|
| Logiciel | restic 0.19.1, **image figée par empreinte**, servie par le registre interne | chiffrement authentifié côté client, instantanés, dédoublonnage ; le namespace n'a pas d'accès Internet |
| Dépôt | seau `sauvegardes` du stockage objet commun, **sans versionnage ni verrouillage** | `restic prune` doit pouvoir supprimer les paquets oubliés. La protection contre une suppression malveillante relève de la copie hors site |
| Chiffrement | dans le cluster, avant toute écriture ; mot de passe dans le Secret `restic-mot-de-passe`, monté en lecture seule (`0400`) | le stockage ne voit que des blocs chiffrés. Sans ce mot de passe, le dépôt est illisible |
| Bases | toutes les heures, à la minute 05 | au plus une heure de perte |
| Format des vidages | `pg_dump -Fc -Z0` (sans compression), relu par `pg_restore --list` ; propriétaires et droits gardés (pas de `--no-owner`) | restic dédoublonne d'une heure à l'autre ; un vidage illisible arrête la sauvegarde ; un schéma revient à son propriétaire |
| Rôle PostgreSQL | `sauvegarde` : connexion, membre de `pg_read_all_data`, `CONNECT` sur chaque base ; ni superutilisateur, ni contournement des règles de lignes (`BYPASSRLS`) | il lit tout, sans pouvoir rien écrire |
| Extractions | dans le namespace de chaque service, puis dépôt dans un seau interne, par une identité en écriture seule (`Write`, sans `Read` ni `List`) | un pod d'un autre namespace ne lit pas le volume d'un service : la SCC fixe le niveau SELinux au namespace |
| Forge | pod sous l'uid 1000 de Forgejo, par la SCC `lecture-forge` (uid 1000 seul, aucune capacité, racine en lecture seule, utilisable par le seul compte `export-forge`) ; volume monté en lecture seule ; copie cohérente de la base SQLite, puis `integrity_check` | `/data` appartient à l'uid 1000, en mode `0700` ; aucun droit de la forge n'est retiré ni réduit |
| Base vectorielle | instantané par l'API (`POST /snapshots`), supprimé sur Qdrant même en cas d'échec ; refusé s'il manque une collection qui a des points | aucun volume monté ; une archive incomplète ne passe pas |
| Nuit | 03:30 ; un export qui n'est pas du jour (date UTC) arrête la sauvegarde | une copie périmée ne passe pas pour fraîche |
| Secrets | un `Role` et un `RoleBinding` (`get`, `list`) par namespace listé, jamais de `ClusterRole` ; `sophia-sauvegarde` exclu | droit limité à une liste écrite ; le mot de passe restic n'entre pas dans son propre dépôt |
| Rétention | bases : 48 horaires, 7 quotidiens, 5 hebdomadaires, 12 mensuels ; nuit : 7 quotidiens, 5 hebdomadaires, 12 mensuels ; `prune` chaque nuit | `restic forget` par étiquette (`bases`, `nuit`) |
| Intégrité | `restic check --read-data-subset 2%` chaque nuit | une part des données relue chaque nuit |
| Essai de restauration | le dimanche à 08:00 : une base restaurée dans un PostgreSQL éphémère (conteneur annexe du pod), rôles d'abord, puis propriétaires des schémas et nombre de lignes de chaque table comparés au vidage ; **600 s au plus**. La plus grosse base la première semaine du mois, sinon une base tournante selon le numéro de la semaine | une sauvegarde ne compte que si elle se restaure |
| Concurrence | `concurrencyPolicy: Forbid`, `backoffLimit: 0` ; `--retry-lock 30m` | le `prune` de la nuit prend un verrou exclusif : la sauvegarde horaire suivante attend au lieu d'échouer |
| Durées | au plus 30 min (bases), 3 h (nuit), 1 h (essai) ; retard au départ admis : 15 min, 1 h, 1 h | une tâche bloquée finit en échec, donc en alerte |
| Réseau | aucune entrée ; sorties : DNS, PostgreSQL (5432), passerelle S3 (8443), API du cluster (6443) ; `EgressFirewall` qui refuse tout le reste | rien ne sort du cluster |
| Jetons | `automountServiceAccountToken: false` partout, sauf pour la nuit (l'export des Secrets passe par l'API) ; `enableServiceLinks: false` | un pod sans besoin de l'API n'a pas de jeton |
| Ressources | quota du namespace : 4 CPU et 6 Gi en limites, 4 pods ; volume de travail en `emptyDir` (10 Gi, 30 Gi, 20 Gi) | rien ne reste en clair après le passage |
| Alertes | cinq par CronJob : en échec, en retard (2 h, 26 h, 8 jours), jamais réussie, absente, suspendue | une sauvegarde n'est acquise qu'avec un contrôle automatique qui alerte |

## Fichiers

| Fichier | Namespace | Contenu |
|---|---|---|
| `00-namespace.yaml` | `sophia-sauvegarde` | namespace, quota, valeurs par défaut, refus par défaut et sorties, `EgressFirewall`, compte `sauvegarde` |
| `01-images.yaml` | `sophia-sauvegarde` | six ImageStreams figés par empreinte : restic, rclone, PostgreSQL 18, Python, `oc`, client S3 |
| `02-lecture-secrets.yaml` | un namespace de la liste | `Role` et `RoleBinding` de lecture des Secrets ; rendu une fois par namespace |
| `03-scripts.yaml` | `sophia-sauvegarde` | scripts des sauvegardes et de l'essai ; ConfigMap de l'autorité de service d'OKD |
| `04-cronjobs.yaml` | `sophia-sauvegarde` | CronJobs `sauvegarde-bases`, `sauvegarde-nuit`, `essai-restauration` |
| `05-restic-init.yaml` | `sophia-sauvegarde` | Job de création du dépôt restic, une seule fois |
| `06-scc-lecture-forge.yaml` | cluster, `sophia-git` | SCC `lecture-forge`, son `ClusterRole` d'usage, le `RoleBinding` du compte `export-forge` |
| `07-extraction-forgejo.yaml` | `sophia-git` | compte, droit de tirer les images, sortie, scripts, CronJob `extraction-forgejo` |
| `08-extraction-prosody.yaml` | `sophia-messagerie` | compte, droit de tirer les images, sortie, scripts, CronJob `extraction-prosody` |
| `09-extraction-qdrant.yaml` | `sophia-memory` | compte, droit de tirer les images, sortie, entrée sur Qdrant, scripts, CronJob `extraction-qdrant` |
| `10-seaux.yaml` | `sophia-storage` | Job des quatre seaux, rejouable |
| `11-alertes.yaml` | les quatre namespaces | une `PrometheusRule` par namespace, cinq alertes par CronJob |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${LAN_NODE_IP}` | adresse du nœud : le Service `kubernetes` y aboutit, port 6443 | `192.0.2.10` |
| `${SERVICE_NETWORK}`, `${POD_NETWORK}` | réseaux des Services et des pods du cluster | `172.30.0.0/16`, `10.128.0.0/14` (défauts d'OKD) |
| `${PG18_DIGEST}` | empreinte de l'image de l'instance [PostgreSQL 18](../core/postgres18/README.md) : `pg_dump` doit être de la même version | `sha256:…` |
| `${OKD_CLI_IMAGE}` | image de `oc` de la version du cluster, celle de `openshift/cli:latest` | `quay.io/okd/scos-content@sha256:…` |
| `${AWSCLI_VERSION}`, `${AWSCLI_DIGEST}` | version et empreinte de l'image du client S3, comme pour le [stockage](../storage/README.md) | `2.37.9`, `sha256:…` |
| `${SECRETS_NAMESPACES}` | namespaces dont les Secrets sont exportés, séparés par des espaces, **sans** `sophia-sauvegarde` | `sophia-core sophia-git sophia-memory sophia-messagerie sophia-storage` |
| `${NAMESPACE_LU}` | un namespace de cette liste, pour le rendu de `02-lecture-secrets.yaml` (posé par la boucle de l'étape 2) | `sophia-core` |
| `${SUSPENDRE}` | `true` à la première mise en service, `false` une fois le premier cycle contrôlé | `true` |
| `${FORGEJO_PVC}` | PVC du volume `/data` de Forgejo, dans `sophia-git` | `forgejo-data` |
| `${PROSODY_PVC}` | PVC des données de Prosody, dans `sophia-messagerie` | `prosody-data` |

Les scripts des gabarits ont leurs propres `$` : chaque rendu nomme donc ses variables, `envsubst '${…}'`, jamais un `envsubst` sans liste. `03-scripts.yaml`, `05-restic-init.yaml`, `06-scc-lecture-forge.yaml` et `11-alertes.yaml` n'ont aucune variable.

## Secrets (jamais versionnés)

| Secret | Namespace | Clés | Créé à |
|---|---|---|---|
| `sauvegarde-s3` | `sophia-sauvegarde` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | étape 3 |
| `export-forge-s3` | `sophia-git` | idem | étape 3 |
| `export-prosody-s3` | `sophia-messagerie` | idem | étape 3 |
| `export-qdrant-s3` | `sophia-memory` | idem | étape 3 |
| `postgres-sauvegarde` | `sophia-sauvegarde` | `password` (48 caractères hexadécimaux) | étape 4 |
| `restic-mot-de-passe` | `sophia-sauvegarde` | `password` | étape 5 |
| `qdrant-cle` | `sophia-memory` | `cle` : celui que Qdrant lit déjà ([mémoire](../memory/memoire/README.md)) | existant |
| `s3-config`, `s3-admin` | `sophia-storage` | ceux du [stockage](../storage/README.md) | existants |

Les valeurs sont tirées sur place et passent **par un tube**, jamais en argument. Le mot de passe restic, lui, doit être gardé hors de la plateforme : il est saisi par `read -rs`, sans affichage.

## Procédure (l'administrateur)

Prérequis : le [stockage objet](../storage/README.md), [PostgreSQL 18](../core/postgres18/README.md), Forgejo dans `sophia-git`, Prosody dans `sophia-messagerie`, Qdrant et son Secret `qdrant-cle` dans `sophia-memory`, et la [supervision](../monitoring/README.md), qui route les alertes `sophia: oui`. Commandes depuis ce dossier, avec les droits d'administration du cluster. Une étape à la fois ; chaque contrôle se relit avant l'étape suivante. Sur macOS, remplacer `sha256sum` par `shasum -a 256`.

**Étape 0 — Variables.** Relever les valeurs propres à l'installation :

```bash
oc -n openshift get istag cli:latest -o jsonpath='{.image.dockerImageReference}{"\n"}'
oc -n sophia-core get deploy postgres-sophia-18 -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
oc -n sophia-git get pvc
oc -n sophia-messagerie get pvc
```

Attendu : l'image de `oc` (c'est `${OKD_CLI_IMAGE}`), l'image de PostgreSQL et son empreinte (`${PG18_DIGEST}`), puis les PVC de Forgejo et de Prosody. Exporter ensuite chaque variable du tableau (`export NOM=valeur`), avec `SUSPENDRE=true`, puis :

```bash
env | grep -E '^(LAN_NODE_IP|SERVICE_NETWORK|POD_NETWORK|PG18_DIGEST|OKD_CLI_IMAGE|AWSCLI_VERSION|AWSCLI_DIGEST|SECRETS_NAMESPACES|SUSPENDRE|FORGEJO_PVC|PROSODY_PVC)='
```

Attendu : onze lignes, aucune vide.

**Étape 1 — Namespace et images :**

```bash
envsubst '${LAN_NODE_IP} ${SERVICE_NETWORK} ${POD_NETWORK}' < 00-namespace.yaml | oc apply --dry-run=server -f -
envsubst '${LAN_NODE_IP} ${SERVICE_NETWORK} ${POD_NETWORK}' < 00-namespace.yaml | oc apply -f -
envsubst '${PG18_DIGEST} ${OKD_CLI_IMAGE} ${AWSCLI_VERSION} ${AWSCLI_DIGEST}' < 01-images.yaml | oc apply -f -
oc -n sophia-sauvegarde get istag
```

Attendu : sept objets `created (server dry run)`, puis `created` ; six ImageStreams ; puis six ImageStreamTags, chacun avec son empreinte. Un tag sans image : relire l'empreinte de son ImageStream.

**Étape 2 — Lecture des Secrets**, un `Role` et un `RoleBinding` par namespace de la liste, puis le contrôle par le compte lui-même :

```bash
for ns in $(echo "$SECRETS_NAMESPACES"); do NAMESPACE_LU=$ns envsubst '${NAMESPACE_LU}' < 02-lecture-secrets.yaml | oc apply -f -; done
for ns in $(echo "$SECRETS_NAMESPACES"); do echo "$ns : $(oc auth can-i list secrets -n $ns --as=system:serviceaccount:sophia-sauvegarde:sauvegarde)"; done
oc auth can-i list secrets -n sophia-sauvegarde --as=system:serviceaccount:sophia-sauvegarde:sauvegarde
```

Attendu : deux `created` par namespace ; puis `yes` pour chacun ; puis `no` pour `sophia-sauvegarde`.

**Étape 3 — Identités et seaux S3.** Dans l'installation de référence, cette étape a été jouée en plusieurs fois, au fil des extractions ajoutées ; elle est donnée ici en un seul état final, qui n'a pas été rejoué tel quel. Relire chaque contrôle avant la commande suivante. D'abord une copie de la configuration des identités, **dans le cluster** ; puis les quatre Secrets, remplis par `openssl` dans un tube :

```bash
oc -n sophia-storage get secret s3-config -o json | python3 -c 'import json, sys; d = json.load(sys.stdin); d["metadata"] = {"name": "s3-config-avant-sauvegarde", "namespace": d["metadata"]["namespace"]}; d.pop("status", None); print(json.dumps(d))' | oc create -f -
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-sauvegarde create secret generic sauvegarde-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-git create secret generic export-forge-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-messagerie create secret generic export-prosody-s3 --from-env-file=/dev/stdin
{ printf 'AWS_ACCESS_KEY_ID='; openssl rand -hex 12; printf 'AWS_SECRET_ACCESS_KEY='; openssl rand -hex 24; } | oc -n sophia-memory create secret generic export-qdrant-s3 --from-env-file=/dev/stdin
```

Attendu : `secret/s3-config-avant-sauvegarde created`, puis quatre `created`. Ensuite les quatre identités, tirées de ces Secrets et ajoutées à `s3-config` par des fichiers temporaires privés, effacés dans le même bloc ; le nouveau `s3.json` n'est envoyé que si le script a réussi. Puis un contrôle de concordance par empreintes tronquées, qui ne sont jamais affichées :

```bash
( umask 077; T=$(mktemp -d); oc -n sophia-storage get secret s3-config -o jsonpath='{.data.s3\.json}' | base64 -d > "$T/s3.json" && oc -n sophia-sauvegarde get secret sauvegarde-s3 -o json > "$T/a.json" && oc -n sophia-git get secret export-forge-s3 -o json > "$T/b.json" && oc -n sophia-messagerie get secret export-prosody-s3 -o json > "$T/c.json" && oc -n sophia-memory get secret export-qdrant-s3 -o json > "$T/d.json" && python3 -c 'import base64, json, sys; c = json.load(open(sys.argv[1])); cl = lambda f: tuple(base64.b64decode(json.load(open(f))["data"][x]).decode() for x in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")); cles = [cl(f) for f in sys.argv[2:6]]; assert all(len(k) == 24 and len(s) == 48 for k, s in cles), "clés inattendues"; noms = [i["name"] for i in c["identities"]]; nouveaux = ["sauvegarde", "export-forge", "export-prosody", "export-qdrant"]; assert not set(nouveaux) & set(noms), "identité déjà présente"; lect = [v + ":" + s for s in nouveaux[1:] for v in ("Read", "List")]; droits = [lect + ["Read:sauvegardes", "Write:sauvegardes", "List:sauvegardes"]] + [["Write:" + n] for n in nouveaux[1:]]; [c["identities"].append({"name": n, "credentials": [{"accessKey": k, "secretKey": s}], "actions": a}) for n, (k, s), a in zip(nouveaux, cles, droits)]; json.dump(c, open(sys.argv[6], "w")); print("identités :", noms, "+", ", ".join(nouveaux))' "$T/s3.json" "$T/a.json" "$T/b.json" "$T/c.json" "$T/d.json" "$T/nouveau.json" && oc -n sophia-storage set data secret/s3-config --from-file=s3.json="$T/nouveau.json"; rm -rf "$T" )
( umask 077; T=$(mktemp -d); oc -n sophia-storage get secret s3-config -o jsonpath='{.data.s3\.json}' | base64 -d > "$T/s3.json" && oc -n sophia-sauvegarde get secret sauvegarde-s3 -o json > "$T/a.json" && oc -n sophia-git get secret export-forge-s3 -o json > "$T/b.json" && oc -n sophia-messagerie get secret export-prosody-s3 -o json > "$T/c.json" && oc -n sophia-memory get secret export-qdrant-s3 -o json > "$T/d.json" && python3 -c 'import base64, hashlib, json, sys; c = json.load(open(sys.argv[1])); e = lambda v: hashlib.sha256(v.encode()).hexdigest()[:12]; ok = lambda nom, f: (lambda m, d: (e(m["accessKey"]), e(m["secretKey"])) == (e(base64.b64decode(d["AWS_ACCESS_KEY_ID"]).decode()), e(base64.b64decode(d["AWS_SECRET_ACCESS_KEY"]).decode())))([i for i in c["identities"] if i["name"] == nom][0]["credentials"][0], json.load(open(f))["data"]); print([(i["name"], i["actions"]) for i in c["identities"]]); print("concordance :", "ok" if all(ok(n, f) for n, f in zip(["sauvegarde", "export-forge", "export-prosody", "export-qdrant"], sys.argv[2:6])) else "ÉCART")' "$T/s3.json" "$T/a.json" "$T/b.json" "$T/c.json" "$T/d.json"; rm -rf "$T" )
```

Attendu :
- `identités : [...] + sauvegarde, export-forge, export-prosody, export-qdrant`, puis `secret/s3-config data updated` ;
- toutes les identités avec leurs droits : celles d'avant n'ont pas changé ; `sauvegarde` a 9 droits (`Read` et `List` sur les trois seaux d'export, `Read`, `Write` et `List` sur `sauvegardes`) ; chaque `export-…` en a un seul, `Write` sur son seau ;
- `concordance : ok`. Aucune clé ne s'affiche.

Les entrées sur la passerelle S3 : le namespace `sophia-sauvegarde`, et le seul pod d'extraction de chacun des trois autres. Le gabarit [`../storage/03-network.yaml`](../storage/03-network.yaml) les contient : si `s3-ingress` a été appliquée depuis sa version actuelle, sauter le patch et passer au contrôle (la dernière commande du bloc). Sinon, un patch JSON qui commence par un `test` de l'état en service, et n'ajoute que ces quatre entrées, après une copie de la règle :

```bash
mkdir -p "$HOME/sauvegardes"
oc -n sophia-storage get networkpolicy s3-ingress -o yaml > "$HOME/sauvegardes/s3-ingress-avant-sauvegarde.yaml"
oc -n sophia-storage patch networkpolicy s3-ingress --type=json -p '[{"op":"test","path":"/spec/ingress/0/ports/0/port","value":8443},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-git"}},"podSelector":{"matchLabels":{"app":"export-forge"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-messagerie"}},"podSelector":{"matchLabels":{"app":"export-prosody"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-memory"}},"podSelector":{"matchLabels":{"app":"export-qdrant"}}}}]' --dry-run=server
oc -n sophia-storage patch networkpolicy s3-ingress --type=json -p '[{"op":"test","path":"/spec/ingress/0/ports/0/port","value":8443},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-git"}},"podSelector":{"matchLabels":{"app":"export-forge"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-messagerie"}},"podSelector":{"matchLabels":{"app":"export-prosody"}}}},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-memory"}},"podSelector":{"matchLabels":{"app":"export-qdrant"}}}}]'
oc -n sophia-storage get networkpolicy s3-ingress -o json | python3 -c 'import json, sys; d = json.load(sys.stdin); print([(f.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name", "-"), f.get("podSelector", {}).get("matchLabels", {}).get("app", "-")) for f in d["spec"]["ingress"][0]["from"]])'
```

Attendu : `patched (server dry run)`, puis `patched`, puis la liste des entrées, qui finit par `('sophia-sauvegarde', '-'), ('sophia-git', 'export-forge'), ('sophia-messagerie', 'export-prosody'), ('sophia-memory', 'export-qdrant')`. Si le gabarit de l'installation est plus ancien, y reporter ces quatre entrées, pour qu'un `oc apply` ultérieur ne les retire pas.

La relance du stockage, qui ne lit ses identités qu'au démarrage. **Elle coupe le stockage objet environ une minute** (fichiers, mémoire) :

```bash
oc -n sophia-storage rollout restart deploy/s3
oc -n sophia-storage rollout status deploy/s3 --timeout=5m
```

Puis les seaux :

```bash
envsubst '${AWSCLI_VERSION} ${AWSCLI_DIGEST}' < 10-seaux.yaml | oc apply -f -
oc -n sophia-storage wait --for=condition=complete job/s3-init-sauvegardes --timeout=5m
oc -n sophia-storage logs job/s3-init-sauvegardes
```

Attendu : pour chacun des quatre seaux, `"Location"` à la création, aucun versionnage, `ObjectLockConfigurationNotFoundError` sous « verrouillage » (voulu) ; puis la liste des seaux, avec `sauvegardes`, `export-forge`, `export-prosody` et `export-qdrant`.

**Étape 4 — Rôle PostgreSQL `sauvegarde`.** Rien ne doit exister :

```bash
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select count(1) from pg_roles where rolname = 'sauvegarde'"
```

Attendu : `0`. Puis le Secret d'abord, et le rôle par son vérificateur SCRAM, calculé hors du serveur par [`role-scram.py`](../memory/memoire/role-scram.py) ; puis ses droits ; puis la lecture de ce qu'il est :

```bash
openssl rand -hex 24 | tr -d '\n' | oc -n sophia-sauvegarde create secret generic postgres-sauvegarde --from-file=password=/dev/stdin && oc -n sophia-sauvegarde get secret postgres-sauvegarde -o jsonpath='{.data.password}' | base64 -d | python3 ../memory/memoire/role-scram.py sauvegarde | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -d postgres -v ON_ERROR_STOP=1
printf 'GRANT pg_read_all_data TO sauvegarde;\nSELECT format(%sGRANT CONNECT ON DATABASE %%I TO sauvegarde%s, datname) FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY datname \\gexec\n' "'" "'" | oc -n sophia-core exec -i deploy/postgres-sophia-18 -- psql -d postgres -v ON_ERROR_STOP=1
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select rolname, rolcanlogin, rolsuper, rolbypassrls, left(rolpassword, 14), pg_has_role('sauvegarde', 'pg_read_all_data', 'member'), (select count(1) from pg_database d where d.datallowconn and not d.datistemplate and not has_database_privilege('sauvegarde', d.datname, 'CONNECT')) from pg_authid where rolname = 'sauvegarde'"
```

Attendu, ligne par ligne :
1. `secret/postgres-sauvegarde created`, `vérificateur SCRAM-SHA-256 calculé localement`, puis `CREATE ROLE` ;
2. `GRANT ROLE`, puis un `GRANT` par base ;
3. `sauvegarde|t|f|f|SCRAM-SHA-256$|t|0` : connexion permise, pas superutilisateur, pas de contournement des règles de lignes, vérificateur SCRAM, membre de `pg_read_all_data`, aucune base sans `CONNECT`.

L'entrée de `sophia-sauvegarde` sur PostgreSQL, que le gabarit [`../core/postgres18/03-network.yaml`](../core/postgres18/03-network.yaml) contient aussi (si `postgres-18-ingress` vient de sa version actuelle, sauter ce patch), sinon par un patch JSON qui commence par un `test`, après une copie de la règle :

```bash
oc -n sophia-core get networkpolicy postgres-18-ingress -o yaml > "$HOME/sauvegardes/postgres-18-ingress-avant-sauvegarde.yaml"
oc -n sophia-core patch networkpolicy postgres-18-ingress --type=json -p '[{"op":"test","path":"/spec/podSelector/matchLabels/app","value":"postgres-sophia-18"},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}}]' --dry-run=server
oc -n sophia-core patch networkpolicy postgres-18-ingress --type=json -p '[{"op":"test","path":"/spec/podSelector/matchLabels/app","value":"postgres-sophia-18"},{"op":"add","path":"/spec/ingress/0/from/-","value":{"namespaceSelector":{"matchLabels":{"kubernetes.io/metadata.name":"sophia-sauvegarde"}}}}]'
```

Attendu : `patched (server dry run)`, puis `patched`. Si le gabarit de l'installation est plus ancien, y reporter l'entrée.

**Étape 5 — Mot de passe du dépôt restic.** Le créer d'abord dans un gestionnaire de mots de passe (au moins 32 caractères tirés au hasard), et le garder en plusieurs exemplaires, **hors de la plateforme** : sans lui, toutes les sauvegardes sont illisibles. Puis le coller à l'invite de `read`, qui n'affiche rien :

```bash
read -rs RESTIC_MDP
printf '%s' "$RESTIC_MDP" | oc -n sophia-sauvegarde create secret generic restic-mot-de-passe --from-file=password=/dev/stdin
printf '%s' "$RESTIC_MDP" | sha256sum | cut -c1-12
unset RESTIC_MDP
oc -n sophia-sauvegarde get secret restic-mot-de-passe -o jsonpath='{.data.password}' | base64 -d | sha256sum | cut -c1-12
```

Attendu : `secret/restic-mot-de-passe created`, puis deux fois les **mêmes** 12 caractères (une empreinte, jamais la valeur). Deux empreintes différentes : supprimer le Secret et recommencer.

**Étape 6 — Scripts et dépôt restic :**

```bash
oc apply -f 03-scripts.yaml
oc apply -f 05-restic-init.yaml
until oc -n sophia-sauvegarde get job restic-init -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/restic-init
```

Attendu : deux ConfigMaps `created`, le Job `created`, puis `created restic repository … at s3:https://s3.sophia-storage.svc:9000/sauvegardes`.

**Étape 7 — CronJobs, suspendus** (`SUSPENDRE=true`). La SCC d'abord, puisque le pod d'extraction de la forge l'épingle :

```bash
oc apply -f 06-scc-lecture-forge.yaml
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply --dry-run=server -f -
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${FORGEJO_PVC}' < 07-extraction-forgejo.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${PROSODY_PVC}' < 08-extraction-prosody.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION}' < 09-extraction-qdrant.yaml | oc apply -f -
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend | grep -E 'sauvegarde|extraction|NOM'
```

Attendu : trois objets `created` pour la SCC ; trois CronJobs ; six, six et sept objets pour les extractions ; puis six lignes `SUSPENDU true`.

**Étape 8 — Alertes, et alerte forcée :**

```bash
oc apply -f 11-alertes.yaml
oc get prometheusrule -A -l sophia=oui | grep -E 'NAME|sauvegardes'
```

Attendu : quatre `sophia-sauvegardes`, dans `sophia-git`, `sophia-memory`, `sophia-messagerie` et `sophia-sauvegarde`. Au bout d'une heure, `SophiaSauvegardeSuspendue` (warning) sonne pour chacun des six CronJobs et doit parvenir à l'administrateur : c'est la preuve de la chaîne d'alerte.

**Étape 9 — Premier cycle, à la main.** Dans l'ordre, chacun après le contrôle du précédent. Les trois extractions et la nuit doivent tomber **le même jour UTC** : la nuit refuse un export d'un autre jour. Les vidages d'abord :

```bash
oc -n sophia-sauvegarde create job sauvegarde-bases-premier --from=cronjob/sauvegarde-bases
until oc -n sophia-sauvegarde get job sauvegarde-bases-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/sauvegarde-bases-premier --all-containers
oc -n sophia-core exec deploy/postgres-sophia-18 -- psql -d postgres -Atc "select count(1) from pg_database where datallowconn and not datistemplate"
```

Attendu : `vidages : N bases, … Mo`, le résumé de restic (`Added to the repository: …`) et les instantanés gardés ; puis le même N. Les extractions :

```bash
oc -n sophia-git create job extraction-forgejo-premier --from=cronjob/extraction-forgejo
until oc -n sophia-git get job extraction-forgejo-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-git logs job/extraction-forgejo-premier --all-containers
oc -n sophia-messagerie create job extraction-prosody-premier --from=cronjob/extraction-prosody
until oc -n sophia-messagerie get job extraction-prosody-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-messagerie logs job/extraction-prosody-premier --all-containers
oc -n sophia-memory create job extraction-qdrant-premier --from=cronjob/extraction-qdrant
until oc -n sophia-memory get job extraction-qdrant-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-memory logs job/extraction-qdrant-premier --all-containers
```

Attendu :
- forge : `dépôts git exclus de l'archive : N`, `Forgejo : base copiée (integrity_check ok), archive de … Mo`, puis `déposé : forgejo.tar dans export-forge, … Mo` ;
- messagerie : `Prosody : archive de … Mo`, puis `déposé : prosody.tar dans export-prosody, … Mo` ;
- base vectorielle : `Qdrant : N collections, … points avant l'instantané (…)`, `Qdrant : instantané complet … téléchargé, … Ko, … fichiers dans l'archive, supprimé de Qdrant`, puis `déposé : qdrant.snapshot dans export-qdrant, … Mo`.

La nuit, puis l'essai de restauration :

```bash
oc -n sophia-sauvegarde create job sauvegarde-nuit-premier --from=cronjob/sauvegarde-nuit
until oc -n sophia-sauvegarde get job sauvegarde-nuit-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/sauvegarde-nuit-premier --all-containers
oc -n sophia-sauvegarde create job essai-restauration-premier --from=cronjob/essai-restauration
until oc -n sophia-sauvegarde get job essai-restauration-premier -o 'jsonpath={.status.conditions[?(@.status=="True")].type}' | grep -Ewq 'Complete|Failed'; do sleep 10; done
oc -n sophia-sauvegarde logs job/essai-restauration-premier --all-containers
```

Attendu :
- nuit : la taille des trois copies d'export (sinon `export périmé : …` : refaire alors l'extraction en cause), `Secrets exportés : … dans N namespaces`, le résumé de restic, les deux `forget`, le `prune`, puis `no errors were found` ;
- essai : `base choisie : …`, puis `restauration de … : … tables, décomptes égaux, … schémas à leur propriétaire, … s`, sous 600 s.

**Étape 10 — Bilan :**

```bash
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend,DERNIER_SUCCES:.status.lastSuccessfulTime | grep -E 'sauvegarde|extraction|NOM'
```

Attendu : six lignes `SUSPENDU true`, chacune avec `DERNIER_SUCCES` renseigné : les Jobs lancés par `--from=cronjob` portent l'ownerReference de leur CronJob. Avec l'alerte de l'étape 8 reçue, le premier cycle est fait.

**Étape 11 — Levée de la suspension.** `export SUSPENDRE=false`, puis le même rendu, contrôlé par `oc diff` :

```bash
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc diff -f -
envsubst '${SUSPENDRE} ${SECRETS_NAMESPACES}' < 04-cronjobs.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${FORGEJO_PVC}' < 07-extraction-forgejo.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION} ${PROSODY_PVC}' < 08-extraction-prosody.yaml | oc apply -f -
envsubst '${SUSPENDRE} ${AWSCLI_VERSION}' < 09-extraction-qdrant.yaml | oc apply -f -
oc get cronjob -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,SUSPENDU:.spec.suspend,DERNIER_SUCCES:.status.lastSuccessfulTime | grep -E 'sauvegarde|extraction|NOM'
```

Attendu : le diff ne montre que `suspend: true` devenu `false`, pour les trois CronJobs ; puis six `cronjob.batch/… configured` en tout (les autres objets `unchanged`) ; puis six lignes `SUSPENDU false`. `SophiaSauvegardeSuspendue` se résout dans l'heure ; le premier vidage automatique part à la minute 05 suivante.

**Étape 12 — Premier cycle automatique**, le lendemain matin : la commande de l'étape 10. Attendu : `DERNIER_SUCCES` de la nuit pour les trois extractions et pour `sauvegarde-nuit`, de moins d'une heure pour `sauvegarde-bases`, et aucune alerte. L'essai de restauration suit le dimanche à 08:00.

## Restaurer

Le seul chemin éprouvé est celui de l'essai hebdomadaire : une base restaurée dans un PostgreSQL éphémère, contrôlée, puis jetée (`essai-restaurer.sh`, `essai-verifier.sh` de `03-scripts.yaml`). Ses scripts sont le modèle d'une restauration : rôles d'abord (`globales.sql`, sans mots de passe), puis la base avec ses propriétaires. Les mots de passe des rôles ne sont pas dans les vidages ; ils sont dans les Secrets, exportés chaque nuit. Les réglages par base (`ALTER DATABASE … SET`) ne sont pas dans un vidage : la reconstruction les remet. La SCC `lecture-forge` est prévue aussi pour restaurer Forgejo sous son uid. La restauration en place d'un service et la reconstruction du serveur n'ont pas encore de procédure écrite.

## Copie hors site

Le dépôt restic est dans le stockage objet du même serveur : il protège d'une erreur ou d'une donnée corrompue, pas de la perte du serveur. Une installation ajoute une copie hors site du seau `sauvegardes`, qui ne contient que des blocs chiffrés, poussée par un compte qui ne peut ni remplacer ni supprimer. Les options sont dans [Sauvegarde et stockage : solutions souveraines](../../../docs/security.md#sauvegarde-et-stockage--solutions-souveraines). Ces gabarits n'en contiennent aucune.

## Retour arrière

À rebours, et seulement en connaissance de cause : sans ces tâches, plus rien n'est sauvegardé. Suspendre d'abord (`SUSPENDRE=true`, étape 11). Puis `oc delete` des rendus de `11`, `09`, `08`, `07` et `06` ; le `Role` et le `RoleBinding` de chaque namespace de la liste (`oc -n <namespace> delete role,rolebinding sauvegarde-lecture-secrets`) ; puis le namespace `sophia-sauvegarde`, qui emporte ses CronJobs, ses images et ses Secrets, **mot de passe restic compris** : le dépôt n'est plus lisible qu'avec les exemplaires gardés hors de la plateforme. Sur PostgreSQL : `REVOKE CONNECT` sur chaque base (même `\gexec` qu'à l'étape 4), `REVOKE pg_read_all_data FROM sauvegarde`, `DROP ROLE sauvegarde` ; la règle d'entrée depuis sa copie (`oc apply -f "$HOME/sauvegardes/postgres-18-ingress-avant-sauvegarde.yaml"`). Sur le stockage : `s3-config` depuis `s3-config-avant-sauvegarde`, puis la relance (coupure d'environ une minute) ; `s3-ingress` depuis sa copie ; les Secrets `export-…-s3` des trois namespaces. Les seaux ne se suppriment que vides, par l'identité d'administration : vider `sauvegardes` **détruit toutes les sauvegardes**. La copie `s3-config-avant-sauvegarde` se supprime une fois le premier cycle automatique conforme.

## Pièges

- **Niveau SELinux du namespace.** Un pod de `sophia-sauvegarde` ne peut pas lire le volume de la forge ni celui de la messagerie : la SCC fixe le niveau SELinux au namespace. D'où les extractions, chacune dans le namespace de son service, qui déposent une copie dans un seau interne.
- **Forge sous l'uid 1000, en `0700`.** `restricted-v2` donne un uid de la plage du namespace, qui ne lit pas `/data`. D'où la SCC `lecture-forge`, épinglée par annotation. Elle n'est étroite que pour les pods qui l'épinglent : relire les autres SCC accordées aux comptes du namespace de la forge.
- **SQLite en mode WAL sur un volume en lecture seule.** La copie de la base de Forgejo demande parfois le fichier `-shm`. Dans l'installation de référence, elle passe en lecture seule ; si elle échoue chez vous, monter le volume en écriture est une décision à part.
- **Export du jour, en UTC.** La nuit refuse un export d'un autre jour UTC. À la main, lancer les extractions et la nuit le même jour UTC : à Paris, juste après minuit, la date UTC est encore celle de la veille.
- **Verrou de restic.** Le `prune` de la nuit prend un verrou exclusif ; sans `--retry-lock`, le vidage horaire suivant échouerait.
- **Quota CPU.** La nuit, un vidage horaire et l'essai ensemble dépasseraient les 4 CPU du quota : l'essai part le dimanche à 08:00, après la fenêtre de la nuit (03:30, une heure de retard admise et trois de durée, soit 07:30 au plus).
- **Quota de la messagerie.** L'extraction de Prosody tourne dans le namespace de la messagerie : ses limites, conteneur d'init compris, doivent tenir dans ce que laisse le quota de ce namespace.
- **Base nouvelle.** Le rôle `sauvegarde` n'a `CONNECT` que sur les bases qui existaient à l'étape 4 : pour une base créée ensuite, rejouer la ligne `GRANT CONNECT` (rejouable), sinon le vidage horaire échoue, et l'alerte le dit.
- **Namespace nouveau.** L'ajouter à `${SECRETS_NAMESPACES}`, rendre `02-lecture-secrets.yaml` pour lui, puis rendre de nouveau `04-cronjobs.yaml` : sinon ses Secrets ne sont pas sauvegardés, sans alerte.
- **Une règle d'alerte par namespace.** Thanos Ruler ne montre à une `PrometheusRule` que les séries de son namespace : une règle centrale ne verrait pas les CronJobs des autres.
- **Mot de passe de l'essai.** Le PostgreSQL éphémère de l'essai a un mot de passe fixe (`POSTGRESQL_ADMIN_PASSWORD` de `04-cronjobs.yaml`). Ce n'est pas un secret : l'instance n'est joignable que dans le pod et disparaît avec lui.
