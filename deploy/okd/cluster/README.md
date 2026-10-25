# Priorités et quotas CPU (cluster)

Un seul nœud porte la discussion, le modèle de langage, la voix, les agents, la bureautique, les images et le développement. La mémoire vive a de la marge, **le CPU non** : la consommation réelle est faible, mais les limites déclarées dépassent la capacité du nœud. Ce dossier fixe **qui passe en premier** quand la place manque, et **combien chaque namespace peut déclarer**. Concept : [Inférence et matériel](../../../docs/concepts/11-inference-materiel.md).

## Classes de priorité

| Classe | Valeur | Préemption | Charges |
|---|---|---|---|
| `sophia-socle` | 2 000 000 | non | pod de lecture du cluster (assistant de code), forge Git |
| `sophia-inference-high` | 1 000 000 | **oui** | serveur du modèle de langage ([`../inference/00-namespace-guardrails.yaml`](../inference/00-namespace-guardrails.yaml)) |
| `sophia-chat` | 100 000 | non | interface, applications du foyer, routeur de modèles, base relationnelle, identité |
| `sophia-voix` | 90 000 | non | reconnaissance et synthèse vocales |
| `sophia-agents` | 80 000 | non | répartiteur, workflows, bus, agents, embedding, sas web |
| `sophia-workspace-low` | 50 000 | non | bureautique |
| `sophia-images` | 30 000 | non | génération d'images, plafonnée à 8 CPU |
| `sophia-dev` | 10 000 | non | pods de développement, passerelle de dev, clusters enfants |

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Préemption | **aucune classe SophIA ne préempte** (`preemptionPolicy: Never`) ; seule la classe d'inférence, existante, garde ce droit | une préemption tue un pod en plein travail ; avec une vingtaine de CPU de marge en requests, la file d'attente suffit |
| Socle au-dessus de l'inférence | `sophia-socle` (2 000 000) plutôt que passer `sophia-inference-high` en `Never` | le planificateur n'évince jamais un pod de priorité égale ou supérieure ; `preemptionPolicy` ne se modifie pas sur une classe existante : il aurait fallu la supprimer, la recréer, puis recréer le serveur d'inférence |
| Socle | le pod de lecture du cluster et la forge Git | le premier permet de comprendre l'état du cluster en panne ; tous les déploiements partent de la seconde : sans elle, plus rien ne démarre |
| Demande mémoire du socle | au-dessus du pic mesuré (pod de lecture 12 Gio pour 10,8 Gio, forge 1,5 Gio pour 965 Mio) | sous pression mémoire, le kubelet évince d'abord les pods qui dépassent leur demande, **quelle que soit leur classe** ; un pod sans demande (`BestEffort`) part le premier |
| Pas de classe par défaut | `globalDefault: false` | un pod sans classe vaut 0 et passe après toutes les charges SophIA : chaque charge nomme la sienne |
| Images | 8 CPU au plus, 8 threads | la génération d'images prenait jusqu'à 16 CPU, en concurrence directe avec la voix |
| Quotas | sur les **limits**, par namespace, avec un `LimitRange` de valeurs par défaut | les limits déclarées dépassaient 160 % du nœud ; le quota borne ce qu'un namespace peut promettre, le `LimitRange` donne des limites aux pods qui n'en déclarent pas |

## Quotas de l'installation de référence

| Namespace | limits CPU | limits mémoire | pods | Remarque |
|---|---|---|---|---|
| `sophia-memory` | 8 | 16 Gi | 10 | base graphe 2 CPU / 8 Gi au plus |
| `sophia-dmz` | 8 | 12 Gi | 12 | navigateur distant des courses |
| `sophia-apps` | 24 | 40 Gi | 30 | les builds y tournent, dont une compilation CUDA en 16 CPU / 24 Gi |
| `${AGENT_NAMESPACE}` | 28 | 48 Gi | 15 | pod de lecture 16 CPU / 32 Gi au plus ; ressources explicites sur **tous** les conteneurs, init compris |
| bureautique | 10 | 10 Gi | 15 | plus requests 2 CPU / 4 Gi |

Gabarit : `01-namespace-quota.yaml` (une copie par namespace).

