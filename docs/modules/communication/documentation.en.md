# Communication Module — documentation

Status: **in service, in acceptance testing**. Both services run in the reference installation, checked read-only; a first sign-in to the chat created a room, and a first pass through the video service was seen in the adapter's log. Messages and Video can be displayed in the interface's cockpit, and the unread-summary module is loaded in Synapse. Acceptance testing with the household's devices is still to do (see [Acceptance testing to do](#acceptance-testing-to-do)).

## What the module does

- **Persistent chat**: rooms between household members, in the browser (Element Web) and on phones and tablets (Matrix clients). Messages and files stay on the home server.
- **Video calls**: a video room opens through a link, for instance pinned in a chat room; only the household's admitted accounts can join it.
- **Notifications** on Android, through a local relay, without any third-party notification service.
- **In the cockpit**: Messages (Element) and Video are displayed in the centre of the [interface's cockpit](../../../deploy/okd/apps/chat-interface/README.en.md), and the "What's new?" panel counts each person's unread messages (in service, in acceptance testing); an "Ask Sophia" panel is offered there, without reading the messages.

## Architecture

```
browser, Matrix client (VPN) ──► ingress router ──► Element Web
                                                ├──► Synapse ──► PostgreSQL 18 (synapse database)
                                                │        └──► ntfy (notifications)
                                                └──► MAS ──► identity provider (OIDC, PKCE); PostgreSQL 18 (mas database)

browser only (VPN) ──► ingress router ──► Jitsi web ──► Prosody ◄── Jicofo
                    └──► adapter ──► identity provider (OIDC) → room token
media (UDP, VPN only) ──► ${VPN_IP}:${JVB_UDP_PORT} ──► JVB

interface server ──► Synapse, HTTP port (summary module) ──► realm public keys (through the router)
```

| Element | Choice | Reason |
|---|---|---|
| Namespaces | two dedicated namespaces, `sophia-messagerie` (chat) and `sophia-visio` (video), each with quota, LimitRange, EgressFirewall, default ingress and egress deny, DNS; **no role binding to any agent** | the office suite had no room left in its quota; isolate chat and video from everything else |
| Priority | the office suite's class for every pod, **except the video media bridge**, in the voice class ([priorities](../../../deploy/okd/cluster/README.en.md)) | the media of an ongoing call must not wait behind background work |
| Images | pinned by digest; Synapse 1.163.2, Jitsi `stable-11248-2` | an update is a decision |

### Persistent chat: Matrix

| Element | Choice | Reason |
|---|---|---|
| Server | Synapse, `synapse` database on the shared PostgreSQL 18 (`C` collation, required by Synapse) | the platform's common database; its own database and role, cross access refused |
| Sign-in | **MAS** (Matrix Authentication Service) delegates authentication to the platform's identity provider (OIDC, PKCE); its own `mas` database | single sign-on, no Matrix password; MAS is Matrix's current authentication path |
| Access | reserved to the household's groups: a client role in the identity provider, and a sign-in flow that **refuses the guests group** | MAS does not filter by group: refusal happens earlier, at the identity provider |
| Federation | **off** | the server talks to no other Matrix server; nothing goes out |
| End-to-end encryption | **off by default** for new rooms (setting served to clients by the server) | the household's choice. **Accepted consequence**: the server administrator can read the rooms |
| Media | 50 MB at most per file; dedicated 10 GiB logical volume, `Retain` PV; **no backup** | losing media is accepted; messages are in the database |
| Notifications | **ntfy** in the same namespace, through UnifiedPush: the notification carries neither the text nor the sender; Synapse only goes out to MAS, ntfy and the identity provider's public name (public keys, for the summary module) | no third-party push gateway |
| Web client | Element Web, configuration without any external address; can only be displayed by the platform's chat (`frame-ancestors`) | served by the platform; without this header, Element could be displayed by any page |
| Unread summary | a **Python module mounted in Synapse** exposes a summary route for the interface's "What's new?" panel (see below) | exact count through Synapse's own function, no new secret |

#### Unread summary for the interface

Synapse only accepts MAS tokens: the interface server cannot ask it for a person's unread messages with the token it relays. Three ways were weighed: administrative access to MAS (exact count, but a secret that can do anything in MAS), reading Synapse's database directly (redoing its computation, fragile across updates), or a module inside Synapse. Choice: **the module**.

- **The module verifies the relayed token itself**: signature by the realm's public keys, issuer, dates, a **custom audience** specific to this route (set by a mapper on the interface's client, with no identity-provider client, since nothing is introspected or exchanged), originating client (the interface) and the household's groups: guests are excluded.
- **What it returns**: a count per unread room, mentions first; **never a text or a sender**. `no-store`.
- **Errors**: 401 for a refused token, 503 for any other error; Synapse starts even if the module is broken. **Removal in one configuration line.**
- **Synapse updates**: the module calls an internal Synapse function; a test fails if its signature changes, to be rerun before each update.
- **Condition**: the Matrix account is found from the person's identifier at the identity provider: **an identifier must never move from one person to another**.
- **Network**: Synapse ingress from the interface pod, on its HTTP port. The route can also be reached through Synapse's public address, inside the VPN: the token guards it.

