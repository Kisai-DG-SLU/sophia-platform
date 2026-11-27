# Inference and Hardware

This page says **which model serves whom**, **on which hardware**, and how a single graphics card is shared today between uses without the chat suffering.

---

## Principles

- **100% local.** The target has always been fully local inference. A remote model is only a development exception, chosen by routing, never a dependency.
- **The language model split by layers, perception apart.** The language model can span several cards, **by layers**: at each token, only small data passes from one card to the next, which the PCIe bus handles easily. *Tensor parallelism* is ruled out: it requires a direct link between the cards (NVLink). Perception, embedding, the graph and the small models have their own card, which isolates their workloads.
- **One router for all.** Interface, modules and agents call models through router aliases (LiteLLM), never a server directly. Changing model is a routing change.
- **The model chosen per task.** Routing, classification and extraction in constrained output do not need the same model as breaking down a complex goal.

---

## Today

| Use | Where | Status |
|---|---|---|
| General model (text and vision), mixture of experts: 35 billion parameters, 3 active, quantized | the only graphics card (16 GB, PCIe 3.0 x8); the experts of 34 layers stay in RAM, computed by 20 reserved cores; 8 conversations in parallel over a shared context | in service |
| Embedding | CPU, in the memory zone | in service |
| Voice (recognition, synthesis) and image generation | CPU, without network access | in service |
| Interface, modules, school | local model by default | in service |
| Pantheon agents | the local model, through the background alias; one router key per agent, limited to that alias and embedding | in service |

The reference server takes three cards. **Target, stage 1**: cards 1 and 2 carry the language model together, split by layers (chat, school, agents); card 3 carries perception (vision, OCR, voice), embedding, the graph and the small models. With a single card, the bus is loaded by copying the experts kept in RAM (about 14.7 GB per prompt batch), and the first word can take 7.8 s when six requests arrive together. On two cards, almost the whole model fits in graphics memory, and that traffic essentially disappears. The gains are to be proven by a benchmark with the real mix (chat, school, agents).

---

## Stage 2: an inference machine behind the router

Stage 1, the three A2 cards in the server, remains the current target. Stage 2, under study and with no purchase decision, adds a **DGX Spark**: GB10 chip, 128 GB of unified memory, shared between the processor and graphics compute, memory bandwidth of about 273 GB/s.

- **Outside the server, behind the router.** The DGX Spark is a separate machine, reached over the network behind LiteLLM. Only the request and the response cross the network, as with a remote model, but locally: link bandwidth is not a bottleneck.
- **Two compute pools**:

| Pool | Hardware | Uses |
|---|---|---|
| DGX Spark | the whole machine | chat and school with a larger model, code model, advanced vision, world models when needed (models that predict how a scene evolves) |
| A2 cards | cards 1 and 2, the current model split by layers | agents and background tasks; chat fallback through the router's fallbacks if the DGX Spark does not respond |
| A2 cards | card 3 | voice, embedding, document reading |

- **Aliases do not change, only routing does.** Interface, modules and agents keep their aliases; the router directs them to the DGX Spark or to the A2s.
- **Embedding stays put**: changing the embedding model would require re-indexing the whole memory.

**Limits**:

- **shared compute and bandwidth**: the models served together on the DGX Spark share its compute and its 273 GB/s; several models loaded does not mean several fast models at the same time;
- **memory shared with the system**: 110 to 115 GB actually usable out of 128;
- **ARM machine, connected over the network**: the model servers' images must exist for this architecture; 10 Gb/s port to be checked on the server side;
- **power draw** of 170 to 240 W;
- **no Internet access point**: the machine is only reached through an entry point declared in the inference namespace (`sophia-inference`), like the other model servers.

---

## Sharing the card, priority to chat

A single general model serves the interface, the modules, the agents and the planner. Without a rule, a background task can take a conversation's slots. The server has 8 slots, set at startup; **the bound is held by the clients**:

| Period | Chat (bounded by the interface) | Background alias (module tasks, non-streaming) | Agent missions (bounded by the dispatcher) |
|---|---|---|---|
| Day | 4 | 1 | 1 |
| 3 a.m. to 7 a.m. | 1 | 1 | 2 |

School and the other interactive uses take the rest of the 8 slots.

- **Two aliases on the same server** (in service). The main alias stays with chat, school and interactive uses; school never waits. The "background" alias, limited to one request at a time, serves the agents and the modules' background tasks (recipe generation, shopping lists, chat titles and summaries), falling back to the main alias as long as it is not open to a module's key. **Limit**: when streaming, the router's lock is released at the first response and does not cover generation; it only applies to non-streaming calls.
- **Chat bounded by the interface** (in service): 4 slots during the day, 1 from 3 a.m. to 7 a.m.; one more conversation waits a minute at most.
- **Missions bounded by the dispatcher**: one mission at a time per executor, and one or two missions on the background alias depending on the time. In service. Nothing is interrupted when the period changes: at 7 a.m., a running mission may make chat wait until it ends.
- **Agents' context window** set to 64,000 tokens: the local server does not publish its window, and the agent fell back to 256,000, taking chat's reserve.
- **Small decisions**: with a modest local model, plans are broken into constrained-output decisions, framed by rules (see [Deterministic Automation](09-automation-deterministe.en.md)).

A pitfall of moving to local: a remote model accepted two `system` messages in a row, the local model's chat template refuses them (see [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/README.en.md)).

---

## Choosing the model

| Option | Effect | Status |
|---|---|---|
| A single model for every role, with the "background" alias | no extra cost; per-role acceptance tests to do | in service |
| Mixture-of-experts model (35 billion parameters, 3 active) in hybrid card + RAM, replacing the 9-billion model | quality 80/85 against 74/85 on the services' series; 20 reserved cores and 40 Gi of memory; first word up to 7.8 s when six requests arrive together | in service, after a benchmark that measured the CPU peak; the 9-billion model stays available for rollback |
| Second model on CPU for the agents | at least 16 cores permanently | ruled out: the CPU does not have that margin |
| Language model split by layers over two cards | almost the whole model in graphics memory: hardly any copying of the experts over the bus, first word with several users expected much shorter | target, stage 1; to be proven by a benchmark with the real mix |
| Unified-memory machine (DGX Spark, 128 GB) outside the server, behind the router | larger models, and several models loaded together; compute and bandwidth shared between them; the A2s move to agents, fallback and perception | stage 2, under study |

---

## Resource budget

RAM has headroom, **CPU does not**. Actual consumption is low (a few cores in normal times, an 11-core peak over a week), but declared limits exceeded the node's capacity, and the new workloads (office suite, hybrid model, memory re-indexing) are heavy. The hybrid model alone reserves 20 cores, one socket of the reference node. **In service** (recipe: [`deploy/okd/cluster/`](../../deploy/okd/cluster/)):

- **Priorities, without preemption**: a **base** above everything (the cluster read pod, which lets you understand an outage, and the Git forge, where every deployment starts: never evicted), then chat and language model > voice > dispatcher and agents > office > images > development and child clusters. Only the language model server keeps the right to preempt;
- **quotas** on limits, per namespace, and explicit requests and limits for every container; the agents namespace quota is set, after the read pod's class;
- image generation capped at 8 cores.

**Lesson**: a priority class only protects pods that declare their requests. A pod without requests is the first evicted under memory pressure, whatever its class: every base pod requests at least its measured peak.

Planned: heavy jobs at night (re-indexing, conversions).

---

See also: [Infrastructure POC](../../deploy/infrastructure.en.md) · [Local inference](../../deploy/okd/inference/README.en.md) · [Observability](10-observabilite.en.md)
