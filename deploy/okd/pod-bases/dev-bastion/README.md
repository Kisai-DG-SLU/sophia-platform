# Bastion Dev — Passerelle SSH

Le bastion développement fournit un accès SSH sécurisé au namespace sandbox.

## Architecture

- `dev-gateway.yaml` — Deployment exécutant un serveur OpenSSH (port 2222) avec authentification stricte par clé ; classe de priorité `sophia-dev`
- `scc-dev-gateway.yaml` — SCC propre à la passerelle (copie d'`anyuid` plus la seule capacité `SYS_CHROOT`, dont sshd a besoin pour la séparation de privilèges), liée à son seul compte, demandée par l'annotation `openshift.io/required-scc`
- `dev-infra-headless.yaml` — Service headless pour la découverte de pods via DNS
- `dev-gateway-service.yaml` — deux Services : `dev-gateway` en ClusterIP seule (sans NodePort, qui serait servi sur le réseau local) et `dev-gateway-vpn`, externalIP sur l'adresse du VPN, port réservé à la plage d'administration par le filtre ([`../../host/wireguard/`](../../host/wireguard/README.md), section 7)
- `gateway-strict-isolation.yaml` — NetworkPolicy limitant la passerelle au seul accès DNS et workspace

## Sécurité du namespace

| Élément | État |
|---|---|
| SCC `privileged` retirée de tous les comptes du namespace : un pod privilégié y est refusé, y compris pour l'agent de développement, administrateur du namespace | en service |
| Passerelle sous sa SCC propre, sans privilège ; `anyuid` gardé | en service |
| AdminNetworkPolicy sur tout le namespace, règle d'admission qui n'accepte que les images du registre interne | prévu |
| Un cluster virtuel par projet, recréé depuis la forge par un workflow | prévu, rien d'installé |

Retrait de la SCC `privileged` : sauvegarde des liaisons hors du dépôt, SCC propre appliquée avant le retrait, puis essais en `--dry-run=server` (un pod privilégié doit être refusé sous chaque compte, la passerelle doit être admise sous sa SCC) ; la passerelle redémarre une fois et répond en SSH. Retour arrière : réappliquer les liaisons sauvegardées.

## Variables

| Variable | Rôle | Exemple |
|---|---|---|
| `${SANDBOX_NAMESPACE}` | namespace de développement | `sandbox` |
| `${GATEWAY_SERVICE_ACCOUNT}` | compte de la passerelle, seul lié à la SCC | `dev-gateway-sa` |
| `${INTERNAL_REGISTRY}` | registre interne du cluster | `image-registry.openshift-image-registry.svc:5000` |
| `${VPN_SERVER_IP}` | adresse du serveur sur le VPN, externalIP de `dev-gateway-vpn` | `a.b.c.1` |
| `${DEV_GATEWAY_VPN_PORT}` | port SSH de la passerelle sur cette adresse, distinct des ports de Forgejo | — |
| `${DEV_GATEWAY_CLUSTER_IP}` | ClusterIP fixée de `dev-gateway`, point d'arrivée du secours d'administration par le nœud | une adresse libre du réseau des Services |

## Utilisation

1. Appliquer `scc-dev-gateway.yaml`, puis déployer la passerelle et les ressources associées
2. Se connecter en SSH à la passerelle avec sa clé configurée, par le VPN : `ssh -p ${DEV_GATEWAY_VPN_PORT} app-user@${VPN_SERVER_IP}`
3. Depuis la passerelle, se connecter aux workspaces de développement dans le cluster
