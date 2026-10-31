# Orchestration — `sophia-core`

Le cœur de la plateforme : le routeur de modèles (LiteLLM), la base PostgreSQL partagée, le bus d'événements (RabbitMQ) et le moteur de workflows durables (Temporal). Tout ce qui parle à un modèle passe par LiteLLM ; aucune application n'appelle un fournisseur directement.

## Composants

| Dossier | Rôle |
|---|---|
| `litellm/` | routeur de modèles : alias stables (`sophia-local`, `sophia-local-fond`, `sophia-embedder`, `sophia-stt`, `sophia-tts`, et des alias distants pour le développement), clés virtuelles restreintes, coûts |
| [`postgres18/`](postgres18/) | **PostgreSQL 18**, instance commune de toutes les bases (LiteLLM, Keycloak, interface, Temporal, mémoire, validations humaines, bureautique, modules), un rôle propriétaire par base, sans superutilisateur réseau ; volume logique dédié |
| `postgres/` | ancienne instance PostgreSQL 15, remplacée par `postgres18/` : à 0 réplique pendant une garde de 7 jours, puis retirée ; `pv.yaml` porte la variable `${NODE_NAME}` (nœud du volume) |
| [`rabbitmq/`](rabbitmq/) | bus d'événements, dont le répartiteur est le seul éditeur ; interface d'administration derrière Keycloak |
| [`temporal/`](temporal/) | workflows durables des délégations (reprise après panne) |
| [`repartiteur/`](repartiteur/) | répartiteur des délégations : règles sans modèle, seul client de Temporal, seul éditeur des événements |
| `network/` | sortie du namespace (EgressFirewall), entrée de Postgres, refus par défaut en entrée (`default-deny-ingress.yaml`) |
| `00-namespace-guardrails.yaml` | `ResourceQuota` et `LimitRange` du namespace |

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Alias de modèles | les applications demandent un **rôle** (`sophia-think`), jamais un modèle | changer de modèle ou de fournisseur ne touche qu'à `litellm/config.yaml` |
| Modèle local | `sophia-local` → serveur llama.cpp de `sophia-inference`, coût 0, `supports_vision`, `max_input_tokens` 61 440 | même interface que les modèles distants ; la borne correspond à la fenêtre par discussion du serveur ([`../inference/`](../inference/)) |
| Alias de fond | `sophia-local-fond` → même serveur, `max_parallel_requests: 1`, pour les agents et les tâches non urgentes des applications | laisse à la discussion les autres emplacements du serveur ; **en flux, le verrou est relâché à la première réponse** et ne couvre pas la génération : il ne vaut que pour les appels sans flux, et les missions des agents sont bornées par le [répartiteur](repartiteur/) |
| Embedding | `sophia-embedder` → service d'embedding de `sophia-memory`, coût 0 | l'ingestion et le service mémoire appellent l'embedding par le routeur, comme tout le reste |
| Voix | `sophia-stt` et `sophia-tts` → service vocal de `sophia-inference`, coût 0 | la voix passe par le même routeur, les mêmes clés et les mêmes journaux |
| Clés restreintes | chaque client (interface, agents) a une clé limitée à une liste de modèles ; `add-model-to-keys.py` y ajoute un nouvel alias | un nouvel alias est invisible tant qu'il n'est pas ajouté aux clés qui en ont besoin |
| Une clé par agent | `agent-<nom>` (`litellm/create-agent-key.py`) : alias de fond et embedding seulement, 120 requêtes par minute ; Secret `litellm-cle-<agent>` dans le namespace des agents | la clé maître administre le routeur (clés, budgets) et ouvre tous les modèles : elle ne sort pas du pod du routeur |
| Tarifs | recopiés de l'API du fournisseur par `sync-pricing.py`, jamais à la main | le coût affiché suit le prix réel |
| Clés par usage | une clé virtuelle par appelant (`litellm/create-virtual-key.py`) : la voix du chat (ses deux alias, débit propre), chaque pod de développement (les modèles du chat sans la voix), chaque application ; jamais `*` | la règle est tenue par le routeur, quelle que soit la requête ; voir [Modèles par rôle](../../../docs/concepts/13-modeles-par-role.md) |
| Bascule sans coupure | sondes `readiness` (`/health/readiness`, 3 s) et `liveness` (`/health/liveliness`), stratégie `RollingUpdate` (`maxSurge: 1`, `maxUnavailable: 0`) | sans sonde, le pod était déclaré prêt avant d'écouter : chaque redémarrage (configuration, clé maître) coupait le chat |
| Journaux de LiteLLM | `INFO`, pas `DEBUG` | en `DEBUG`, chaque requête entière (conversations privées, photos en base64) part dans les journaux et ralentit les grosses requêtes |
| Entrée | refus par défaut en entrée, puis une règle par service ; le routeur de modèles (`litellm/network-policy.yaml`) n'admet que les namespaces de ses appelants relevés, le routeur d'entrée et le réseau du nœud | sans règle, tout pod du cluster joint le routeur et dépense ses clés ; par namespace et non par pod, pour couvrir les pods éphémères |
| Garde-fous | quota du namespace (16 Gi, 12 CPU, 15 pods) et limites explicites sur **chaque** conteneur, builds compris | un conteneur sans limite reçoit 512 Mi par défaut : LiteLLM, Postgres ou un build mourraient en OOM. **Appliquer les limites avant le quota** |
| LiteLLM | 768 Mi demandés, 2 Gi et 2 CPU au plus | ≈ 550 Mi au repos, les photos gonflent les requêtes ; le plafond CPU borne aussi le gel d'un comptage de tokens pathologique |
| Postgres | **version 18**, image **figée par digest**, `IfNotPresent`, `Recreate`, 2 Gi, sondes `pg_isready`, volume logique dédié extensible à chaud | un redémarrage ne tire jamais une autre version ; jamais deux Postgres sur le même volume local ; l'image dérive ses tampons de la limite mémoire ; détails et migration dans [`postgres18/`](postgres18/) |
| Rétention du routeur | journal détaillé des appels (`LiteLLM_SpendLogs`) gardé 30 jours (`maximum_spend_logs_retention_period`) ; les agrégats quotidiens restent | environ 3 Ko par appel : sans rétention, la table grossirait sans fin |
| Sortie | tout refusé sauf Services et pods du cluster, le fournisseur des modèles distants, les registres et dépôts de paquets des builds, et le fournisseur d'identité en 443 | RabbitMQ lit les clés de signature de Keycloak par son nom public, qui résout vers le nœud, hors des réseaux internes |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${AGENT_NAMESPACE}` | namespace des agents du panthéon | `agents` |
| `${CONFIG_REPO_URL}` | dépôt Git interne qui contient ce dossier (builds) | `http://git.example.internal/org/platform.git` |
| `${LITELLM_HOST}` | nom DNS de LiteLLM, résolu vers l'adresse du VPN | `llm.example.org` |
| `${IDP_HOST}` | nom public du fournisseur d'identité | `auth.example.org` |