| Variable | Rôle | Exemple |
|---|---|---|
| `${NAMESPACE}` | namespace visé | `sophia-memory` |
| `${QUOTA_NAME}` | nom du quota | `memory-quota` |
| `${QUOTA_LIMITS_CPU}`, `${QUOTA_LIMITS_MEMORY}`, `${QUOTA_PODS}` | plafonds | `8`, `16Gi`, `10` |
| `${DEFAULT_CPU_LIMIT}`, `${DEFAULT_MEMORY_LIMIT}` | limites par défaut d'un conteneur | `500m`, `512Mi` |
| `${DEFAULT_CPU_REQUEST}`, `${DEFAULT_MEMORY_REQUEST}` | demandes par défaut | `20m`, `64Mi` |
| `${AGENT_NAMESPACE}` | namespace des agents | `agents` |

## Procédure (l'administrateur)

Une étape à la fois, depuis un clone propre et à jour du dépôt interne, comparé d'abord au cluster : `oc diff` ne doit montrer que les changements voulus. **Chaque `oc apply` est précédé d'un `oc diff` relu en entier.** Une classe ne change rien aux pods déjà lancés : chaque `apply` d'une charge redémarre son pod une fois, sur la même image.

1. **Classes** (aucun effet sur ce qui tourne) : `priority-classes.yaml`. Contrôle : `oc get priorityclass -o custom-columns=NOM:.metadata.name,VALEUR:.value,PREEMPTION:.preemptionPolicy`, les sept classes en `Never`, la classe d'inférence en `PreemptLowerPriority`. Retour arrière : supprimer les sept classes, inutilisées tant que l'étape 3 n'est pas faite.
2. **Quotas** (aucun effet sur ce qui tourne) : une copie de `01-namespace-quota.yaml` par namespace, **sauf** ceux dont un conteneur n'a pas encore de ressources explicites (voir l'étape 4). Contrôle : `oc describe resourcequota -n <namespace>`, l'utilisation actuelle tient sous les plafonds.
3. **Charges, par ordre d'impact** :
   - d'abord celles qui ne touchent aucun utilisateur : répartiteur, workflows, bus, embedding, sas web, passerelle de dev ;
   - puis, **quand personne n'utilise la discussion** : routeur de modèles, base relationnelle (environ 30 s sans base pour toutes les applications), identité (SSO coupé une à deux minutes), voix, images. Avant de redémarrer un pod en `imagePullPolicy: Always`, vérifier que le registre interne sert bien son image ;
   - une charge dont le manifeste n'est pas versionné (par exemple la forge) reçoit un patch : sauvegarde de l'objet hors du dépôt, essai `--dry-run=server`, puis application ;
   - un manifeste qui porte un autre changement dépendant d'un prérequis (par exemple un nouvel alias de modèle) attend ce prérequis, pour ne redémarrer le pod qu'une fois.

   Pour chacune : `oc diff -f <fichier>`, `oc apply -f <fichier>`, `oc rollout status`, puis `oc get pod -o jsonpath='{.items[0].spec.priorityClassName} {.items[0].status.containerStatuses[0].ready}'`, attendu `<classe> true`. Retour arrière : `oc rollout undo`.
4. **Socle, dans son créneau** : le pod de lecture du cluster reçoit sa classe et ses ressources explicites ; le recréer coupe les sessions qu'il porte. **Ensuite seulement**, le quota de son namespace.

## Contrôles

- Pas de préemption possible au-dessus du socle : `oc get pod -A -o custom-columns=NS:.metadata.namespace,NOM:.metadata.name,PRIO:.spec.priority | sort -k3 -n -r | head`.
- Classe de service : `oc get pod -o jsonpath='{.status.qosClass}'` ne doit jamais donner `BestEffort` pour une charge du socle.
- Les applications reconnectent seules leur pool de connexions après le redémarrage de la base : une ou deux erreurs de sonde au plus, sans redémarrage de pod.

## Leçons

- **`BestEffort` passe avant la classe** : un pod sans demande est le premier évincé sous pression mémoire, même dans une classe haute. Une classe de priorité ne protège que des pods qui déclarent leurs ressources.
- **Le quota après les ressources** : un quota sur les limits impose aux pods recréés la valeur par défaut du `LimitRange` ; posé avant que chaque conteneur ait ses ressources, il étouffe le premier pod recréé (1 CPU, 1 Gio).
- **La préemption ne regarde que les requests**, pas la consommation réelle ; un pod sans classe vaut 0 et part avant tout le reste.
- **Les déclencheurs d'image d'OpenShift** remplacent les tags par des empreintes dans les objets du cluster : réaligner le dépôt avant le premier `oc diff`, sinon il montre des écarts sans rapport.
