# Bastion Dev — Passerelle SSH

Le bastion developpement fournit un acces SSH securise au namespace sandbox.

## Architecture

- `dev-gateway.yaml` — Deployment executant un serveur OpenSSH (port 2222) avec authentification stricte par cle ; classe de priorite `sophia-dev`
- `scc-dev-gateway.yaml` — SCC propre a la passerelle (copie d'`anyuid` plus la seule capacite `SYS_CHROOT`, dont sshd a besoin pour la separation de privileges), liee a son seul compte, demandee par l'annotation `openshift.io/required-scc`
- `dev-infra-headless.yaml` — Service headless pour la decouverte de pods via DNS
- `dev-gateway-service.yaml` — deux Services : `dev-gateway` en ClusterIP seule (sans NodePort, qui serait servi sur le reseau local) et `dev-gateway-vpn`, externalIP sur l'adresse du VPN, port reserve a la plage d'administration par le filtre ([`../../host/wireguard/`](../../host/wireguard/README.md), section 7)
- `gateway-strict-isolation.yaml` — NetworkPolicy limitant la passerelle au seul acces DNS et workspace

## Securite du namespace

| Element | Etat |
|---|---|
| SCC `privileged` retiree de tous les comptes du namespace : un pod privilegie y est refuse, y compris pour l'agent de developpement, administrateur du namespace | en service |
| Passerelle sous sa SCC propre, sans privilege ; `anyuid` garde | en service |
| AdminNetworkPolicy sur tout le namespace, regle d'admission qui n'accepte que les images du registre interne | prevu |
| Un cluster virtuel par projet, recree depuis la forge par un workflow | prevu, rien d'installe |

Retrait de la SCC `privileged` : sauvegarde des liaisons hors du depot, SCC propre appliquee avant le retrait, puis essais en `--dry-run=server` (un pod privilegie doit etre refuse sous chaque compte, la passerelle doit etre admise sous sa SCC) ; la passerelle redemarre une fois et repond en SSH. Retour arriere : reappliquer les liaisons sauvegardees.

## Variables

| Variable | Role | Exemple |
|---|---|---|
| `${SANDBOX_NAMESPACE}` | namespace de developpement | `sandbox` |
| `${GATEWAY_SERVICE_ACCOUNT}` | compte de la passerelle, seul lie a la SCC | `dev-gateway-sa` |
| `${INTERNAL_REGISTRY}` | registre interne du cluster | `image-registry.openshift-image-registry.svc:5000` |
| `${VPN_SERVER_IP}` | adresse du serveur sur le VPN, externalIP de `dev-gateway-vpn` | `a.b.c.1` |
| `${DEV_GATEWAY_VPN_PORT}` | port SSH de la passerelle sur cette adresse, distinct des ports de Forgejo | — |

## Utilisation

1. Appliquer `scc-dev-gateway.yaml`, puis deployer la passerelle et les ressources associees
2. Se connecter en SSH a la passerelle avec sa cle configuree, par le VPN : `ssh -p ${DEV_GATEWAY_VPN_PORT} app-user@${VPN_SERVER_IP}`
3. Depuis la passerelle, se connecter aux workspaces de developpement dans le cluster
