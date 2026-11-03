# Communication Module — the household's persistent chat and video calls

A module built on SophIA from existing free software: a persistent chat between household members, **Converse.js and Prosody** (XMPP), instead of **Matrix** (a decision taken after a test on the real tablet); "tell", so that Sophia writes on the person's behalf; **Jitsi Meet** for video calls. Single sign-on through the platform's identity provider, no local account; everything stays at home, reached through the VPN.

| | |
|---|---|
| Status | **in service, in acceptance testing** in the reference installation: Matrix chat and video calls displayed in the dashboard; **first video call with picture** between a computer and the older tablet, in the dashboard, through the VPN; **final XMPP messaging in service** in the dashboard, with "tell"; Matrix readable until the end of acceptance testing, then dismantled; **household acceptance testing under way**, on every household device; video calls go through the browser only; deployment recipe published as a procedure, without the manifests |
| Users | the household's groups; guests are refused by the identity provider, and by the video service itself |
| Model | none in messaging: no agent in the rooms; "tell" goes through the chat's model for the intent, then a confirmation and a rule for sending; the unread summary is a deterministic computation |
| Platform building blocks | SSO, shared PostgreSQL 18, dedicated local volume, priority classes and quotas, VPN (video media) |
| Code | upstream software, images pinned by digest; a small adapter written for the video service; Prosody modules (household groups, "tell"), push gateway and Converse.js plugins written for the household; the reference installation's manifests are not published; architecture and recipe are described here |

Detailed documentation: [documentation.en.md](documentation.en.md). Deployment recipe: [`deploy/okd/office/`](../../../deploy/okd/office/README.en.md#persistent-chat-and-video-calls). Other modules: [private modules](../README.en.md).
