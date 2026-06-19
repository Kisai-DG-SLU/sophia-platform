# Ghost Search: Search Intent Obfuscation

**Ghost Search** is an obfuscation mechanism designed to hide the system's real intentions when performing searches on the Internet.

Its objective is to prevent analysis and profiling of requests emitted from the infrastructure, so as not to reveal areas of interest, ongoing projects, or strategic directions of the organization.

---

## Problem

Every web request emitted from an enterprise infrastructure leaves a trace. Search engines, CDNs, advertising networks, and access providers analyze these requests to:

- build a profile of the requesting entity
- deduce search topics, technologies used, R&D directions
- resell this data to competitors or data brokers

For an organization concerned with its sovereignty, exposing its search intentions is equivalent to exposing its strategy.

---

## Principle

Ghost Search is based on a simple principle: drown legitimate requests in a volume of indistinguishable decoy requests.

One useful request is accompanied by several dummy requests, emitted simultaneously or in close sequence, from different network identities.

An external observer cannot distinguish the real request from the decoys.

---

## Operation

### Decoy generation

Decoy requests are generated according to several strategies:

- **Thematic.** Requests on related but non-sensitive topics, to blur the exact field of research.
- **Random.** Requests on completely unrelated topics, to dilute the signal in noise.
- **Historical.** Requests reproducing past search patterns, to simulate normal and continuous activity.

### Identity rotation

Each request (useful or decoy) is emitted from a different network identity: different proxy, varied HTTP headers, different browser fingerprints.

### Temporal synchronization

Requests are emitted so that an observer cannot differentiate them by rhythm or volume. Decoys follow the same temporal distributions as real requests.

---

## Relationship with the Paranoia Airlock

Ghost Search is a module of the Paranoia Airlock. It operates upstream of the content neutralization phase:

1. Ghost Search generates requests (useful + decoys) and routes them through the obfuscation infrastructure.
2. The Paranoia Airlock retrieves responses, sanitizes them, and only transmits the text content of the useful request to the system.

---

## Position in the architecture

Ghost Search executes in the `sophia-dmz` namespace, which is the only web access zone. It requires no access from other namespaces, preserving system isolation.

---

## Objective

Ensure that an external observer cannot deduce the organization's search topics, ongoing projects, or strategic directions from analysis of its web traffic.
