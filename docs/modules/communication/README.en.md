# Communication Module — the household's persistent chat and video calls

A module built on SophIA from existing free software: a persistent chat between household members, **Matrix** today (Synapse server, Element client), being replaced by **Converse.js and Prosody** (XMPP), a decision taken after a test on the real tablet; **Jitsi Meet** for video calls. Single sign-on through the platform's identity provider, no local account; everything stays at home, reached through the VPN.

| | |
|---|---|
| Status | **in service, in acceptance testing** in the reference installation: Matrix chat and video calls displayed in the cockpit; **first video call with picture** between a computer and the older tablet, in the cockpit, through the VPN; XMPP messaging proven on the older tablet (test), final version being designed, then Matrix dismantled; three-device and per-device acceptance testing to do; video calls go through the browser only; deployment recipe published as a procedure, without the manifests |
| Users | the household's groups; guests are refused by the identity provider, and by the video service itself |
| Model | none: no agent in the rooms for now; the unread summary for the interface is a deterministic computation |
| Platform building blocks | SSO, shared PostgreSQL 18, dedicated local volume, priority classes and quotas, VPN (video media) |
| Code | upstream software, images pinned by digest; a small adapter written for the video service; the reference installation's manifests are not published; architecture and recipe are described here |

Detailed documentation: [documentation.en.md](documentation.en.md). Deployment recipe: [`deploy/okd/office/`](../../../deploy/okd/office/README.en.md#persistent-chat-and-video-calls). Other modules: [private modules](../README.en.md).
