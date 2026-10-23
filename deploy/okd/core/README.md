# Orchestration — `sophia-core`

Le cœur de la plateforme : le routeur de modèles (LiteLLM), la base PostgreSQL partagée, le bus d'événements (RabbitMQ) et le moteur de workflows durables (Temporal). Tout ce qui parle à un modèle passe par LiteLLM ; aucune application n'appelle un fournisseur directement.

## Composants

| Dossier | Rôle |
|---|---|
| `litellm/` | routeur de modèles : alias stables (`sophia-routine`, `sophia-think`, `sophia-architect`, `sophia-local`, `sophia-stt`, `sophia-tts`), clés virtuelles restreintes, coûts |
| `postgres/` | PostgreSQL 15 : bases de LiteLLM, de Keycloak, de l'interface, de Temporal et des modules, un compte par base |
| [`rabbitmq/`](rabbitmq/) | bus d'événements des agents, interface d'administration derrière Keycloak |
| [`temporal/`](temporal/) | workflows durables des agents (délégation, reprise après panne) |
| `network/` | sortie du namespace (EgressFirewall) et entrée de Postgres |
| `00-namespace-guardrails.yaml` | `ResourceQuota` et `LimitRange` du namespace |

## Choix

| Élément | Choix | Raison |
|---|---|---|
| Alias de modèles | les applications demandent un **rôle** (`sophia-think`), jamais un modèle | changer de modèle ou de fournisseur ne touche qu'à `litellm/config.yaml` |
| Modèle local | `sophia-local` → serveur llama.cpp de `sophia-inference`, coût 0, `supports_vision`, `max_input_tokens` 61 440 | même interface que les modèles distants ; la borne correspond à la fenêtre par discussion du serveur ([`../inference/`](../inference/)) |
| Voix | `sophia-stt` et `sophia-tts` → service vocal de `sophia-inference`, coût 0 | la voix passe par le même routeur, les mêmes clés et les mêmes journaux |
| Clés restreintes | chaque client (interface, agents) a une clé limitée à une liste de modèles ; `add-model-to-keys.py` y ajoute un nouvel alias | un nouvel alias est invisible tant qu'il n'est pas ajouté aux clés qui en ont besoin |
| Tarifs | recopiés de l'API du fournisseur par `sync-pricing.py`, jamais à la main | le coût affiché suit le prix réel |
| Journaux de LiteLLM | `INFO`, pas `DEBUG` | en `DEBUG`, chaque requête entière (conversations privées, photos en base64) part dans les journaux et ralentit les grosses requêtes |
| Garde-fous | quota du namespace (16 Gi, 12 CPU, 15 pods) et limites explicites sur **chaque** conteneur, builds compris | un conteneur sans limite reçoit 512 Mi par défaut : LiteLLM, Postgres ou un build mourraient en OOM. **Appliquer les limites avant le quota** |
| LiteLLM | 768 Mi demandés, 2 Gi et 2 CPU au plus | ≈ 550 Mi au repos, les photos gonflent les requêtes ; le plafond CPU borne aussi le gel d'un comptage de tokens pathologique |
| Postgres | image **figée par digest**, `IfNotPresent`, `Recreate`, 2 Gi | un redémarrage ne tire jamais une autre version ; jamais deux Postgres sur le même volume local ; l'image dérive ses tampons de la limite mémoire |
| Sortie | tout refusé sauf Services et pods du cluster, le fournisseur des modèles distants, les registres et dépôts de paquets des builds, et le fournisseur d'identité en 443 | RabbitMQ lit les clés de signature de Keycloak par son nom public, qui résout vers le nœud, hors des réseaux internes |

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${CONFIG_REPO_URL}` | dépôt Git interne qui contient ce dossier (builds) | `http://git.example.internal/org/platform.git` |
| `${LITELLM_HOST}` | nom DNS de LiteLLM, résolu vers l'adresse du VPN | `llm.example.org` |
| `${IDP_HOST}` | nom public du fournisseur d'identité | `auth.example.org` |

## Secrets (jamais versionnés)

| Secret | Clés |
|---|---|
| `llm-api-keys` | `DEEPINFRA_API_KEY`, `LITELLM_MASTER_KEY`, `DATABASE_URL` |
| `postgres-sophia-creds` | `username`, `password` (`openssl rand -base64 24`) |
| `forgejo-creds` | accès en lecture du build au dépôt interne |

## Procédure (l'administrateur)

1. Limites explicites d'abord : `litellm/deployment.yaml`, `litellm/build.yaml`, `postgres/instance.yaml` — `--dry-run=server`, puis `apply`.
2. Garde-fous : `00-namespace-guardrails.yaml`, puis `oc describe quota -n sophia-core`.
3. Réseau : `network/policies.yaml`, `postgres/allow-apps-to-postgres.yaml`.
4. Routeur : `litellm/config.yaml` (`oc diff` d'abord : seuls les alias attendus changent), redémarrage de LiteLLM, puis `add-model-to-keys.py` à blanc et avec `--apply` pour chaque nouvel alias :

```bash
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local < litellm/add-model-to-keys.py           # à blanc
oc exec -i -n sophia-core deploy/litellm -- python3 - sophia-local --apply < litellm/add-model-to-keys.py   # applique
```

Le script lit la clé maître dans l'environnement du pod, ne l'affiche jamais, et ne touche que les clés qui ont déjà le modèle de référence (`sophia-think`).
