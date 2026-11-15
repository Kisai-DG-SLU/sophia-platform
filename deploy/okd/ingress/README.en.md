# Trusted certificate and names — VPN-only access

Every Route presents a **Let's Encrypt certificate** obtained through **DNS-01** validation: no port is opened to the Internet, and the certificate is trusted by every browser, phones included. Service names point to the server's **VPN address**: the platform is reachable through the VPN only, at home as elsewhere.

| Choice | Value | Reason |
|---|---|---|
| Issuance | cert-manager, ACME Let's Encrypt, DNS-01 | nothing exposed; wildcard possible |
| Version | cert-manager **1.21.3**, official static manifest, checksum verified before any apply | only the last two minor versions are maintained, and only they cover the cluster's version |
| Scope | one certificate: `*.apps` + names outside the wildcard, as the router's default certificate | a single item to renew, no Route to change |
| Renewal | automatic, 30 days before expiry (90 days) | no manual operation |
| Names | **public** A records pointing to the server's **VPN address** | no local DNS server to maintain; without the VPN, the address is unreachable |
| Access | WireGuard VPN **always on** on every device, including on the local network; the local network is **never** routed into the VPN | one access path, the home network out of the VPN's reach |

## Files

| File | Content |
|---|---|
| `00-clusterissuer.yaml` | `letsencrypt-staging` (testing) and `letsencrypt-prod` issuers; `solvers` block to adapt to the DNS provider (example: RFC 2136) |
| `01-certificate.yaml` | `sophia-ingress` certificate in `openshift-ingress` |

## Procedure (administrator)

1. **DNS access**: a token or key **restricted to the zone alone**, allowed to edit its records; store it in a secret in the `cert-manager` namespace, without it going through the shell history (`read -rs`).
2. **Issuers**: `oc apply -f 00-clusterissuer.yaml`; `oc get clusterissuer` → `READY True`.
3. **Testing**: `oc apply -f 01-certificate.yaml`; `oc get certificate sophia-ingress -n openshift-ingress -w` → `READY True` within 1 to 3 minutes. If it waits: `oc describe certificaterequest,order,challenge -n openshift-ingress`.
4. **Production**: `issuerRef` → `letsencrypt-prod`, re-apply, wait for `READY True`.
5. **Router default certificate** (router pods restart, a few seconds of downtime):
   ```bash
   oc get ingresscontroller default -n openshift-ingress-operator -o yaml > backup-ingresscontroller-default.yaml
   oc patch ingresscontroller default -n openshift-ingress-operator --type=merge \
     -p '{"spec":{"defaultCertificate":{"name":"sophia-ingress-tls"}}}'
   oc rollout status deploy/router-default -n openshift-ingress
   ```
   Rollback: `oc patch ingresscontroller default -n openshift-ingress-operator --type=json -p '[{"op":"remove","path":"/spec/defaultCertificate"}]'`.
6. **Names**: at the DNS provider, A records (not proxied, short TTL) pointing to the server's VPN address, for `*.apps`, the names outside the wildcard and the cluster API.
7. **Devices**: one WireGuard peer per device, `AllowedIPs` limited to the VPN network, "always on" connection on phones and tablets. Server, adding devices and node-side filtering: `../host/wireguard/`.

## Upgrading cert-manager

Done on 15/11 in the reference installation, from 1.14.4 to 1.21.3, without interrupting ingress.

1. **One minor version at a time**, at the latest patch of each (official path): 1.15.5, 1.16.5, 1.17.4, 1.18.6, 1.19.6 (never 1.19.0, which reissues certificates for no reason), 1.20.5, 1.21.3.
2. **Before**: back up the objects outside any repository (issuers' Secrets included); router certificate `READY True`; no challenge in progress; CRDs stored in `v1` (`status.storedVersions`).
3. **At each version**: manifest downloaded, compared with its SHA-256 checksum measured beforehand (the static manifest is not signed), `--dry-run=server`, apply, three deployments ready, server-side dry run of a Certificate (webhook and cainjector answer), router certificate still ready.
4. **After**: test issuance on the staging issuer, then cleanup: `apply` prunes nothing, and the RBAC objects added in 1.16, renamed in 1.19 then removed in 1.21, stay orphaned until deleted.

The router's Secret is not owned by the Certificate: even with cert-manager stopped, the router keeps serving the current certificate until it expires.

## Verification

```bash
echo | openssl s_client -connect <VPN address>:443 -servername chat.example.org 2>/dev/null \
  | openssl x509 -noout -issuer -subject -ext subjectAltName -enddate
curl -s -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' https://chat.example.org/   # no -k: 0 expected
```
