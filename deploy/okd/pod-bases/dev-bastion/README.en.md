# Dev Bastion — SSH Gateway

The dev bastion provides secure SSH access into the sandbox namespace.

## Architecture

- `dev-gateway.yaml` — Deployment running an OpenSSH server (port 2222) with strict key-based authentication; `sophia-dev` priority class
- `scc-dev-gateway.yaml` — SCC specific to the gateway (a copy of `anyuid` plus the single `SYS_CHROOT` capability, which sshd needs for privilege separation), bound to its account only, requested through the `openshift.io/required-scc` annotation
- `dev-infra-headless.yaml` — Headless service for DNS-based pod discovery
- `gateway-strict-isolation.yaml` — NetworkPolicy limiting the gateway to DNS and workspace access only

## Namespace security

| Element | Status |
|---|---|
| `privileged` SCC removed from every account of the namespace: a privileged pod is refused there, including for the development agent, administrator of the namespace | in service |
| Gateway under its own SCC, without privilege; `anyuid` kept | in service |
| AdminNetworkPolicy on the whole namespace, admission rule accepting images from the internal registry only | planned |
| One virtual cluster per project, recreated from the forge by a workflow | planned, nothing installed |

Removing the `privileged` SCC: back up the bindings outside the repository, apply the dedicated SCC before the removal, then test with `--dry-run=server` (a privileged pod must be refused under each account, the gateway must be admitted under its SCC); the gateway restarts once and answers over SSH. Rollback: re-apply the saved bindings.

## Variables

| Variable | Role | Example |
|---|---|---|
| `${SANDBOX_NAMESPACE}` | development namespace | `sandbox` |
| `${GATEWAY_SERVICE_ACCOUNT}` | gateway account, the only one bound to the SCC | `dev-gateway-sa` |
| `${INTERNAL_REGISTRY}` | cluster internal registry | `image-registry.openshift-image-registry.svc:5000` |

## Usage

1. Apply `scc-dev-gateway.yaml`, then deploy the gateway and related resources
2. SSH into the gateway using your configured key: `ssh -p 2222 app-user@<gateway-ip>`
3. From the gateway, connect to dev workspaces within the cluster
