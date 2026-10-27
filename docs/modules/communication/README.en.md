# Communication Module — the household's persistent chat and video calls

A module built on SophIA from existing free software: **Matrix** (Synapse server, Element client) for a persistent chat between household members, **Jitsi Meet** for video calls. Single sign-on through the platform's identity provider, no local account; everything stays at home, reached through the VPN.

| | |
|---|---|
| Status | **installed, in acceptance testing** in the reference installation: both services run and the first sign-in is done; acceptance testing (multi-device call, guest refused, protected account, mobile clients) is still to do; deployment recipe published as a procedure, without the manifests |
| Users | the household's groups; guests are refused by the identity provider, and by the video service itself |
| Model | none: no agent in the rooms for now |
| Platform building blocks | SSO, shared PostgreSQL 18, dedicated local volume, priority classes and quotas, VPN (video media) |
| Code | upstream software, images pinned by digest; a small adapter written for the video service; the reference installation's manifests are not published; architecture and recipe are described here |

Detailed documentation: [documentation.en.md](documentation.en.md). Deployment recipe: [`deploy/okd/office/`](../../../deploy/okd/office/README.en.md#persistent-chat-and-video-calls). Other modules: [private modules](../README.en.md).
