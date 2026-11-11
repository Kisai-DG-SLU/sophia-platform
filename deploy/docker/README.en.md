# Base images (historical, not maintained)

These images date from the June 2026 base. None is built or deployed today in the reference installation. They are kept as history and no longer follow the platform's rules (images pinned by digest, unprivileged accounts, dedicated namespaces). Each file carries the same note at the top.

| Folder | State | Version that is authoritative |
|---|---|---|
| `core/` | old copy | [`okd/pod-bases/core/Containerfile`](../okd/pod-bases/core/), base image that is built |
| `litellm/` | old copy | [`okd/core/litellm/Containerfile`](../okd/core/README.en.md), model router image that is built |
| `runner/` | continuous integration runner, stopped (0 replicas) | [`okd/pod-bases/runner/`](../okd/pod-bases/runner/README.en.md) |
| `dev-assist/`, `dev-bastion/`, `workspaces/` | never deployed | — |
