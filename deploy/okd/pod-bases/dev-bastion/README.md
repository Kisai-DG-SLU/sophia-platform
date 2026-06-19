# Bastion Dev — Passerelle SSH

Le bastion developpement fournit un acces SSH securise au namespace sandbox.

## Architecture

- `dev-gateway.yaml` — Deployment executant un serveur OpenSSH (port 2222) avec authentification stricte par cle
- `dev-infra-headless.yaml` — Service headless pour la decouverte de pods via DNS
- `gateway-strict-isolation.yaml` — NetworkPolicy limitant la passerelle au seul acces DNS et workspace

## Utilisation

1. Deployer la passerelle et les ressources associees
2. Se connecter en SSH a la passerelle avec sa cle configuree : `ssh -p 2222 app-user@<gateway-ip>`
3. Depuis la passerelle, se connecter aux workspaces de developpement dans le cluster
