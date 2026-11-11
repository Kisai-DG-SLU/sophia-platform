# Scripts

Les scripts d'exploitation de l'installation de référence (sauvegardes, rotation des certificats, poste de l'administrateur) ne sont pas publiés : ils portent les chemins, les noms et les secrets de cette installation. Les scripts utiles pour reproduire la plateforme sont publiés **à côté de la recette qui s'en sert**, paramétrés par des variables (quelques chemins du nœud, dans les scripts de l'inférence et des outils, restent à mettre en variables) :

| Recette | Scripts | Rôle |
|---|---|---|
| [Routeur de modèles](../okd/core/README.md) | `okd/core/litellm/*.py` | clés virtuelles par usage et par agent, modèles d'une clé, tarifs recopiés du fournisseur |
| [Identité](../okd/identity/README.md) | `ajouter-mappeur-audience.py`, `temporal-keycloak.py`, `sessions/acl.sh` | audiences du jeton relayé, client de Temporal, comptes des sessions |
| [Interface de discussion](../okd/apps/chat-interface/README.md) | `entrypoint.sh`, `render-*.py` | configuration rendue au démarrage |
| [VPN](../okd/host/wireguard/README.md) | `add-peer.sh`, `wg-filter*`, `test-*.sh` | pairs, filtre du nœud et ses essais |
| [Inférence](../okd/inference/README.md) | `fetch-*.sh`, `export-voices.sh`, `bench.py` | modèles et voix sur le nœud, banc de mesure |
| [Mémoire](../okd/memory/README.md) | `qdrant-schema.py` | collections de la base vectorielle |
| [Métrologie](../okd/monitoring/README.md) | `*-ajout.py`, `node-metrics/` | routes d'alerte, exporteur du nœud |
| [Outils](../okd/skills/README.md) | `fetch-geo-data.sh`, `geo_build.py` | données géographiques locales |
| [Assistant de développement](../okd/hermes-system/assistant/README.md) | `ws` | une session par projet |

Le mode d'emploi de chaque script, essai à blanc compris quand il en a un, est dans sa recette.