## Secrets (jamais versionnés)

| Secret | Clés |
|---|---|
| `llm-api-keys` | `DEEPINFRA_API_KEY`, `LITELLM_MASTER_KEY`, `DATABASE_URL`, `LITELLM_SALT_KEY` (chiffrement de ce que LiteLLM garde en base : à poser **à la valeur actuelle de la clé maître** avant de renouveler celle-ci) |
| `litellm-cle-<agent>` | `cle` : clé virtuelle de l'agent (namespace des agents) |
| `postgres-sophia-18-creds`, `postgres-18-<rôle>` | `password` : voir [`postgres18/`](postgres18/) |
| `forgejo-creds` | accès en lecture du build au dépôt interne |

## Procédure (l'administrateur)

1. Limites explicites d'abord : `litellm/deployment.yaml`, `litellm/build.yaml` — `--dry-run=server`, puis `apply`.
2. Garde-fous : `00-namespace-guardrails.yaml`, puis `oc describe quota -n sophia-core`. Puis la base de données, par sa propre procédure : [`postgres18/`](postgres18/).
3. Réseau : `network/policies.yaml`, `postgres18/03-network.yaml`, `litellm/network-policy.yaml`, puis **seulement ensuite** `network/default-deny-ingress.yaml`. Avant et après : le routeur répond par sa Route et depuis chaque namespace appelant ; retour arrière : supprimer `default-deny-ingress`.
4. Routeur : `litellm/config.yaml` (`oc diff` d'abord : seuls les alias attendus changent), redémarrage de LiteLLM, puis `add-model-to-keys.py` à blanc et avec `--apply` pour chaque nouvel alias :

```bash
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local < litellm/add-model-to-keys.py           # à blanc
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local --apply < litellm/add-model-to-keys.py   # applique
```

Le script lit la clé maître dans l'environnement du pod, ne l'affiche jamais, et ne touche que les clés qui ont déjà le modèle de référence (`sophia-think` par défaut, ou `--reference=<alias>`, par exemple `--reference=sophia-local` pour ouvrir l'alias de fond aux clés des applications).

5. **Clés des agents**, en trois temps.
   1. Clés et Secrets, sans effet sur ce qui tourne : `create-agent-key.py <agent> --dry-run`, puis la forme `--eval CLE_AGENT`, et un Secret créé par l'entrée standard (`printf '%s' "$CLE_AGENT" | oc create secret generic litellm-cle-<agent> --from-file=cle=/dev/stdin`), puis `unset CLE_AGENT`. Aucune clé n'est affichée.
   2. Un `apply` par agent ([`../hermes-system/`](../hermes-system/)), un agent à la fois. Contrôle dans l'agent : `/key/info` avec sa propre clé renvoie `agent-<nom>` et ses deux modèles, puis une mission « pong ».
   3. Quand plus aucun agent ne la lit : retirer la clé maître du Secret des agents, poser `LITELLM_SALT_KEY`, puis renouveler la clé maître. Chaque valeur passe par `--patch-file=/dev/stdin`, jamais dans les arguments d'une commande. Relever avant tous les consommateurs de la clé maître (scripts, postes d'administration).
6. **Clés par usage** (voix, pod de développement, application) : `create-virtual-key.py`, toujours à blanc d'abord.

```bash
oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --modeles <m1>,<m2> --rpm <N> --dry-run < litellm/create-virtual-key.py
oc exec -i -n sophia-core deploy/litellm -- python3 - <alias> --comme <alias-de-référence> --sans <m1> --dry-run < litellm/create-virtual-key.py
oc exec -i -n sophia-core deploy/litellm -- python3 - --info <alias> < litellm/create-virtual-key.py
```

La création remplace `--dry-run` par `--eval <VARIABLE>` dans un `eval "$(…)"`, puis la clé part dans le Secret de l'appelant par l'entrée standard. `--info` donne les modèles, les limites et le début de l'empreinte SHA-256 de la clé : comparé à l'empreinte de la valeur du Secret, il prouve que c'est la bonne clé, sans l'afficher.