Status: module loaded, route answering 401 without a token; interface egress to Synapse open; called by the interface for "What's new?": in service, in acceptance testing.

### Video calls: Jitsi Meet

Jitsi Meet replaced La Suite numérique's video service, planned first: its interface does not start on the household's older tablets, whereas Jitsi's mobile app accepted them (iOS 15.1 at least).

**Video calls now go through the browser only**, hence through the interface's cockpit (household decision): `DISABLE_DEEP_LINKING` removes the "Join in the app" page, and the mobile app is no longer used. Consequence: video calls in the older tablet's browser (Safari 15) **are not proven yet**; they are part of the acceptance step.

| Element | Choice | Reason |
|---|---|---|
| Components | web, Prosody, Jicofo, JVB (the media bridge); neither database nor cache | as few parts as possible |
| Access | a home-made **adapter** (Python, standard library only) performs the OIDC sign-in with the identity provider and returns a **signed token valid 10 minutes, for a single room**; guests are refused by the identity provider, and by the adapter should one get through; states bound to the browser and single-use; the adapter's log holds neither the query string nor any secret | Jitsi only accepts a token: the adapter issues it to admitted accounts only |
| Media | **a single UDP port**, exposed through an `externalIP` on the node's VPN address (`${VPN_IP}:${JVB_UDP_PORT}`), forwarded by a rule of the VPN's nftables table; **no NodePort** | media can only be reached through the VPN, never from the local network; the bridge sees the devices' real VPN address |
| Network | peer-to-peer and STUN off; third-party requests off; private address candidates not advertised; bridge channel over the SCTP data channel | everything goes through the home bridge; nothing leaves for an outside service |
| OKD arbitrary UID | Jitsi images use s6-overlay, which refuses a `/run` owned by root; the variable `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` makes it accept it | **neither privilege nor `anyuid`** |
| Probes | Jicofo serves its health API on `127.0.0.1` only: `exec` probe | listening is not widened for the probe |
| Encryption | no end-to-end encryption | the home bridge sees the media, like any video bridge |
| Display | can only be displayed by the platform's chat (`frame-ancestors` in `CSP_HEADER`); camera and microphone allowed by the frame's `allow` attribute, for video only | the video service lives in the cockpit |

## Clients

| Device | Chat | Video |
|---|---|---|
| Computer | browser (Element Web) | browser |
| Android | Element X, notifications through ntfy; Element Web in the cockpit | browser, in the cockpit |
| Older tablet (iOS 15) | Element Classic | browser, in the cockpit: to be proven |

The **first sign-in** to the chat goes through two MAS pages: account linking, then application authorisation. In the cockpit, the MAS sign-in page is refused in a frame: if the Matrix session has expired, "Sign in again" opens Element in a tab, then one comes back to the cockpit.

**Element Web is not supported by Safari 15**: on the older tablet, the cockpit's Messages module therefore does not work as is. Options, to be decided after the test on the device: keep Element Classic on that tablet (recommended), a lighter Matrix web client, or a message view built by the interface itself.

## Privacy and limits

- **Home only**: chat and video are reached through the VPN only.
- **No end-to-end encryption**, neither in the chat (by default) nor in video calls: the system administrator can read the rooms. No room is therefore "private".
- **Chat media without backup.**
- **Video through the browser only**: Jitsi's mobile app, which sent usage metrics to a third-party service, is no longer used.
- **Unread summary**: the route only exposes counts, never a text or a sender, and only to the person themselves, through their token.
- **No agent** in the rooms for now; the chat does not receive the platform's alerts (they have their own channel, see [Observability](../../concepts/10-observabilite.en.md)).
- **Adapter**: a VPN device can exhaust its in-memory state pool and block sign-ins to the video service for 10 minutes.

## Acceptance testing to do

- a call with at least three devices, and the VPN UDP rule's counter increasing;
- guest refused (chat and video), protected account admitted;
- Element Classic on an older tablet, Element X with ntfy on Android;
- video calls in the browser on Android, without a "Join in the app" page; video and Element Web in the older tablet's browser;
- Element in the cockpit: session kept, a message sent;
- a message sent in a room, unencrypted;
- unread summary with a real relayed token, in "What's new?".

## Planned

- **Unified mail**: decided, **postponed** behind the other projects; nothing is open to the household.
- **Access through the cockpit only**, once the cockpit is validated on every device: an application page opened directly will be sent back to the cockpit; native chat clients are not concerned; direct access stays with the administrator, for troubleshooting.
- **Starting a call from Sophia's chat**, and Sophia in the rooms: later, with the agents.

## Lessons

- A local "arbitrary UID" test must also reproduce **volume ownership**: under OKD, an `emptyDir` is owned by root, which the local test did not show.
- A service exposed through an `externalIP` on the VPN address, rather than a NodePort, stays unreachable from the local network and sees the client's real address.
- A negated authentication-flow condition is set through a negation key specific to the condition: to be checked by testing, guest included.
- An `add_header` in an nginx `location` cancels those of the upper level: Element's `frame-ancestors` header is repeated in every location.
