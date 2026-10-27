# Private modules — what you can build with SophIA

A **module** is an application for the household or the organisation, built on the platform's bricks instead of reinventing them: single sign-on, model router and local model, shared PostgreSQL database, MCP tools, chat interface. The modules below run in the reference install; their code is **private** (it carries a household's own data and settings), but their architecture and rules are described here so that a third party can build equivalents.

| Module | What it does | Platform bricks |
|---|---|---|
| [Cooking](cuisine/README.en.md) | meal plan, recipe catalogue, rule-bound recipe generation, shopping | SSO, local model, PostgreSQL, `image` tool, web airlock, MCP to the chat and to the Shopping module |
| [Shopping](courses/README.en.md) | choosing a drive-through store's products according to household rules, filling the real basket, express basket from the chat | SSO, local model, PostgreSQL, remote browser in the airlock, MCP |
| [School](ecole/README.en.md) | playful school from primary to lower secondary, hints without the answer, report book, reading photographed homework | SSO and roles, local model with vision, chat interface, content through Git |
| [Office](bureautique/README.en.md) | each person's files, private by default, document editing in the browser, search and reading from the chat | SSO, PostgreSQL 18, common S3, "files" MCP tool under the person's identity |
| [Communication](communication/README.en.md) | persistent chat between household members and video calls, at home only; installed, in acceptance testing | SSO, PostgreSQL 18, dedicated local volume, VPN for video media |
| [Visualisation](visualisation/README.en.md) | measured state of each component and path of a request, hourly check of repository mirrors; compliance planned | SSO, read access to the cluster API and metrics, read access to the event bus, forge |

## The common pattern

| Rule | How it applies |
|---|---|
| **The model analyses, rules decide, a tool executes** | the model proposes (a recipe, the understanding of a shopping line, a hint) in strict JSON; a deterministic validator accepts or rejects with its reasons; only code acts (saving, filling a basket, publishing) |
| **A check around every model output** | cited sources = pages actually read; brand accepted only if written; a hint never contains the answer; an image goes through the classifier |
| **Identity comes from the platform, never from the model** | header set by oauth2-proxy on pages; parameter injected by the interface (`sophia/injecte`) into MCP tools; list of allowed members checked by the server |
| **Protected accounts** | children read, never trigger a purchase or a costly generation; their data never goes to a remote model |
| **Closed-list networking** | each module only opens the flows it needs (ingress from the router and the interface, egress to the model router, identity provider, its database, the tools it uses); Internet access goes through the airlock |
| **One module = one pod, one database, one group** | pod with its oauth2-proxy on its own address (an application served under the interface's origin would have all of the person's rights over the chat), own database and role in the shared PostgreSQL, realm group; build from the internal forge |
| **The human keeps control of the irreversible** | validating a list, payment, marking a dictation |

To plug a module into the chat: expose an MCP server (see the [tool contract](../../deploy/okd/skills/README.en.md)), add it to the [interface](../../deploy/okd/apps/chat-interface/README.en.md)'s `SOPHIA_MCP_URLS` and open the flow in its NetworkPolicy; to give it a database: a block in [`allow-apps-to-postgres.yaml`](../../deploy/okd/core/postgres/allow-apps-to-postgres.yaml).
