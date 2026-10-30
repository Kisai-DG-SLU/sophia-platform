# Office Module — the household's files and documents

A module built on SophIA from existing free software: **La Suite Drive** ("Files") to store and share files, **Collabora Online** to edit documents in the browser. Each person has their own space, private by default; from the chat, Sophia finds one of the person's files and opens it through a button. In the interface's cockpit, Files is displayed in the centre, under the name "Desk", and a document opens there in its own frame.

| | |
|---|---|
| Status | in service in the reference installation; display in the cockpit in service, in acceptance testing; "Sophia, open document X" in service, in acceptance testing; Sophia writing into the open document in service, verified; recipe published as a procedure, without the manifests; detailed acceptance testing still to do |
| Users | every account of the realm, each in their own space; guests do not get the search tool in the chat |
| Model | none inside the module; from the chat, reading a document's content is reserved to local models |
| Platform building blocks | SSO, shared PostgreSQL 18, common S3 object storage, priority classes and quotas, chat interface, "files" MCP tool |
| Code | upstream software, images pinned by digest; the reference installation's manifests are not published; architecture and recipe are described here |

Detailed documentation: [documentation.en.md](documentation.en.md). Deployment recipe: [`deploy/okd/office/`](../../../deploy/okd/office/README.en.md). Other modules: [private modules](../README.en.md).
