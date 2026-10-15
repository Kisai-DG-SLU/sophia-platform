# Identity — Keycloak (SSO)

Single identity provider for the platform (OIDC): one person, one account, one sign-in for every application. Realm groups carry the roles described in the [functional scope](../../../docs/functional-scope.en.md#users-and-roles).

| Choice | Value | Reason |
|---|---|---|
| Installation | official Keycloak operator (OLM, `community-operators` catalog), manual approval | realm and clients described as Kubernetes resources, reproducible |
| Database | dedicated role and database in the existing PostgreSQL | no new volume when storage has no dynamic provisioner |
| Public name | under the Routes wildcard domain (`auth.apps.example.org`) | covered by the router's DNS and certificate, resolvable from inside the cluster |
| TLS | terminated by the Route (edge, Redirect) | Keycloak speaks HTTP inside the cluster, `X-Forwarded-*` headers |

## Files

| File | Content |
|---|---|
| `00-namespace-operator.yaml` | namespace, OperatorGroup, Subscription (manual approval) |
| `02-network.yaml` | PostgreSQL accepts the identity namespace; Keycloak only accepts the router, the applications namespace and itself |
| `03-keycloak.yaml` | Keycloak instance and Route |
| `04-realm-sophia.yaml` | realm: groups, password policy, first OIDC client (PKCE, secret through a *placeholder*) |

## Procedure

1. **Operator**: `oc apply -f 00-namespace-operator.yaml`, approve the InstallPlan, wait for the CSV to reach `Succeeded`.
2. **Database**: create the `keycloak-db` secret (user, random password), then the role and database in PostgreSQL. **The password goes through `psql`'s standard input, never the command line**: `oc exec` arguments are recorded by the API.
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
3. **Network**: `oc apply -f 02-network.yaml`.
4. **Keycloak**: `oc apply -f 03-keycloak.yaml`, wait for `Ready`. Sign in with the temporary administrator created by the operator, **create a named administrator in the `master` realm, delete the temporary one**.
5. **Realm**: create the client secret (`openssl rand -hex 32`), then `oc apply -f 04-realm-sophia.yaml`, wait for `Done`. Create users in the console (email set and verified) and put each one in a group.

## Pitfalls we hit

- **A list provided in the import replaces the realm defaults.** Declaring `clientScopes` to add one scope removes `profile`, `email`, `basic`… and sign-in fails with `invalid_scope`. Add, do not redefine: the group mapper is carried by the client.
- **The import only applies when the realm is created.** To replay a fixed import: delete the realm, delete the `KeycloakRealmImport` resource, apply again.

Client application example: [chat interface](../apps/chat-interface/README.en.md).
