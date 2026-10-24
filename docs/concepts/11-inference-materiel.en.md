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
| Pantheon agents | still configured on remote models, for testing | to move to local (planned) |

The reference server takes three cards: the target is one card per task family. A second or third card will serve embedding, voice and vision, **not a second general model**.

---

## Sharing the card, priority to chat

A single general model serves the interface, the modules, the agents and the planner. Without a rule, a background task can take a conversation's slots. **Planned:**

- **Two aliases on the same server.** The main alias stays with chat, school and interactive uses. A "background" alias, limited to one request at a time, serves the agents, the planner and the modules' background tasks: chat effectively keeps three slots.
- **Concurrency bounded by the dispatcher**: one mission at a time at first.
- **Small decisions**: with a modest local model, plans are broken into constrained-output decisions, framed by rules (see [Deterministic Automation](09-automation-deterministe.en.md)).

---

## Choosing the model

| Option | Effect | Status |
|---|---|---|
| Keep the current model for every role, with the "background" alias | no extra cost; per-role acceptance tests to do | planned (first step) |
| Mixture-of-experts model (35 billion parameters, 3 active) in hybrid card + RAM, replacing the current model | better reasoning expected; 12 to 16 cores during generation and 25 to 40 GB of memory, in direct competition with voice, images and office | to be measured, CPU peak included, before deciding |
| Second model on CPU for the agents | at least 16 cores permanently | ruled out: the CPU does not have that margin |

---

## Resource budget

RAM has headroom, **CPU does not**. Actual consumption is low (a few cores in normal times), but declared limits exceed the node's capacity, and upcoming workloads (office suite, hybrid model, memory re-indexing) are heavy. **Planned:**

- **Priorities**: chat and language model > voice > dispatcher and agents > office > images > development and child clusters;
- **quotas** per namespace, and requests and limits for each agent;
- image generation capped at 8 cores;
- heavy jobs at night (re-indexing, conversions).

---

See also: [Infrastructure POC](../../deploy/infrastructure.en.md) · [Local inference](../../deploy/okd/inference/README.en.md) · [Observability](10-observabilite.en.md)
