# Observabilité minimale

Voir l'état de la plateforme avant ses utilisateurs : un modèle saturé, un pod tué faute de mémoire, des messages en lettres mortes, un workflow en échec, une carte graphique pleine, un filtre d'accès VPN retiré. Ce dossier s'appuie sur la pile de supervision fournie par OKD, sans composant de plus qu'un petit exporteur pour le nœud. Concept : [Observabilité et réaction aux incidents](../../../docs/concepts/10-observabilite.md).

```
RabbitMQ, Temporal, llama-server ──┐            ┌─ Thanos Ruler : 29 règles « Sophia… »
exporteur du nœud (GPU, .prom) ────┼─ Prometheus ┤
                                   │  (charges   └─ Alertmanager des charges utilisateur ──┐
       métriques d'OKD (kube-state-metrics…)       ─┐        │                              │
                                                    │        ▼                              ▼
                                Thanos (lecture) ◀──┘  répartiteur /v1/alertes      bot Telegram → administrateur
                                                       (journalise ; workflow                ▲
                                                        « incident » prévu)    Alertmanager de la plateforme OKD
```

## État

| Élément | État |
|---|---|
| Surveillance des charges utilisateur (Prometheus, Thanos Ruler, Alertmanager propres) | en service |
| Collecte de RabbitMQ, Temporal et llama-server | en service |
| 29 règles d'alerte : 21 dans `20-regles.yaml`, 8 pour le nœud dans `40-node-metrics.yaml` | en service : chargées, aucune en erreur |
| Exporteur du nœud : GPU par NVML, fichiers `.prom` déposés par les scripts du nœud, occupation des volumes (`/var` et chaque volume logique monté sous `/var/mnt`) ; classe `sophia-agents` | en service |
| Alerte de remplissage des volumes, à 80 % puis 90 % | en service |
| Garde-fou du filtre VPN qui écrit son code en métrique | en service |
| Notification de l'administrateur par Telegram, pour toutes les alertes actionnables des namespaces SophIA et de la plateforme OKD : un message par problème, puis « Résolue » | en service ; essai réel reçu |
| Envoi par courriel de la plateforme | retiré : Telegram seul |
| Webhook vers le répartiteur (`30-` et `31-alertmanager-config…yaml`, récepteur `/v1/alertes`) pour `sophia-core` et `sophia-workflow` | en service : le répartiteur **journalise** chaque alerte, dans la vie de son pod |
| Alertes de la plateforme OKD vers le répartiteur (`alertmanager-main-ajout.py`) | prévu, avec le workflow « incident » |
| Workflow « incident », registre durable des incidents | prévus |

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Pile | la surveillance des charges utilisateur d'OKD (`enableUserWorkload`), pas une pile Prometheus à part | une seule pile, déjà maintenue par la plateforme ; les règles se lisent avec le reste dans la console (**Observe**) |
| Ressources | Prometheus 1 à 3 Gio, Thanos Ruler et Alertmanager bornés ; rétention de 15 jours ; coût mesuré ≈ 0,2 CPU et 1 à 2 Gio | le CPU est la ressource rare du nœud, pas la mémoire |
| Services de métriques | des Services à part (`*-metrics`), étiquetés `sophia-metrics` | ne rien changer aux Services existants, donc rien à leurs clients |
| Entrée | une NetworkPolicy par namespace, qui n'ouvre que les ports de métriques au seul Prometheus des charges utilisateur | `sophia-core` et `sophia-inference` refusent toute entrée par défaut |
| RabbitMQ | agrégats toutes les 30 s ; détail par file et par exchange du vhost toutes les 60 s | la file des lettres mortes se lit dans le détail, pas dans les agrégats |
| Règles communes | OOM et redémarrages en boucle, **répétés dans chaque namespace** surveillé | une `PrometheusRule` des charges utilisateur ne voit que les séries de son namespace |
| Étiquette `sophia: oui` | sur chaque règle et chaque alerte | c'est elle que route l'AlertmanagerConfig, et elle seule |
| GPU | exporteur en bibliothèque standard Python, qui lit NVML par `ctypes` dans la bibliothèque du pilote montée depuis le nœud ; pod privilégié dans `sophia-inference`, dont le compte a déjà la SCC `privileged` de llama-server | pas d'opérateur GPU ni de DCGM sur un chemin « pilote seul » ; aucun droit nouveau ; NVML ne fait que lire, sans effet sur llama-server |
| Métriques du nœud | les scripts du nœud déposent des fichiers `.prom` dans un répertoire du nœud, que l'exporteur lit en lecture seule | le collecteur `textfile` du node-exporter d'OKD est un `emptyDir` : le nœud ne peut pas y écrire |
| Occupation des volumes | mesurée par l'exporteur, qui monte `/var/mnt` en lecture seule (propagation `HostToContainer`, pour voir aussi un volume monté après son démarrage) ; un répertoire non monté est ignoré | les séries du node-exporter d'OKD vivent dans le namespace de la plateforme, qu'une règle d'un namespace SophIA ne peut pas lire |
| Garde-fou du filtre VPN | une seule fonction ajoutée : à chaque passage, il écrit son code (0 lisible, 1 filtre retiré, 2 vérification impossible) et un horodatage ; écriture atomique (fichier temporaire puis `mv`), **erreurs ignorées** | ses décisions, ses actions et ses codes de sortie ne changent pas ; une alerte prévient si le filtre est retiré, et une autre si le garde-fou se tait plus de 45 minutes |
| Format d'exposition | une ligne `# TYPE` au-dessus de chaque famille, ses séries regroupées dessous | une seule ligne `TYPE` en tête, pour une seule famille, laisse les autres sans type |
| Notification de l'administrateur | une route Telegram dans la **configuration générale** de chacun des deux Alertmanager (plateforme et charges utilisateur), placée **en tête**, `continue: true`, plutôt qu'une AlertmanagerConfig et un Secret par namespace | un seul endroit à tenir par Alertmanager ; le jeton n'est que dans les deux namespaces de supervision, réservés aux administrateurs |
| Bot | un bot **dédié aux alertes**, qui n'écrit qu'à l'administrateur, dans une conversation privée ; ajout aux groupes interdit | le bot d'un agent permettrait aussi de lire ce que l'administrateur écrit à l'agent ; celui-ci ne peut qu'écrire, sous son nom |
| Jeton | Secret `alertes-telegram` monté par l'opérateur (`secrets:` des ConfigMaps `00-` et `01-`), lu par `bot_token_file` | jamais écrit dans la configuration d'Alertmanager |
| Filtre | `warning` et `critical` seulement : `Watchdog`, `InfoInhibitor` et `info` (dont `UpdateAvailable`) ne passent pas ; deux alertes de la plateforme permanentes et sans action possible sont exclues par leur nom | relevé de 7 jours avant la mise en service : les seules alertes actives de la plateforme étaient du bruit |
| Un message par problème | groupement par namespace et nom d'alerte ; une alerte critique masque l'avertissement de même nom ; rappel toutes les 24 h | une alerte qui dure ne doit pas noyer les autres |
| Contenu | nom, gravité, namespace, résumé, heure de début (heure de Paris, date ajoutée au-delà de 12 h) ; « ✅ Résolue » avec la durée ; lien de la console, joignable par le VPN seulement | ni donnée d'utilisateur ni secret ne part chez Telegram |
| Plateforme | Telegram **seul** : l'ancien récepteur par courriel et ses clés `smtp_*` sont retirés, le récepteur par défaut n'a plus d'intégration | un seul canal, et plus de mot de passe de messagerie dans la configuration |
| Alertes vers le répartiteur | AlertmanagerConfig par namespace (charges utilisateur), jeton porteur et TLS de service ; route prévue dans `alertmanager-main` (OKD) | une alarme devient une demande comme une autre, avec une identité vérifiée ; le récepteur ne fait que valider et journaliser tant que le workflow « incident » n'existe pas. Les deux envois sont indépendants : un répartiteur arrêté n'empêche pas le message |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-cluster-monitoring-config.yaml` | active la surveillance des charges utilisateur |
| `01-user-workload-config.yaml` | rétention, ressources, Alertmanager des charges utilisateur avec AlertmanagerConfig |
| `10-metrics-services.yaml` | Services de métriques de RabbitMQ (15692) et de Temporal (9090) |
| `11-servicemonitors.yaml` | collecte de RabbitMQ, Temporal et llama-server |
| `12-network-policies.yaml` | entrée des ports de métriques depuis le seul Prometheus des charges utilisateur |
| `20-regles.yaml` | 7 `PrometheusRule` `sophia-alertes` : répartiteur indisponible, lettres mortes et alarmes de RabbitMQ, workflows en échec, modèle local indisponible ou saturé, collecte en échec, et les règles communes |
| `30-alertmanager-config.yaml` | webhook des alertes `sophia: oui` de `sophia-core` vers le répartiteur |
| `31-alertmanager-config-sophia-workflow.yaml` | le même, pour les alertes `audience: admin` de `sophia-workflow` (miroirs des dépôts) |
| `alertes-telegram-ajout.py` | ajoute le récepteur Telegram et sa route en tête à la configuration générale d'un Alertmanager (`main` ou `user-workload`) ; `--telegram-seul` retire l'ancien courriel de la plateforme ; `masque` pour comparer avant et après sans rien afficher ; rejouable |
| `40-node-metrics.yaml` | exporteur du nœud (Deployment, Service, ServiceMonitor, NetworkPolicy) et ses 8 règles : filtre VPN retiré, vérification impossible, garde-fou muet ; GPU non mesurable, mémoire pleine, température ; volume presque plein (80 %), plein (90 %) |
| `node-metrics/exporteur.py` | code de l'exporteur, bibliothèque standard seulement |
| `alertmanager-main-ajout.py` | ajoute le récepteur du répartiteur et sa route en tête à la configuration de `alertmanager-main`, sans rien retirer ; rejouable (prévu) |

Le garde-fou du filtre VPN est décrit dans [`../host/wireguard/`](../host/wireguard/).

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${AGENT_NAMESPACE}` | namespace des agents, surveillé par les règles communes | `agents` |
| `${NVIDIA_LIB_DIR}` | répertoire du nœud qui contient `libnvidia-ml.so.1`, le même que pour llama-server | `/var/lib/nvidia` |
| `ALERTES_CHAT_ID` | (environnement de `alertes-telegram-ajout.py`) conversation privée entre le bot et l'administrateur | identifiant numérique |
| `CONSOLE_URL` | (même script) adresse de la console d'OKD, en fin de message | `https://console.example.org` |

