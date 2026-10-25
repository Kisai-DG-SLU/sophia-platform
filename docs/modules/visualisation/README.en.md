# Visualisation module — seeing what actually runs

A private module built on SophIA: a page that shows the **path of a request** (interface, dispatcher, durable workflows, executing agents, result) and, for each component, whether it is **theoretical, deployed or failing**, based on measurements rather than documentation. The same collector **checks the mirrors** of the forge's repositories.

| | |
|---|---|
| Status | in service in the reference installation (overview, replay, live, still to deploy; mirror check); compliance section designed |
| Users | the administration group only |
| Model | none: everything is deterministic |
| Platform building blocks | SSO, read access to the cluster API and metrics, read access to the event bus, forge |
| Code | private; this page describes the architecture and the rules so that an equivalent can be built |

Detailed documentation: [documentation.en.md](documentation.en.md). Other modules: [private modules](../README.en.md).
