# Cooking module — a household's menus, recipes and shopping

A private module built on SophIA: it keeps a household's **meal plan** (lunch and dinner, per person), its **recipe catalogue** and its **shopping list**. The model **invents** recipes; **rules decide** whether they enter the catalogue.

| | |
|---|---|
| State | in service in the reference install |
| Users | the household's adults (full access), children (protected accounts, read-only) |
| Model | `sophia-local` (local inference) by default, through the model router |
| Platform bricks | SSO, model router, shared PostgreSQL 18, `image` MCP tool, web airlock, chat interface, Shopping module |
| Code | private; this page describes the architecture and rules needed to build an equivalent |

Detailed documentation: [documentation.en.md](documentation.en.md). Other modules: [private modules](../README.en.md).
