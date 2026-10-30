# Shopping module — a drive-through grocery basket prepared by the assistant

A private module built on SophIA: from a shopping list (the [Cooking module](../cuisine/README.en.md)'s, free input, recurring items), it **chooses the products** of a drive-through grocery store according to the household's rules and **fills the real basket**. The time slot and payment always stay with the human, in the store's own app.

| | |
|---|---|
| State | in service in the reference install; a few fixes under acceptance testing; not yet shown in the interface's cockpit (opened separately) |
| Users | the household's adults (the only ones allowed to write); no child account |
| Shape | an engine exposed over **MCP** (Cooking module, chat), a fallback web page, a remote browser in the airlock |
| Model | `sophia-local`, to **understand** a list line — never to choose a product |
| Code | private; this page describes the architecture and rules |

Detailed documentation: [documentation.en.md](documentation.en.md). Other modules: [private modules](../README.en.md).
