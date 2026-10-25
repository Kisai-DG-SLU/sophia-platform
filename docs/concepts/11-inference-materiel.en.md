# Inference and Hardware

This page says **which model serves whom**, **on which hardware**, and how a single graphics card is shared between uses without the chat suffering.

---

## Principles

- **100% local.** The target has always been fully local inference. A remote model is only a development exception, chosen by routing, never a dependency.
- **One task family per card.** Language model, embedding, voice and vision: each card carries its own models, which isolates workloads. No model is split across several cards.
- **One router for all.** Interface, modules and agents call models through router aliases (LiteLLM), never a server directly. Changing model is a routing change.
- **The model chosen per task.** Routing, classification and extraction in constrained output do not need the same model as breaking down a complex goal.

---

## Today

| Use | Where | Status |
|---|---|---|
| General model (text and vision), 9 billion parameters, quantized | the only graphics card (16 GB); 4 conversations in parallel over a shared context | in service |
| Embedding | CPU, in the memory zone | in service |
| Voice (recognition, synthesis) and image generation | CPU, without network access | in service |
| Interface, modules, school | local model by default | in service |
| Pantheon agents | the local model, through the background alias; one router key per agent, limited to that alias and embedding | in service |

The reference server takes three cards: the target is one card per task family. A second or third card will serve embedding, voice and vision, **not a second general model**.

---

## Sharing the card, priority to chat

A single general model serves the interface, the modules, the agents and the planner. Without a rule, a background task can take a conversation's slots. The server keeps its 4 slots, set at startup; **the bound is held by the clients**:

| Period | Chat (bounded by the interface) | Background alias (module tasks, non-streaming) | Agent missions (bounded by the dispatcher) |
|---|---|---|---|
| Day | 2 | 1 | 1 |
| 3 a.m. to 7 a.m. | 1 | 1 | 2 |

- **Two aliases on the same server** (in service). The main alias stays with chat, school and interactive uses; school never waits. The "background" alias, limited to one request at a time, serves the agents and the modules' background tasks (recipe generation, shopping lists, chat titles and summaries), falling back to the main alias as long as it is not open to a module's key. **Limit**: when streaming, the router's lock is released at the first response and does not cover generation; it only applies to non-streaming calls.
- **Chat bounded by the interface** (in service): 2 slots during the day, 1 at night; one more conversation waits a minute at most.
- **Missions bounded by the dispatcher**: one mission at a time per executor, and one or two missions on the background alias depending on the time. Written and tested, in service at the dispatcher's next build. Nothing is interrupted when the period changes: at 7 a.m., a running mission may make chat wait until it ends.
- **Agents' context window** set to 64,000 tokens: the local server does not publish its window, and the agent fell back to 256,000, taking chat's reserve.
- **Small decisions**: with a modest local model, plans are broken into constrained-output decisions, framed by rules (see [Deterministic Automation](09-automation-deterministe.en.md)).

A pitfall of moving to local: a remote model accepted two `system` messages in a row, the local model's chat template refuses them (see [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/README.en.md)).

---

## Choosing the model

| Option | Effect | Status |
|---|---|---|
| Keep the current model for every role, with the "background" alias | no extra cost; per-role acceptance tests to do | in service (first step) |
| Mixture-of-experts model (35 billion parameters, 3 active) in hybrid card + RAM, replacing the current model | better reasoning expected; 12 to 16 cores during generation and 25 to 40 GB of memory, in direct competition with voice, images and office | to be measured, CPU peak included, before deciding |
| Second model on CPU for the agents | at least 16 cores permanently | ruled out: the CPU does not have that margin |

---

## Resource budget

RAM has headroom, **CPU does not**. Actual consumption is low (a few cores in normal times, an 11-core peak over a week), but declared limits exceeded the node's capacity, and upcoming workloads (office suite, hybrid model, memory re-indexing) are heavy. **In service** (recipe: [`deploy/okd/cluster/`](../../deploy/okd/cluster/)):

- **Priorities, without preemption**: a **base** above everything (the cluster read pod, which lets you understand an outage, and the Git forge, where every deployment starts: never evicted), then chat and language model > voice > dispatcher and agents > office > images > development and child clusters. Only the language model server keeps the right to preempt;
- **quotas** on limits, per namespace, and explicit requests and limits for every container; the agents namespace quota waits for the read pod's slot;
- image generation capped at 8 cores.

**Lesson**: a priority class only protects pods that declare their requests. A pod without requests is the first evicted under memory pressure, whatever its class: every base pod requests at least its measured peak.

Planned: heavy jobs at night (re-indexing, conversions).

---

See also: [Infrastructure POC](../../deploy/infrastructure.en.md) · [Local inference](../../deploy/okd/inference/README.en.md) · [Observability](10-observabilite.en.md)
