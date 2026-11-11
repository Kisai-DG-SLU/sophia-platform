# Scripts

The reference installation's operating scripts (backups, certificate rotation, the administrator's workstation) are not published: they carry that installation's paths, names and secrets. The scripts needed to reproduce the platform are published **next to the recipe that uses them**, driven by variables (a few node paths, in the inference and tools scripts, are still to be turned into variables):

| Recipe | Scripts | Role |
|---|---|---|
| [Model router](../okd/core/README.en.md) | `okd/core/litellm/*.py` | virtual keys per use and per agent, a key's models, prices copied from the provider |
| [Identity](../okd/identity/README.en.md) | `ajouter-mappeur-audience.py`, `temporal-keycloak.py`, `sessions/acl.sh` | audiences of the relayed token, Temporal's client, session accounts |
| [Chat interface](../okd/apps/chat-interface/README.en.md) | `entrypoint.sh`, `render-*.py` | configuration rendered at start-up |
| [VPN](../okd/host/wireguard/README.en.md) | `add-peer.sh`, `wg-filter*`, `test-*.sh` | peers, the node's filter and its tests |
| [Inference](../okd/inference/README.en.md) | `fetch-*.sh`, `export-voices.sh`, `bench.py` | models and voices on the node, measurement bench |
| [Memory](../okd/memory/README.en.md) | `qdrant-schema.py` | vector database collections |
| [Monitoring](../okd/monitoring/README.en.md) | `*-ajout.py`, `node-metrics/` | alert routes, node exporter |
| [Tools](../okd/skills/README.en.md) | `fetch-geo-data.sh`, `geo_build.py` | local geographic data |
| [Development assistant](../okd/hermes-system/assistant/README.en.md) | `ws` | one session per project |

Each script's usage, dry run included when it has one, is in its recipe.