Les annotations des règles contiennent des `{{ $labels… }}` et des `{{ $value }}`. **La substitution se restreint à la variable du fichier** : `envsubst '${AGENT_NAMESPACE}' < 20-regles.yaml` et `envsubst '${NVIDIA_LIB_DIR}' < 40-node-metrics.yaml`. Un `envsubst` sans liste viderait les annotations sans erreur.

| Secret | Namespace | Clés |
|---|---|---|
| `repartiteur-alertes` | `sophia-core` | `jeton` (`openssl rand -hex 32`, **sans saut de ligne**), lu par le répartiteur et par l'AlertmanagerConfig |
| `repartiteur-alertes` | `sophia-workflow` | `jeton` (la même valeur, par un tube) |
| `alertes-telegram` | `openshift-monitoring` et `openshift-user-workload-monitoring` | `jeton` du bot ; **ces deux copies seulement** |
| `repartiteur-alertes` | `openshift-monitoring` | `jeton` (la même valeur, par un tube), `service-ca.crt` ; pour les alertes d'OKD vers le répartiteur seulement (prévu) |

## Procédure (l'administrateur)

Depuis un clone propre et à jour du dépôt interne. Une étape à la fois, et chaque `oc apply` est précédé d'un `oc diff` **relu en entier**. Aucun service existant ne redémarre : seuls des pods nouveaux sont créés, supervision et exporteur. Les vérifications se font dans la console d'OKD (**Observe**), ou en lecture par Thanos.

