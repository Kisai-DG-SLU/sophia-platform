# Models enforced by role, virtual keys per use

This card explains **who may talk to which model**, and how the rule is held by the server and by the model router (LiteLLM), never by the browser or the model. It applies the [Deterministic Automation](09-automation-deterministe.en.md) pattern: the decision is a rule, written in a versioned configuration.

---

## Problem

In a household or a team, not every account is entitled to the same models: a child or a guest must stay on the local model, an adult may choose an online model. Two mistakes must be avoided:

- a rule **in the browser**: the selector hides models, but a forged request goes through;
- **a single key for everything**: every caller (chat, voice, agents, development pods) then sees every model, remote and paid ones included, and the router's master key ends up in pods that have nothing to administer.

---

## 1. The model by role, on the server

The chat server reads a **role → allowed models** table (`SOPHIA_MODELS_BY_ROLE`, versioned configuration):

| Role | Allowed models (default) |
|---|---|
| children (protected group) | the local model only |
| guests | the local model only |
| account with no known role | treated as a guest |
| adults | no restriction |

- **Explicit refusal**: a model outside the list sent by the browser gets a **403** ("model not allowed for this account: … only"), and nothing goes to the router. Never a silent substitution: the person would not know which model answered.
- **Default model** brought back to the first allowed model: a parent may have picked an online model for a child's profile before the rule existed. Saving a model outside the list in a profile answers 400.
- **Internal calls** (intent analysis, rephrasing, summary, title): they take the model already checked. Background tasks go to the local model's background alias; photos and questions about a selection always stay on the local model.
- **Interface**: the profile exposes the allowed models; the selector and the profile window offer only those. That is a convenience, not the guard.
- **Same family of rule** for document content read by a tool: it goes only to the models on a closed list of local models (`SOPHIA_MODELES_CONTENU`), and it is removed from any call to another model (see [Identity Relay](12-relais-identite.en.md)).

---

## 2. One virtual key per use

The model router issues **virtual keys**: each has a **closed list of models** and its own limits (requests per minute, budget). The rule is then held by the router, whatever the request.

| Use | Models | Limits |
|---|---|---|
| chat | the chat's models | the chat's rate and budget |
| chat voice | speech recognition and synthesis only | its own rate (300 requests per minute), no budget: local models |
| each agent (`agent-<name>`) | the local model's background alias and embedding | 120 requests per minute, no budget: the closed list prevents any paid call |
| each development pod | the chat's models, **without** voice | bounded rate and budget |
| each application (cooking, shopping…) | its own models only | its own |

### Voice: the key set by nginx

Audio routes go from nginx to the router **without going through the chat API**: they are multipart forms, which the API has no business parsing. nginx sets the voice key (`LITELLM_AUDIO_API_KEY`) **on those two routes only**, and overwrites any key sent by the browser. A request to another model with that key is refused by the router itself: the rule holds **without reading the form**.

Why a separate key: a transcription plus one synthesis per sentence, for several people at once, quickly exceeds a chat key's rate. Without a voice key, the chat falls back to the pod's key and says so at startup.

---

## 3. The master key no longer leaves the gateway

The router's master key administers it: creating keys, changing budgets. It must be read by the router alone.

1. **A virtual key for each caller** that used to read the master key (agents, development pods), stored in its own Secret. The `/key/info` check proves it: it answers an alias for a virtual key, and 404 for the master key.
2. **The salt pinned before rotation**: the router encrypts what it keeps in its database with `LITELLM_SALT_KEY`, which defaults to the master key. It is therefore set to the master key's **current value**, without displaying it; **it never changes again**. Otherwise, changing the master key would make what is already encrypted unreadable.
3. **Removal** of the master key from the callers' Secrets.
4. **New master key**, drawn at random and never displayed, set through a patch read from standard input, after the old one has been backed up outside any repository. Salt, removal and rotation take **a single restart** of the router.
5. **Checks**: the key list answers with the new master key; each agent answers; each development pod shows its own alias.

So that this restart cuts nothing, the router has **probes** (readiness on `/health/readiness`, liveness on `/health/liveliness`, 3-second timeout, because readiness queries the database) and a **RollingUpdate** strategy (`maxSurge: 1`, `maxUnavailable: 0`): the old pod serves until the new one is ready. The namespace quota admits that second pod. Without a probe, the pod was declared ready about thirty seconds before listening, hence an outage.

---

## 4. The tool: `create-virtual-key.py`

A script run inside the router's pod, which never displays a key ([`deploy/okd/core/litellm/create-virtual-key.py`](../../deploy/okd/core/litellm/create-virtual-key.py)); it never modifies or deletes an existing key:

- `--modeles a,b --rpm N`: explicit list and rate, no budget; each model must exist in the router; `*` is refused;
- `--comme <alias>`: copies the models and limits (rate, budget) of an existing key, `--sans x,y` removes some, never adds any; an "all models" reference is refused;
- `--dry-run`: shows the key to be created, without creating anything; an alias already taken stops the script;
- `--eval VAR`: returns the key in a shell variable, which then goes into a Secret through a pipe (`printf … | oc set data … --from-file=…=/dev/stdin`), never as an argument;
- `--info <alias>`: models, limits, spend, and a **fingerprint** of the key (start of its SHA-256), to compare with the fingerprint of the Secret's value to verify without displaying anything.

Tested against a fake router: dry run, unknown model, missing limit, incompatible options, creation, alias already taken, `--info`.

---

## Status

| Item | Status |
|---|---|
| Models by role in the chat server, reduced selector | in service |
| Voice key set by nginx | in service |
| One key per agent; master key removed from callers and rotated | in service |
| Router probes and RollingUpdate ([`deployment.yaml`](../../deploy/okd/core/litellm/deployment.yaml)) | in service |
| A development pod key per project, created by the setup script | ready (at the next pod creation) |

---

## What this card does not do

- The browser decides no model: it proposes, the server refuses or lets through.
- No key sees "every model".
- The master key is read by no pod outside the router.

---

## Place in the architecture

- model router: `sophia-core` ([`deploy/okd/core/`](../../deploy/okd/core/));
- chat interface: `sophia-interface` ([`deploy/okd/apps/chat-interface/`](../../deploy/okd/apps/chat-interface/));
- agents: [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/);
- sharing the local model: [Inference and Hardware](11-inference-materiel.en.md);
- overall protections: [Security model](../security.en.md).
