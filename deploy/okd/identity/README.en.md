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
| `02-network.yaml` | PostgreSQL accepts the identity namespace; on its HTTP port Keycloak only accepts the router and a named list of clients that call it through its internal Service, and on its management port only its own namespace |
| `03-keycloak.yaml` | Keycloak instance (with the ingress list of the network policy the operator creates) and Route |
| `04-realm-sophia.yaml` | realm: groups, password policy, OIDC clients — chat interface (PKCE, secret through a *placeholder*), RabbitMQ management (public PKCE client, `rabbitmq` audience), Temporal UI (oauth2-proxy, secret through a *placeholder*); audience mappers of the token relayed by the interface |
| `ajouter-mappeur-audience.py` | adds to the interface's client an audience mapper towards a service that receives the relayed token (below); read-only with `--dry-run`, replayable |

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
- **The operator creates its own NetworkPolicy, open to the whole cluster.** Without a list in the CR (`spec.networkPolicy`), it opens the HTTP port (8080) and the management port (9000) to every pod; since policies add up, the one in `02-network.yaml` then filtered nothing on those ports. The CR therefore carries the same list of peers as `sophia-identity-ingress`: **one more client through the internal Service = one line in both lists**, otherwise its sign-in fails. Clients that go through the public name go through the router, already admitted. Apply at a quiet time, with a sign-in check on each application; the Keycloak pod does not restart. In service.
- **The import only applies when the realm is created.** To replay a fixed import: delete the realm, delete the `KeycloakRealmImport` resource, apply again. On an existing realm, a client added to the file is imported on its own from the console (*Clients → Import client*); the file remains the reference for a fresh install.

## Audiences of the token relayed by the interface

When the chat interface relays the person's access token (see [Identity relay](../../../docs/concepts/12-relais-identite.en.md)), each receiving service only accepts tokens that carry **its audience**. It is added to the token of the interface's client by an **audience mapper**, one per service:

| Receiving service | Check | Mapper |
|---|---|---|
| MCP server that exchanges the token (files) | signature, then exchange on behalf of its client | client audience (`included.client.audience`) |
| an application's oauth2-proxy, for its cockpit summary route | `--skip-jwt-bearer-tokens`: the provider's main verifier, the application's `client-id` required in `aud` | client audience, equal to the application's `client-id` |
| a module that checks the signature itself, without a client of its own (messaging summary) | signature with the realm keys, issuer, audience, originating client, groups | **custom audience** (`included.custom.audience`, `--personnalisee` option): no Keycloak client is created, since it would only serve introspection or exchange |

```bash
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <application-client> --dry-run
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <application-client>
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <free-audience> --personnalisee --dry-run
```

- The script first reads the client's **group mapper**: oauth2-proxy's `--allowed-group` compares the exact value, hence groups **without path** (`full.path false`) in the **access token**. A non-compliant mapper stops the script.
- It refuses mismatched cases: `--personnalisee` for a name that is a client, or the reverse.
- A new audience only appears when the token is renewed: a 403 right after, with an older token, is expected.
- **Never `--extra-jwt-issuers`** on the application side: that setting triggers an OIDC discovery on the provider's **public** address, which pods cannot reach. The main verifier (keys through the internal Service, public issuer) is enough.
- The realm's headers do not change: the sign-in page is still refused in a frame (the cockpit offers "Sign in again").
- These mappers are in `04-realm-sophia.yaml` for a fresh install; the script adds them to an existing realm, since the import only applies at creation.

Status: three audiences (two applications, messaging) in service, checked by replaying the script ("exists, unchanged") and by an invalid token refused with 403 by both applications.

## Reserving an application to some groups: persistent chat and video calls

The `matrix` (Matrix authentication service) and `jitsi` (video adapter) clients of the [Communication module](../../../docs/modules/communication/documentation.en.md), installed and in acceptance testing, are **confidential**, using the standard flow with **PKCE S256**, with the `groups` mapper. Neither MAS nor Jitsi can filter by group: refusal happens in Keycloak, before the application sees the person.

1. **Client role** `acces` on each client, given to the admitted groups (the household, without guests).
2. **Client-specific access flow** (`acces-matrix`, `acces-jitsi`): a **copy of the realm's actual browser flow**, with all its steps (including Keycloak's conditional second factor), to which a conditional sub-step "Condition - user role" on that role is added, **negated**, followed by "Deny access". The flow is bound to the client (*Authentication flow overrides*); the realm's browser flow stays unchanged.
3. **Test** with an admitted account **and** a guest account: the second must be refused by Keycloak.

Pitfall: the condition's negation is set through its `negate` configuration key; a wrongly negated condition refuses everyone, or no one. Only the test with both accounts shows it.

Client applications: [chat interface](../apps/chat-interface/README.en.md), [RabbitMQ](../core/rabbitmq/README.en.md), [Temporal](../core/temporal/README.en.md), [office suite, persistent chat and video calls](../office/README.en.md). Keycloak accepts Temporal's pods from `sophia-core` (signing keys, service account tokens): `02-network.yaml`.