1. **Surveillance des charges utilisateur** : `00-cluster-monitoring-config.yaml`. Attendu, après une à trois minutes, dans `openshift-user-workload-monitoring` : `prometheus-operator`, `prometheus-user-workload-0` et `thanos-ruler-user-workload-0` en `Running`. Retour arrière : revenir au ConfigMap d'avant (ou le supprimer s'il n'existait pas).
2. **Réglages et Alertmanager** : `01-user-workload-config.yaml`. Attendu : en plus, `alertmanager-user-workload-0` en `Running` ; Prometheus redémarre une fois pour prendre ses limites. Retour arrière : supprimer `user-workload-monitoring-config`.
3. **Collecte** : `10-metrics-services.yaml`, `12-network-policies.yaml`, puis `11-servicemonitors.yaml`. Attendu, dans **Observe → Targets**, filtre « User » : `rabbitmq-metrics` (deux points de collecte), `temporal-metrics` et `llama-server`, tous `Up`. Retour arrière : `oc delete -f` des trois fichiers, qui n'ajoutent que des objets nouveaux.
4. **Règles** : `20-regles.yaml` (substitution restreinte), puis `oc get prometheusrule -A -l sophia=oui`. Attendu : sept `sophia-alertes` ; dans **Observe → Alerting**, les règles `Sophia…`, aucune en erreur, aucune en `Firing`. `SophiaLLMLocalIndisponible` peut passer en `Pending` le temps de la première collecte de llama-server, sans atteindre `Firing`. Retour arrière : `oc delete -f`.
5. **Nœud.**
   - **5a. Garde-fou du filtre VPN en métrique.** C'est le seul chemin d'administration : même prudence que pour le filtre lui-même. **Avant toute installation**, le banc compare l'ancien et le nouveau script avec de faux `crictl`, `podman`, `nft` et `logger`, sur 5 scénarios OVN croisés avec 3 états du fichier de métrique. Il se lance **sous Linux seulement** : le garde-fou tourne sur le nœud avec le `sed` GNU, et le banc refuse de tourner avec un autre `sed` (code 2) plutôt que de comparer un autre comportement. Attendu : `AUCUN ÉCART (15 cas)` ; sinon, on n'installe pas. Installation, hors de l'heure d'usage, la session d'administration restant ouverte : contrôle de syntaxe (`bash -n`), ancien script mis de côté sur le nœud, installation, puis **un passage identique à celui de la minuterie**, sans recharger le filtre ni redémarrer aucun service. Attendu : code 0, `sophia_wg_filter_code 0` et un horodatage dans le fichier `.prom`, table du filtre présente ; au passage suivant de la minuterie, l'horodatage avance. **Retour arrière en une commande** : réinstaller l'ancien script mis de côté et le lancer une fois.
   - **5b. Exporteur** : ConfigMap `sophia-node-metrics` créé depuis `node-metrics/exporteur.py` (`oc create configmap … --from-file … --dry-run=client -o yaml`, relu, puis appliqué), puis `40-node-metrics.yaml` (substitution restreinte). Attendu, sur `/metrics` du pod : `sophia_gpu_nvml_ok 1`, la mémoire, l'utilisation, la température et la puissance de la carte, puis les lignes `sophia_wg_filter_…` ; dans Thanos, la cible `sophia-node-metrics` `Up`. Si `sophia_gpu_nvml_ok 0` : le pod ne voit pas les périphériques GPU, lire son journal. Retour arrière : `oc delete -f 40-node-metrics.yaml` et le ConfigMap ; llama-server n'est jamais touché.
