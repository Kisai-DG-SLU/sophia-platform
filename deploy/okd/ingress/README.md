# Certificat de confiance et noms — accès par VPN seulement

Toutes les Routes présentent un **certificat Let's Encrypt** obtenu par validation **DNS-01** : aucun port n'est ouvert sur Internet, et le certificat est reconnu par tous les navigateurs, téléphones compris. Les noms des services pointent vers l'**adresse VPN** du serveur : la plateforme ne se joint que par le VPN, à la maison comme dehors.

| Choix | Valeur | Raison |
|---|---|---|
| Émission | cert-manager, ACME Let's Encrypt, DNS-01 | rien d'exposé ; joker possible |
| Version | cert-manager **1.21.3**, manifeste statique officiel, empreinte vérifiée avant toute application | seules les deux dernières versions mineures sont maintenues, et elles seules couvrent la version du cluster |
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
7. **Appareils** : un pair WireGuard par appareil, `AllowedIPs` limité au réseau du VPN, connexion « toujours active » sur téléphone et tablette. Serveur, ajout d'appareils et filtrage sur le nœud : `../host/wireguard/`.

## Montée de version de cert-manager

Faite le 15/11 dans l'installation de référence, de 1.14.4 à 1.21.3, sans coupure de l'entrée.

1. **Une version mineure à la fois**, au dernier correctif de chacune (chemin officiel) : 1.15.5, 1.16.5, 1.17.4, 1.18.6, 1.19.6 (jamais 1.19.0, qui réémet des certificats sans raison), 1.20.5, 1.21.3.
2. **Avant** : sauvegarde des objets hors de tout dépôt (Secrets des émetteurs compris) ; certificat du routeur `READY True` ; aucun défi en cours ; CRD stockées en `v1` (`status.storedVersions`).
3. **À chaque version** : manifeste téléchargé, comparé à son empreinte SHA-256 relevée d'avance (le manifeste statique n'est pas signé), `--dry-run=server`, application, trois déploiements prêts, essai côté serveur d'un Certificate (le webhook et l'injecteur répondent), certificat du routeur toujours prêt.
4. **Après** : émission d'essai sur l'émetteur de recette, puis ménage : `apply` n'élague rien, et les objets RBAC ajoutés en 1.16, renommés en 1.19 puis retirés en 1.21, restent orphelins jusqu'à leur suppression.

Le Secret du routeur n'appartient pas au Certificate : même cert-manager arrêté, le routeur continue de servir le certificat en place jusqu'à son échéance.

## Vérification

```bash
echo | openssl s_client -connect <adresse VPN>:443 -servername chat.example.org 2>/dev/null \
  | openssl x509 -noout -issuer -subject -ext subjectAltName -enddate
curl -s -o /dev/null -w '%{http_code} %{ssl_verify_result}\n' https://chat.example.org/   # sans -k : 0 attendu
```
