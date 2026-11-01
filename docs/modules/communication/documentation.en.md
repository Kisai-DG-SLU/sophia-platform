# Communication Module — documentation

Status: **in service, in acceptance testing**. The chat (Matrix) and video calls run in the reference installation, checked read-only, and are displayed in the interface's cockpit. The **first video call with picture** between a computer and the older tablet took place in the cockpit, through the VPN, after three fixes in a row (see [Video media](#video-media-three-causes-in-a-row)). **Messaging has changed software**: after a test on the real tablet, the household chose **Converse.js and Prosody (XMPP) instead of Matrix**. The final version is **in service**, in the cockpit, with "tell" (Sophia sends a message on the person's behalf); Matrix stays readable until the end of acceptance testing (see [Messaging: from Matrix to XMPP](#messaging-from-matrix-to-xmpp)). **Acceptance testing with every household device is under way** (see [Acceptance testing to do](#acceptance-testing-to-do)).

## What the module does

- **Persistent chat**: rooms and direct conversations between household members, in the browser and in the cockpit. Messages and files stay on the home server. Converse.js and Prosody (XMPP) since the final version; Matrix (Element) stays readable until the end of acceptance testing, then it is dismantled.
- **"Tell"**: one asks Sophia to write to a family member or to the Family room; after confirmation, the message goes out in the messaging service, on the person's behalf, marked "via Sophia".
- **Video calls**: a video room opens in the cockpit or through a link; only the household's admitted accounts can join it.
- **Notifications** on Android, through a local relay (ntfy), without any third-party notification service and without content: "New message", neither text nor sender.
- **In the cockpit**: Messages and Video are displayed in the centre of the [interface's cockpit](../../../deploy/okd/apps/chat-interface/README.en.md), and the "What's new?" panel counts each person's unread messages (in service, verified); an "Ask Sophia" panel is offered there, without reading the messages.

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

browser, cockpit (VPN) ──► ingress router ──► web: oauth2-proxy + nginx (Converse.js) ──► Prosody (WebSocket, files)
                                                                            └──► push gateway ──► ntfy
interface server ──► "tell" relay (one route, one port) ──► Prosody (HTTP module) ──► identity provider userinfo
```

| Element | Choice | Reason |
|---|---|---|
| Namespaces | two dedicated namespaces, `sophia-messagerie` (chat) and `sophia-visio` (video), each with quota, LimitRange, EgressFirewall, default ingress and egress deny, DNS; **no role binding to any agent** | the office suite had no room left in its quota; isolate chat and video from everything else |
| Priority | the office suite's class for every pod, **except the video media bridge**, in the voice class ([priorities](../../../deploy/okd/cluster/README.en.md)) | the media of an ongoing call must not wait behind background work |
| Images | pinned by digest; Synapse 1.163.2, Jitsi `stable-11248-2` | an update is a decision |

### Persistent chat: Matrix (in service, to be replaced)

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

Status: module loaded, route answering 401 without a token; interface egress to Synapse open; called by the interface for "What's new?": in service, verified. It will go away with Matrix; XMPP messaging will have its own summary.

### Messaging: from Matrix to XMPP

**Household decision, firm after the test on the real tablet**: Converse.js (web client) and Prosody (XMPP server) replace Matrix for the family's messaging.

**Why.** The criteria were checked in order: works on the older tablet (Safari 15), single identity-provider account, no network egress that cannot be cut, notifications, living project. Element Web does not start under Safari 15, and the lighter Matrix web clients fail too: blank page (lookbehind regular expressions), or a stopped project. Converse.js runs on the older tablet, once the logos loaded from its website are removed; it is maintained, and Prosody follows its security fixes. **Accepted risk**: the Prosody module that validates an OIDC token is a community module, at alpha stage.

**Test** (throwaway namespace, deleted as a block at the end):

| Element | Choice | Reason |
|---|---|---|
| Base | quota, default deny, EgressFirewall limited to the cluster; Prosody on an ephemeral volume | a test leaves nothing behind |
| Web pod | nginx and oauth2-proxy (on loopback); access reserved to a **dedicated test group** and a dedicated OIDC client | the test touches no account outside the group |
| Token | a `/credentials` route hands the client the session's access token, filtered | Converse.js signs in without an XMPP password |
| Prosody | 13.0.7, SASL OAUTHBEARER; the token is validated through the identity provider's userinfo; the XMPP account name comes from the userinfo (`preferred_username`), never from the client; no XMPP password, no server-to-server, no TCP client | no impersonation through the name; only the WebSocket is open |
| WebSocket and files | oauth2-proxy `auth_request` on `/xmpp-websocket` and `/file_share/`: 401 without a session | Prosody accepts **any** valid token of the realm (the userinfo checks neither the client, nor the audience, nor the group): without this check, a token from another application opened the test messaging |
| Shared files | `proxy_buffering off` on `/file_share/` | nginx buffered the files read into an ephemeral 64 Mi `/tmp`: two reads of a video got the pod evicted |
| Service names | **fully qualified** names in `.svc.cluster.local` | Prosody resolves through libunbound, which ignores search domains: a short name answered NXDOMAIN, and Prosody's userinfo call, with no adjustable timeout, hung |
| Cockpit tile | visible only to members of the test group (`SOPHIA_ESSAI_GROUPES`); the real check stays the page's oauth2-proxy | hiding is not a control |

**What works on the older tablet**: delivery delay, "typing…", photos both ways, keyboard, rotation, coming back after 5 minutes, staying connected beyond the token's lifetime (renewed), direct conversation, room, removing a member (`/revoke`).

**Defects found**, to be fixed in the final version (setting, small plugin or forced return to the cockpit):

- **no formatting toolbar**: formatting exists (XEP-0393: `*bold*`, `_italic_`, code between backticks) but is typed by hand;
- **member shown twice** in a room: present occupant and member-list entry, not merged;
- **room left in the list** of a removed member: the bookmark set on entering the room is not removed by `/revoke`;
- **invitation window not closed** in the same account's other session, which comes back as a new invitation;
- **double session**: the sign-in tab loads the messaging instead of sending back to the cockpit;
- **no directory**: a family member only shows up after being added by address;
- link to a video call from a conversation: the planned plugin does not work with version 14 of the client.

#### Final messaging (in service)

In the messaging namespace, next to Matrix, until the end of acceptance testing:

| Element | Choice | Reason |
|---|---|---|
| Prosody | 13.0.7, image pinned by digest; data on a **persistent local volume** (`Retain`); room archives kept | messaging is the household's written memory |
| Accounts | identity taken from the token's userinfo (OAUTHBEARER, `preferred_username`), never from a password; a Prosody module refuses at sign-in **any account outside the household groups**, on top of the page's oauth2-proxy | group control does not rest on a single layer |
| Openings | no server-to-server, no registration, no TCP client: the WebSocket only, behind oauth2-proxy; closed NetworkPolicies, Prosody reachable from the web pod only (and from the "tell" relay) | nothing gets in or out outside the intended path |
| Web | nginx (Converse.js 14, served by the image, digest checked; household plugins) and oauth2-proxy; strict content security policy, framable **by the cockpit only**; shared files served with `sandbox` and `nosniff` | no third-party resource; a received file cannot run in the page |
| Contacts | **nothing by default**: everyone adds their contacts by address, or goes through the Family room | household's choice |
| "Family" room | created by default for the whole home, guests excluded; **owners: the adults**; membership by default, no voluntary leaving; a child may create other rooms; absent members are visible to owners only | a guaranteed common place, run by the adults |
| Matrix history | **not migrated**; Element stays readable until the end of acceptance testing | migrating cost more than it brought |
| Notifications | Android: push gateway (XEP-0357) in the Prosody pod, towards ntfy; "New message", **neither text nor sender**, a link to the cockpit; one topic per person, derived from a secret key, shown to that person only. iOS tablet: badge in the cockpit, once Messages has been opened | no content leaves the messaging service; no third-party service |
| Video from a conversation | a button opens the **cockpit's Video tile** on the conversation's room; room name by a fixed rule (Family room → `famille`, other room → derived from its address, one-to-one conversation → derived from the pair of identifiers, hashed); the Video tile opens `famille` by default | one-to-one calls go through the one-to-one conversation |
| Resources | web with the `Recreate` strategy, limits within the namespace quota | a tight quota must not block an update |

**Going live**: prerequisites (volume, OIDC client and Secret, identity provider network ingress), check of the household groups, gateway Secret, images, ntfy setting, dry run, apply, HTTP checks (`/sante` 200; token, push and WebSocket 401 without a session; sign-out 302 with `Clear-Site-Data`), first test outside the cockpit, then the cockpit tile. Local bench through the production path: 25 steps.

**A member leaving**: remove them from the household groups (oauth2-proxy and Prosody refuse any new sign-in), then from the Family room (`/revoke`), then delete their Prosody account, which otherwise keeps its former status until its next sign-in.

#### "Tell": Sophia writes on the person's behalf

In the conversation with Sophia, "tell dad that…" or "tell everyone that…": Sophia drafts the message, the person confirms, and the message goes **into the messaging service**, on the person's behalf, to the one-to-one conversation or the Family room. It replaces the chat's former message drop, now removed.

| Element | Choice | Reason |
|---|---|---|
| Sending | a **Prosody HTTP module** (`POST`, body of 4 KB at most) | the message is a real XMPP message, archived and notified like the others |
| Identity | the chat relays the **person's access token**; Prosody checks it through userinfo, then requires the right issuing client (`azp`), a household group and the **same name** as the account; the sender is **the token's account**, never a body field | nobody can write on someone else's behalf, not even the chat |
| Isolation | a **relay** in the gateway pod opens **one route and one port** to the chat; the chat never reaches Prosody's HTTP port (WebSocket, files) | Prosody cannot reserve a path to a source |
| Display | "**via Sophia**" under the message (Converse.js plugin); **not editable** ("Edit" removed), but **retractable** by its sender | everyone knows what Sophia wrote, and it can be taken back |
| Limits | **30 messages a day** per person; log without text | no runaway |
| Unset | without the relay address in the chat manifest, "tell" answers that it is not open yet | a two-step go-live with no visible error |

Usage choices: the model analyses the intent, the person confirms, a rule sends; any answer other than "yes" sends nothing.

### Video calls: Jitsi Meet### Video calls: Jitsi Meet

Jitsi Meet replaced La Suite numérique's video service, planned first: its interface does not start on the household's older tablets.

**Video calls go through the browser only**, hence through the interface's cockpit (household decision): `DISABLE_DEEP_LINKING` removes the "Join in the app" page, and the mobile app is no longer used. Video calls in the older tablet's browser **work** since its VPN profile was adjusted (below).

| Element | Choice | Reason |
|---|---|---|
| Components | web, Prosody, Jicofo, JVB (the media bridge); neither database nor cache | as few parts as possible |
| Access | a home-made **adapter** (Python, standard library only) performs the OIDC sign-in with the identity provider and returns a **signed token valid 10 minutes, for a single room**; guests are refused by the identity provider, and by the adapter should one get through; states bound to the browser and single-use; the adapter's log holds neither the query string nor any secret | Jitsi only accepts a token: the adapter issues it to admitted accounts only |
| Sign-in in the cockpit | **in a window** (`tokenAuthInline`, Jitsi's native mechanism), see below | the identity provider refuses to be displayed in a frame |
| Media | **a single UDP port**, exposed through an `externalIP` on the node's VPN address (`${VPN_IP}:${JVB_UDP_PORT}`); **no NodePort** | media can only be reached through the VPN, never from the local network |
| Network | peer-to-peer and STUN off; third-party requests off; **private address candidates advertised** (the VPN address is one); bridge channel over the SCTP data channel | everything goes through the home bridge; nothing leaves for an outside service |
| Media ingress | the bridge's NetworkPolicy admits the VPN network **and the `host-network` group** on the UDP port | in OVN-Kubernetes' shared gateway, externalIP traffic reaches the pod with a rewritten source (see below) |
| OKD arbitrary UID | Jitsi images use s6-overlay, which refuses a `/run` owned by root; the variable `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` makes it accept it | **neither privilege nor `anyuid`** |
| Probes | Jicofo serves its health API on `127.0.0.1` only: `exec` probe | listening is not widened for the probe |
| Encryption | no end-to-end encryption | the home bridge sees the media, like any video bridge |
| Display | can only be displayed by the platform's chat (`frame-ancestors` in `CSP_HEADER`); camera and microphone allowed by the frame's `allow` attribute, for video only | the video service lives in the cockpit |

#### Sign-in in a window

When video calls moved into a cockpit frame, entering a room stopped working: the OIDC sign-in happened inside the frame, and the identity provider refuses to be displayed there ("content blocked" on a computer, nothing on the tablet). Display in the frame had been checked, not entering a room. Household decision: video stays in the cockpit, **only the sign-in goes through a window**, which returns to the tile. Jitsi has this flow (`tokenAuthInline`); nothing is added to the cockpit.

- A small configuration script, active **only in a frame**, turns on `tokenAuthInline` and adds `fenetre=1` to the adapter's address. Outside a frame, the redirect flow stays as it was.
- In window mode, the adapter requires a closed-form `nonce` (64 hexadecimal characters, exact check of the whole string) and keeps it in the state.
- On return from the identity provider, it serves a **return page** (`no-store`, `no-referrer`, CSP without inline script, `frame-ancestors 'none'`) that posts the token to `window.opener`, **to the video service's origin only**, then closes. A third-party page receives nothing; a stolen or replayed return gets a 400.
- The earlier checks remain: state bound to the cookie and single-use, PKCE, userinfo, groups.
- **Limits**: Jitsi does not check the `nonce` on receipt (it only identifies the mode); protection comes from the message target, the state and PKCE. The token appears in no page address, but Jitsi puts it in its WebSocket address, in both modes (masked in its log).
- **Expired token**: in window mode, the token stays in Jitsi's state, which only checks its expiry on reload; the next entry was refused. The configuration script clears it 30 s before it expires (internal `SET_JWT` action), so that the next entry reopens the window. Internal action: to be rechecked at each version upgrade.

#### Video media: three causes in a row

The conference was set up (participants entered the room), but **no media flow had ever been established**: the bridge's metrics showed `ice_succeeded 0` since installation, and the bridge expired each participant after 2 min 48. The multi-device test had been deferred to acceptance testing, never done. Three causes hid one behind the other:

1. **The bridge did not advertise its address.** `JVB_ADVERTISE_PRIVATE_CANDIDATES=false` removes every RFC 1918 address from the advertised candidates; the node's VPN address is one. The browser received no candidate. Proof: the bridge's debug state (`advertisePrivateCandidates: false`, 0 packets received or sent). Fix: `true`. The pod address is advertised too, but it is unreachable and dropped by ICE.
2. **The NetworkPolicy refused the media.** externalIP traffic is indeed translated to the pod, but, in OVN-Kubernetes' shared gateway, with a **rewritten source** `169.254.0.2` (host masquerade). The policy only admitted the VPN network: everything stayed unanswered (`[UNREPLIED]` in the node's connection-tracking table). Fix: also admit the `policy-group.network.openshift.io/host-network` group on the UDP port, as the forge is admitted through the `ingress` group. Consequence: the NetworkPolicy cannot filter this traffic per device. The computer then established its media.
3. **The iOS tablet did not send its media into the tunnel.** Its HTTPS went through the VPN, but no UDP packet reached the node. A diagnostic page (listing the device's ICE candidates, sending STUN requests to the bridge, looked up in the connection-tracking table) proved it: only the Wi-Fi address was among the candidates. **Cause**: WebKit's WebRTC on iOS (Safari as well as Chrome, which uses the same engine) only enumerates the "default" interface, and libwebrtc determines it by opening a UDP socket towards `8.8.8.8` (without sending anything). With `AllowedIPs` limited to the VPN network, that interface is the Wi-Fi. **Fix, in the device's profile**: `AllowedIPs = ${VPN_NETWORK}, 8.8.8.8/32`. The VPN becomes the "default" interface for WebRTC, and the rest of the Internet stays on Wi-Fi or the mobile network. See the [iOS device profile](../../../deploy/okd/host/wireguard/README.en.md#ios-devices-video-calls-and-the-default-network).

Result: **first video call with picture** between the computer and the older tablet, in the cockpit, through the VPN; both participants have ICE and DTLS established. Leads dropped along the way: direct device-to-device connection (off), a TURN relay over TCP (it would have failed for the same reason as UDP), the mobile app, or a port on the local network (against "everything through the VPN, in the cockpit").

**What counts as proof**: the bridge's debug state (`iceConnected`, packets) and the node's connection-tracking table. The VPN nftables rule's counter is not a check: it stayed at zero during a successful call.

## Clients

| Device | Chat | Video |
|---|---|---|
| Computer | Converse.js in the cockpit | browser, in the cockpit: **picture and sound established** |
| Android | Converse.js in the cockpit, notifications through the ntfy app | browser, in the cockpit: to be proven (the default VPN profile should be enough) |
| Older tablet (iOS 15) | Converse.js in the cockpit, badge without notifications when the page is closed | browser, in the cockpit: **picture and sound established**, with the iOS VPN profile |

While Matrix stays readable: the **first sign-in** to the Matrix chat goes through two MAS pages: account linking, then application authorisation. In the cockpit, the MAS sign-in page is refused in a frame: if the Matrix session has expired, "Sign in again" opens Element in a tab, then one comes back to the cockpit.

**Element Web is not supported by Safari 15**: this is one of the reasons for moving to Converse.js, which works there. The unread badge only appears once Messages has been opened: messaging is not loaded in the background when the cockpit opens, to spare the older tablet's memory.

## Privacy and limits

- **Home only**: chat and video are reached through the VPN only.
- **No end-to-end encryption**, neither in the chat nor in video calls: the system administrator can read the rooms. No room is therefore "private".
- **Chat media without backup.**
- **Video rooms not private between household members**: the video token is valid for any room, and a one-to-one room name can be recomputed; a third household member could join it, and would be seen. People outside the household are refused. Closing this limit needs tokens restricted to one room: later, on request.
- **Idle presence**: after the page is closed, the session stays idle for up to 72 h for notifications; the person appears present in rooms meanwhile. A choice the household accepts.
- **Notifications**: someone who knew a person's ntfy topic could send them fake alerts or see when they get one, never any content; the topic is shown to that person only.
- **Video through the browser only**: Jitsi's mobile app, which sent usage metrics to a third-party service, is no longer used.
- **Unread summary**: the route only exposes counts, never a text or a sender, and only to the person themselves, through their token.
- **Sign-out**: signing out of the cockpit also closes the sessions of the modules on a closed list, messaging included; signing out of messaging **clears the browser's data** (`Clear-Site-Data`, and a session-less page for the older tablet). Element keeps its token in the browser, out of the cockpit's reach: a known limit, lifted when Matrix is removed.
- **No agent** in the rooms for now; the chat does not receive the platform's alerts (they have their own channel, see [Observability](../../concepts/10-observabilite.en.md)).
- **Adapter**: a VPN device can exhaust its in-memory state pool and block sign-ins to the video service for 10 minutes.

## Acceptance testing to do

- a call with three devices: each sees the other two, leaving then coming back without reloading, screen sharing from a computer;
- every household device run through the candidate diagnostic page, at home then on the mobile network (Android included); the page is then removed;
- guest refused (chat and video), protected account admitted;
- final messaging on each device (under way): adding a contact by address, Family room, Android notification without content, video from a conversation, sign-out; then Matrix dismantled;
- "tell" from each device: one-to-one and to everyone, "via Sophia" mark, no "Edit", any answer other than "yes" sends nothing;
- unread summary with a real relayed token, in "What's new?".

## Planned

- **Removing Matrix** (Synapse, MAS, Element, summary module) at the end of acceptance testing.
- **Direct video buttons** to each member, and private rooms through tokens restricted to one room: later, at the household's request.
- **Unified mail**: decided, **postponed** behind the other projects; nothing is open to the household.
- **Access through the cockpit only**, once the cockpit is validated on every device: an application page opened directly will be sent back to the cockpit; direct access stays with the administrator, for troubleshooting.
- **Starting a call from Sophia's chat**, and Sophia in the rooms: later, with the agents.

## Lessons

- A local "arbitrary UID" test must also reproduce **volume ownership**: under OKD, an `emptyDir` is owned by root, which the local test did not show.
- A service exposed through an `externalIP` on the VPN address, rather than a NodePort, stays unreachable from the local network. But, in OVN-Kubernetes' shared gateway, **the pod sees a rewritten source** (`169.254.0.2`), not the device's address: a NetworkPolicy with the VPN as `ipBlock` refuses it, and cannot filter per device.
- "Do not advertise private candidates" also removes the VPN address, which is private: on a private network, it is the only useful address.
- **WebRTC on iOS does not follow the VPN routes** like the rest of the system: it only offers the default interface, determined by the route to `8.8.8.8`. A page that shows the device's ICE candidates settles in one minute what hours of logs did not.
- Displaying an application in a frame does not prove one can **sign in** within that frame: an identity provider refuses to be framed. Check the full path, up to the action.
- A firewall rule counter at zero does not prove there is no traffic: the packet's real path may avoid the chain. What counts: the service's state and the connection-tracking table.
- Software that resolves names through its own library (libunbound for Prosody) **ignores the pod's search domains**: write Service names in full, and make the test bench resolve like the cluster.
- A server that validates a token through the userinfo accepts any token of the realm, whatever the client: guard each entry point (WebSocket included) with the application's oauth2-proxy.
- An archive made on a Mac from downloaded files carries extended attributes (`com.apple.provenance`) that OKD's binary build cannot read: `COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata`, then check the archive before the build.
- A negated authentication-flow condition is set through a negation key specific to the condition: to be checked by testing, guest included.
- An `add_header` in an nginx `location` cancels those of the upper level: Element's `frame-ancestors` header is repeated in every location.
- A bench that mounts its own configuration does not prove the deployed one: a module present on the bench was missing from the ConfigMap generated by the production render. The bench now mounts the ConfigMaps **from the production render**.
- A server that cannot reserve a route to a source is protected by a **minimal relay** in front of it (one route, one port, one size), not by a network rule on its shared port.
