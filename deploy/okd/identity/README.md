# Identité — Keycloak (SSO)

Fournisseur d'identité unique de la plateforme (OIDC) : une personne, un compte, une connexion pour toutes les applications. Les groupes du realm portent les rôles décrits dans le [périmètre fonctionnel](../../../docs/functional-scope.md#utilisateurs-et-rôles).

| Choix | Valeur | Raison |
|---|---|---|
| Installation | operator Keycloak officiel (OLM, catalogue `community-operators`), approbation manuelle | realm et clients décrits en ressources Kubernetes, reproductibles |
| Base | rôle et base dédiés dans le PostgreSQL existant | pas de nouveau volume quand le stockage n'a pas de provisionneur dynamique |
| Nom public | sous le domaine joker des Routes (`auth.apps.example.org`) | couvert par le DNS et le certificat du routeur, résolvable depuis le cluster |
| TLS | terminé par la Route (edge, Redirect) | Keycloak en HTTP dans le cluster, en-têtes `X-Forwarded-*` |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace-operator.yaml` | namespace, OperatorGroup, Subscription (approbation manuelle) |
| `02-network.yaml` | PostgreSQL accepte le namespace d'identité ; Keycloak n'accepte que le routeur, le namespace des applications et lui-même |
| `03-keycloak.yaml` | instance Keycloak et Route |
| `04-realm-sophia.yaml` | realm : groupes, politique de mots de passe, clients OIDC — interface de discussion (PKCE, secret par *placeholder*), administration de RabbitMQ (client public PKCE, audience `rabbitmq`), interface de Temporal (oauth2-proxy, secret par *placeholder*) |

## Procédure

1. **Operator** : `oc apply -f 00-namespace-operator.yaml`, approuver l'InstallPlan, attendre le CSV `Succeeded`.
2. **Base** : créer le secret `keycloak-db` (utilisateur, mot de passe aléatoire), puis le rôle et la base dans PostgreSQL. **Le mot de passe passe par l'entrée standard de `psql`, jamais par la ligne de commande** : les arguments d'`oc exec` sont tracés par l'API.
   ```bash
   KC_DB_PASS=$(openssl rand -base64 30 | tr -d '/+=' | cut -c1-32)
   oc create secret generic keycloak-db -n sophia-identity --from-literal=username=keycloak --from-literal=password="$KC_DB_PASS"
   oc exec -i -n sophia-core deploy/postgres -- psql -v ON_ERROR_STOP=1 <<SQL
   CREATE ROLE keycloak LOGIN PASSWORD '$KC_DB_PASS';
   CREATE DATABASE keycloak OWNER keycloak;
   REVOKE ALL ON DATABASE keycloak FROM PUBLIC;
   SQL
   unset KC_DB_PASS
   ```
3. **Réseau** : `oc apply -f 02-network.yaml`.
4. **Keycloak** : `oc apply -f 03-keycloak.yaml`, attendre `Ready`. Se connecter avec l'administrateur temporaire créé par l'operator, **créer un administrateur nominatif dans le realm `master`, supprimer le temporaire**.
5. **Realm** : créer le secret du client (`openssl rand -hex 32`), puis `oc apply -f 04-realm-sophia.yaml`, attendre `Done`. Créer les utilisateurs dans la console (e-mail renseigné et vérifié) et les placer dans un groupe.

## Pièges rencontrés

- **Une liste fournie dans l'import remplace les valeurs par défaut du realm.** Déclarer `clientScopes` pour ajouter un scope supprime `profile`, `email`, `basic`… et la connexion échoue en `invalid_scope`. Ajouter, ne pas redéfinir : le mappeur des groupes est porté par le client.
- **L'import ne s'applique qu'à la création du realm.** Pour rejouer un import corrigé : supprimer le realm, supprimer la ressource `KeycloakRealmImport`, réappliquer. Sur un realm existant, un client ajouté au fichier s'importe à part, depuis la console (*Clients → Import client*) ; le fichier reste la référence d'une installation neuve.

Applications clientes : [interface de discussion](../apps/chat-interface/README.md), [RabbitMQ](../core/rabbitmq/README.md), [Temporal](../core/temporal/README.md). Keycloak accepte depuis `sophia-core` les pods de Temporal (clés de signature, jetons des comptes de service) : `02-network.yaml`.