6. **Webhook vers le répartiteur** : une image du répartiteur qui contient le récepteur `/v1/alertes` et retire les blancs du jeton, lu dans le Secret `repartiteur-alertes` ; ce Secret, copié par un tube dans `sophia-workflow` ; une règle d'entrée du répartiteur depuis `openshift-user-workload-monitoring` (pods `app.kubernetes.io/name=alertmanager`, port 8443) ; relance du répartiteur, puis `30-` et `31-alertmanager-config…yaml` (`--dry-run=server`, `oc diff`, `oc apply`). Contrôle par le vrai chemin : `/sante` répond 200 et `/v1/alertes` sans jeton 401. Le récepteur ne fait que valider et journaliser chaque alerte.
7. **Notification de l'administrateur par Telegram.**
   - **7.0 Le bot** (l'administrateur, dans Telegram) : un bot neuf, réservé aux alertes ; ouvrir la conversation avec lui et la démarrer (sans quoi Telegram lui refuse d'écrire), interdire son ajout à un groupe. Contrôle du jeton par `getMe`, l'adresse passée à `curl -K -` sur son entrée, jamais en argument.
   - **7.1 Sauvegardes et Secrets** : configuration générale de chaque Alertmanager sauvegardée **hors du dépôt** (celle de la plateforme peut contenir un mot de passe de messagerie) ; Secret `alertes-telegram` créé par un tube dans les deux namespaces de supervision (`read -rs`, puis `printf … | oc create secret … --from-file=jeton=/dev/stdin`). Contrôle : les longueurs seulement.
   - **7.2 Montage** : `00-` puis `01-…-config.yaml`, **après** les Secrets ; attendre la relance des deux Alertmanager.
   - **7.3 Configurations générales** : `alertes-telegram-ajout.py user-workload`, puis `main --telegram-seul <ancien récepteur>` ; comparer avant et après par `masque`, puis `diff` relu : le récepteur `admin-telegram`, sa route en tête, l'inhibition (charges utilisateur), et, pour la plateforme, l'ancien courriel retiré et rien d'autre. `oc set data` de la clé `alertmanager.yaml`, puis dans le journal de chaque Alertmanager `Completed loading of configuration file` sans erreur.
   - **7.4 Anciennes copies** : supprimer tout Secret du jeton du bot hors des deux namespaces de supervision.
   - **7.5 Essai réel** : une règle toujours vraie dans un namespace SophIA et une sur la plateforme. Attendu : un message par alerte, sans doublon, puis « ✅ Résolue » une dizaine de minutes après leur retrait ; dans Thanos, `alertmanager_notifications_total{integration="telegram"}` augmente et `…_failed_total` reste à 0, `integration="email"` à 0.
   - **Retour arrière** : réécrire les sauvegardes par `oc set data`, retirer le montage, supprimer les Secrets ; le bot se supprime dans Telegram.

