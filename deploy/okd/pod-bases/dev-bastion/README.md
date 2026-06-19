# Dev Bastion — SSH Gateway

The dev bastion provides secure SSH access into the sandbox namespace.

## Architecture

- `dev-gateway.yaml` — Deployment running an OpenSSH server (port 2222) with strict key-based authentication
- `dev-infra-headless.yaml` — Headless service for DNS-based pod discovery
- `gateway-strict-isolation.yaml` — NetworkPolicy limiting the gateway to DNS and workspace access only

## Usage

1. Deploy the gateway and related resources
2. SSH into the gateway using your configured key: `ssh -p 2222 app-user@<gateway-ip>`
3. From the gateway, connect to dev workspaces within the cluster
