# Relaying the person's identity to an MCP tool

This card explains how the chat interface lets an MCP tool **act under the identity of the person** who is talking, without ever handing their token to the model or to a tool that does not need it. It applies the [Deterministic Automation](09-automation-deterministe.en.md) pattern: the model spots the intent, rules decide, the server executes.

The example in service is searching the person's files (La Suite Drive) from the chat; the same path will serve any tool that must see "what this person is allowed to see".

A second path, without token exchange, serves the **summary routes** of the applications shown in the cockpit ("What's new?"): see [To the summary routes](#to-the-summary-routes).

---

## Problem

A tool that reads a family's or a team's documents must show each person only their own. Two shortcuts are ruled out:

- a **service account that reads everything**, then a filter in the tool: one filter mistake and everyone sees everything;
- the **person's token relayed as is** all the way to the service: any chat token, if it leaked, would then open the service.

The right must remain the service's own, and each hop must receive only the token issued for it.

---

## The chain

```
browser ──► oauth2-proxy ──► nginx ──► chat API ──► MCP ──► identity provider (exchange)
            (session          (relay on    (closed list    │
             token)            one route)   of servers)    └──► service (introspection)
```

| Hop | What it does | What it refuses |
|---|---|---|
| **oauth2-proxy** | `--pass-access-token=true`: adds the session's access token as the `X-Forwarded-Access-Token` header; `--cookie-refresh` **shorter than the access token's lifetime** (for instance 4 minutes for a 5-minute token) | a value of that header sent by the browser is removed before injection |
| **nginx** | relays the token to the chat API **on the chat route only**, under an internal header (`X-Sophia-Jeton`) | clears it on every other route and **never** forwards it to the model gateway; a forged value of the internal header is overwritten; the log format contains no header |
| **Chat API** | sends `Authorization: Bearer …` only to the MCP servers on the closed list `SOPHIA_MCP_JETON_URLS`, for tools that declare `sophia/jeton` | the token is never written to the database or a log, never shown to the model, never put in a tool's arguments; a tool from another server asking for the token does not get it; token tools are never offered to the model: the server calls them itself, after the rules have decided |
| **MCP** | verifies the token (below), then **exchanges** it for a token issued to itself | no identity header is trusted; the identity is the `sub` of the verified token |
| **Service** | **introspects** the exchanged token with the identity provider and applies its own permissions | a token that does not come from the MCP |

### Verification by the MCP

Locally, before any call:

- signature, using the realm's public keys (JWKS);
- `iss` = the realm's public issuer (`${OIDC_ISSUER}`), even though the MCP reaches the provider at its internal address;
- `exp`;
- `aud` contains the MCP's client (`${MCP_CLIENT_ID}`), added to the chat token by an audience mapper;
- `azp` = the chat's client (`${CHAT_CLIENT_ID}`);
- `groups` contains one of the allowed groups (`${ALLOWED_GROUPS}`): the chat's rule is enforced a second time here.

### Token exchange

The MCP exchanges the token (Keycloak **Standard Token Exchange V2**, RFC 8693) on behalf of its **confidential client** `${MCP_CLIENT_ID}`, for a token with the **service's audience** (`${SERVICE_CLIENT_ID}`), with `scope=openid`. What to know about Keycloak 26:

- the feature is on by default; it is switched on **per client**, on the requesting client, which must be confidential;
- the presented token must carry the requester in its `aud`: hence the audience mapper on the chat's client;
- the `audience` parameter **filters, it adds nothing**: the requester must itself have a mapper that adds the service's audience;
- no refresh token through exchange: the MCP does not need one;
- the MCP client's secret lives in a Secret in its namespace, created by the administrator, never displayed.

Why exchange: the service then accepts only tokens **issued to the MCP**. The chat's token, if it leaked, would not open its API. The exchanged token is neither logged nor kept beyond the call (one MCP session per call).

### Introspection by the service

- The service introspects with its own client. Since Keycloak 26, introspection **requires that client to be in the token's `aud`**, otherwise it answers `active: false`; the options that disable this check are deprecated and are not used.
- It reads the origin from `client_id` (= the MCP's client), the only allowed value.
- Its API for relayed tokens is served on a **reserved internal port** (`${SERVICE_API_PORT}`), with no Route, **GET only**; the public port answers 404 on that path. A NetworkPolicy opens it to the MCP pod alone.
- The actions the API allows are an allow-list reduced to reading.
- The permissions are **the service's own**: the person sees only their items and those shared with them. No account is created this way.

---

## To the summary routes

The cockpit's "What's new?" panel is computed by the **chat server**, which queries each application's summary route (`GET /api/resume`, deterministic, no model) with the person's access token as `Authorization: Bearer`. Here there is **no exchange**: the token is checked by the receiver, which applies its own rights.

```
chat API ──Bearer──► application's oauth2-proxy ──► application (summary route)
         └─Bearer──► summary module mounted in the messaging server
```

| Receiver | Check | What it refuses |
|---|---|---|
| **an application's oauth2-proxy** | `--skip-jwt-bearer-tokens=true`: the bearer token goes through the **main provider's verifier** (keys through the provider's internal Service, public issuer, the application's `client-id` required in `aud`), then groups and `--allowed-group` as for a session | `--bearer-token-login-fallback=false`: a refused token gets **403**, never a redirect to sign-in |
| **a module that checks by itself** (application without oauth2-proxy) | signature with the realm keys, `iss`, `aud` = a **custom audience**, `azp` = the chat's client, `exp` and `iat`, allowed groups (guests excluded) | 401 for a refused token, 503 for any other error; it only returns counts, never a text or a sender |

- Each receiver's audience is added to the chat token by an **audience mapper** on the chat's client; for a module without a Keycloak client, a custom audience is enough, no client is created ([`deploy/okd/identity/`](../../deploy/okd/identity/README.en.md#audiences-of-the-token-relayed-by-the-interface)).
- Groups are in the access token, **without path**: `--allowed-group` compares the exact value.
- **Never `--extra-jwt-issuers`**: that setting triggers an OIDC discovery on the provider's public address, which pods cannot reach. The main verifier already checks issuer, keys and audience.
- The chat calls the **internal Service** of the application's oauth2-proxy; a separate NetworkPolicy opens that egress only ([`deploy/okd/apps/chat-interface/`](../../deploy/okd/apps/chat-interface/README.en.md#cockpit)), and the application opens the matching ingress.
- The files MCP tool also serves its summary route, with the same verification as its tools.
- An application with no data of its own (a static site) has no route: the chat computes its summary itself, without a token.
- On the chat's side: parallel calls, 2 s each, to the role's modules only; a source that is refused (401, 403), absent (503), failing or too large is left out; 60 s cache without the token; the token is never logged, and nginx only forwards it to the API on the chat route and the "What's new?" route.
- A module that finds the person's account by their identifier assumes that an identifier is **never reassigned** to another person.
- A module's route that can also be reached through its application's public address stays guarded by the token.

Why no exchange here: the route only returns a read-only summary, with the application's own rights, and the audience limits the token to that receiver.

---

## Outputs without URLs, links built by the chat

- The tool returns a **closed schema**: identifier (UUID), name, kind, type, readable path, date, "editable". **No URL**: a returned address would be ignored.
- The chat builds every link: base from the closed list of applications, path template from the closed list, identifier that must be a UUID (otherwise the line is dropped). A final guard checks, before sending, that every link in the answer starts with an allowed base.
- The answer is **written by the server**, without calling the model again. Names are data, possibly written by someone else (a share): control characters removed, length bounded, Markdown characters escaped.
- In the history, the list is replaced by a summary before any model call: file names go to no model.
- Closed errors, turned into sentences by the chat: token missing or expired, account never opened in the service, service unreachable.

---

## Network

MCP egress: DNS, the identity provider (public keys and exchange) and the service's internal port, **nothing else**. MCP ingress: the chat interface only. Signature verification and exchange require egress to the identity provider; without exchange it would go away, at the cost described above.

---

## Traps encountered

| Trap | Effect | Remedy |
|---|---|---|
| A one-hour `--cookie-refresh` for a 5-minute access token | the relayed token is expired most of the time | refresh the session below the token's lifetime, without touching the realm |
| Session in the cookie, split into chunks beyond 4 KB (the relayed token and its audiences make it grow) | oauth2-proxy reads an old whole cookie before its chunks, and never deletes it: the `Cookie` header exceeds the web server's limit (400) on a device that keeps an old session | server-side sessions, in a [dedicated Valkey](../../deploy/okd/identity/sessions/README.en.md) (one ACL user per application); header limit raised to 32 KB during the transition, on nginx **and** on uvicorn, whose h11 server caps at 16 KB by default |
| nginx forwards every received header by default | without an explicit rule, the token would reach the model gateway and every API route | each `proxy_pass` block sets or clears the header; tested with the nginx binary and fake services, route by route |
| Without `--pass-access-token`, oauth2-proxy lets the header through | a value forged by the browser would reach nginx | with the option on, oauth2-proxy removes the received value before injecting its own; nginx overwrites the internal header anyway |
| A client description longer than 255 characters | Keycloak answers 500 on import (255-character column); nothing is created | the import script rejects any over-long text field, before connecting |
| EgressFirewall of a build namespace with a final deny | the build hangs at clone: the cluster API, reached through the `kubernetes` Service, lands on the node on a port outside the allowed ranges | a rule to the control-plane nodes on the API port (`${CLUSTER_API_PORT}`), before the deny, in every namespace that runs builds |
| A base image that installs packages | blocked by the build's EgressFirewall | an image that already contains the interpreter, imported through the internal registry; dependencies pinned by hash |
| An internal relay server without `X-Forwarded-Proto` | the service (Django in production) answers 301 to https: "service unreachable" | copy the public server's `proxy_set_header` lines into the internal server; test the headers the backend expects, not only the routing |
| The MCP's HTTP client logging at INFO | the service URL, hence the person's search, ends up in the log | that logger goes to WARNING, with a test that fails without the fix |
| A title without an extension | a document created in the service from a template keeps a title without an extension: the edit button disappeared | edit button if "editable" **and** an office type by extension **or** MIME type, from a closed list |

---

## Status

| Item | Status |
|---|---|
| Token relay (oauth2-proxy, nginx, closed list) | in service |
| Server-side oauth2-proxy sessions (chat and other applications behind oauth2-proxy) | in service |
| "Files" MCP: verification, exchange, search by name, links built by the chat | in service |
| Reading a document's content, reserved to local models ([Models by role](13-modeles-par-role.en.md)) | deployed, acceptance test pending |
| Cockpit summary routes: audiences, network egress, applications that accept the bearer token (403 for an invalid token), messaging summary module (401 without a token) | in service, checked without a valid token |
| The chat calling the summary routes with the person's token (cooking, visualisation, messaging, files) | in service, verified by the administrator |
| Human approvals through the chat, with the same relayed token | planned (see [Observability](10-observabilite.en.md)) |

---

## What this card does not do

- No tool receives the token because it asks for it: only the closed list decides.
- The model never sees a token, an address or an identifier, and writes none.
- The MCP decides no permission: the service keeps its own.

---

## Place in the architecture

- identity and SSO: `sophia-identity` ([`deploy/okd/identity/`](../../deploy/okd/identity/));
- chat interface: `sophia-interface` ([`deploy/okd/apps/chat-interface/`](../../deploy/okd/apps/chat-interface/));
- MCP tools without Internet: `sophia-skills`;
- overall protections: [Security model](../security.en.md).
