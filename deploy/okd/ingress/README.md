# Certificat de confiance et noms — accès par VPN seulement

Toutes les Routes présentent un **certificat Let's Encrypt** obtenu par validation **DNS-01** : aucun port n'est ouvert sur Internet, et le certificat est reconnu par tous les navigateurs, téléphones compris. Les noms des services pointent vers l'**adresse VPN** du serveur : la plateforme ne se joint que par le VPN, à la maison comme dehors.

| Choix | Valeur | Raison |
|---|---|---|
| Émission | cert-manager, ACME Let's Encrypt, DNS-01 | rien d'exposé ; joker possible |
| Portée | un certificat : `*.apps` + noms hors joker, certificat par défaut du routeur | une seule pièce à renouveler, aucune Route à modifier |
| Renouvellement | automatique, 30 jours avant l'échéance (90 jours) | pas d'opération manuelle |
| Noms | enregistrements A **publics** vers l'**adresse VPN** du serveur | pas de serveur DNS local à maintenir ; sans VPN, l'adresse est injoignable |
| Accès | VPN WireGuard **toujours actif** sur chaque appareil, y compris sur le réseau local ; le réseau local n'est **jamais** routé dans le VPN | un seul chemin d'accès, le réseau domestique hors de portée du VPN |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-clusterissuer.yaml` | émetteurs `letsencrypt-staging` (recette) et `letsencrypt-prod` ; bloc `solvers` à adapter au fournisseur DNS (exemple : RFC 2136) |
| `01-certificate.yaml` | certificat `sophia-ingress` dans `openshift-ingress` |

## Procédure (l'administrateur)

1. **Accès au DNS** : un jeton ou une clé **limité à la seule zone**, avec le droit de modifier ses enregistrements ; le placer dans un secret du namespace `cert-manager`, sans qu'il passe par l'historique du shell (`read -rs`).
2. **Émetteurs** : `oc apply -f 00-clusterissuer.yaml` ; `oc get clusterissuer` → `READY True`.
3. **Recette** : `oc apply -f 01-certificate.yaml` ; `oc get certificate sophia-ingress -n openshift-ingress -w` → `READY True` en 1 à 3 minutes. En cas d'attente : `oc describe certificaterequest,order,challenge -n openshift-ingress`.
4. **Production** : `issuerRef` → `letsencrypt-prod`, réappliquer, attendre `READY True`.
5. **Certificat par défaut du routeur** (redémarrage des pods du routeur, coupure de quelques secondes) :
   ```bash
   oc get ingresscontroller default -n openshift-ingress-operator -o yaml > backup-ingresscontroller-default.yaml
   oc patch ingresscontroller default -n openshift-ingress-operator --type=merge \
     -p '{"spec":{"defaultCertificate":{"name":"sophia-ingress-tls"}}}'
   oc rollout status deploy/router-default -n openshift-ingress
   ```
   Retour arrière : `oc patch ingresscontroller default -n openshift-ingress-operator --type=json -p '[{"op":"remove","path":"/spec/defaultCertificate"}]'`.
6. **Noms** : chez le fournisseur DNS, des enregistrements A (non proxifiés, TTL court) vers l'adresse VPN du serveur, pour `*.apps`, les noms hors joker et l'API du cluster.
7. **Appareils** : un pair WireGuard par appareil, `AllowedIPs` limité au réseau du VPN, connexion « toujours active » sur téléphone et tablette.

## Vérification

```bash
echo | openssl s_client -connect <adresse VPN>:443 -servername chat.example.org 2>/dev/null \
  | openssl x509 -noout -issuer -subject -ext subjectAltName -enddate
curl -s -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' https://chat.example.org/   # sans -k : 0 attendu
```
