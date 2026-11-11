# CI Runners — Forgejo Actions

> **Historical, not maintained.** Continuous integration runner from the June 2026 base, stopped (0 replicas) in the reference installation; its removal is pending. Its manifests have not followed today's rules. Each file carries the same note.

This directory contains deployment manifests for Forgejo Action Runners.

## Resources

- `runner-gpu.yaml` — Deployment of a GPU-enabled runner for CI workloads requiring GPU acceleration
- `policy-runner.yaml` — NetworkPolicy allowing runner-to-Forgejo API access
- `Dockerfile` — at `deploy/docker/runner/Dockerfile`