### Alertes d'OKD vers le répartiteur (prévu, avec le workflow « incident »)

La notification de l'administrateur passe déjà par l'étape 7 ; ce circuit ne sert qu'à journaliser aussi les alertes de la plateforme chez le répartiteur.


1. Secret `repartiteur-alertes` dans `openshift-monitoring` : le jeton passe par un tube depuis celui de `sophia-core`, sans être affiché, puis l'autorité de service d'OKD (`service-ca.crt`). Contrôle : les clés `jeton` et `service-ca.crt`, et rien d'autre.
2. Montage chez l'Alertmanager d'OKD : `repartiteur-alertes` ajouté à `alertmanagerMain.secrets`, à côté d'`alertes-telegram`, dans `cluster-monitoring-config`, **seulement après** le Secret (sans lui, les pods `alertmanager-main` ne démarrent plus). Attendre la fin du `rollout`.
3. Entrée du répartiteur depuis `openshift-monitoring` (pods `alertmanager`, 8443).
4. Sauvegarde de la clé `alertmanager.yaml` du Secret `alertmanager-main` hors du dépôt (elle peut contenir des identifiants de récepteurs), `alertmanager-main-ajout.py < avant > après`, `diff` relu : le récepteur `repartiteur` ajouté, la route en tête, rien d'autre. Puis `oc set data` et, dans le journal de l'Alertmanager, `Completed loading of configuration file` sans erreur. Retour arrière : réécrire la sauvegarde, retirer le montage, supprimer ce Secret.

## Leçons

- **Une AlertmanagerConfig reçoit `continue: true` de l'opérateur.** Un récepteur Telegram dans l'AlertmanagerConfig **et** dans la route générale enverrait chaque alerte deux fois : la notification ne vit que dans la route générale.
- **Un jeton terminé par un saut de ligne fait refuser tout envoi (401).** Créer le Secret sans saut de ligne (`tr -d '\n'`), et retirer les blancs à la lecture.
- **Un bot Telegram ne peut écrire qu'à qui l'a démarré** (erreur 403 sinon).

- **Des métriques exposées ne sont pas collectées.** RabbitMQ, Temporal et llama-server exposaient tous leurs métriques ; personne ne les lisait, et aucune règle n'existait hors d'OKD.
- **Le `textfile` du node-exporter d'OKD est un `emptyDir`** : le nœud ne peut pas y déposer de fichier. D'où l'exporteur à part, qui lit un répertoire du nœud.
- **Une règle ne voit que son namespace** dans la surveillance des charges utilisateur : une règle commune se répète dans chaque namespace, ou elle ne couvre rien.
- **Une ligne `# TYPE` par famille.** Une seule ligne en tête de l'exposition, pour une seule famille, laisse les autres sans type.
- **Un banc se lance là où tourne le script.** Le `sed` BSD ne comprend pas `\+` comme le `sed` GNU du nœud : un banc rejoué ailleurs que sous Linux n'aurait pas prouvé le comportement du nœud.
- **`envsubst` sans liste vide les annotations** qui contiennent `$labels` ou `$value`, sans erreur.

## Suite

- **Volume de Temporal** : environ 21 000 séries, dont 17 000 de seaux d'histogrammes ; la mémoire de travail de Prometheus reste autour de 0,1 Gio pour 3 Gio au plus. La cardinalité suit les opérations, les files et les types de workflow, pas le nombre d'exécutions. **Aucun filtre pour l'instant.** Si la mémoire dépasse environ 1,5 Gio au relevé d'une semaine, on ajoute à l'endpoint du ServiceMonitor `temporal` un `metricRelabelings` qui retire les seules séries `.+_bucket` : environ 3 800 séries restent, les règles et les moyennes (`_sum`, `_count`) aussi ; seuls les percentiles de latence sont perdus.
- Les seuils sont des valeurs de départ, à recalibrer sur une semaine de mesures, en particulier `SophiaLLMLocalSature`.
- Le routeur de modèles n'expose pas de métriques dans sa version en service : seuls ses OOM sont couverts, par la règle commune.
- **Historique des alertes** : Prometheus des charges utilisateur n'a pas de volume persistant (rétention de 15 jours, perdue à la recréation du pod), et le répartiteur ne garde les alertes que dans son journal. Prévu : un registre durable des incidents tenu par le répartiteur.
- Alertes d'OKD vers le répartiteur, puis le workflow « incident » : collecte par les fonctions de lecture, diagnostic du modèle en sortie contrainte, gravité tirée de l'étiquette, notification et approbation, aucune action automatique.
