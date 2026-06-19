# The Paranoia Airlock

The **Paranoia Airlock** is an isolation mechanism designed to interact with the Internet while protecting SophIA's internal infrastructure.

Its objective is simple: consume external information without exposing the infrastructure or contaminating the knowledge base.

---

## Problem

Internet use by AI agents poses several risks:

- data leakage through requests
- user tracking
- retrieval of malicious content
- ingestion of AI-generated content (AI sludge)
- injection of scripts or payloads into the data pipeline

In a sovereign system, direct web access by agents is not acceptable.

---

## Principle

The Paranoia Airlock acts as an isolated buffer zone (DMZ) between the Internet and the rest of the system.

Agents never access the web directly. The flow is as follows:

Agent to Paranoia Airlock to Internet, then sanitization, validation, and transmission to the system.

---

## Operation

The Paranoia Airlock applies several mechanisms.

### Isolation

Web requests are executed in ephemeral, isolated jobs. These jobs are destroyed after use.

### Obfuscation

To limit tracking and request analysis:

- proxy usage
- generation of decoy requests (shadow queries)
- network identity rotation

Example: 1 useful request for 3 to 4 decoy requests.

### Content neutralization

Retrieved pages are destroyed and rebuilt:

- complete JavaScript removal
- tracker removal
- dynamic script removal

The final result is converted to raw Markdown.

### Controlled transmission

Only sanitized text content is transmitted to the internal system.

---

## Position in the architecture

The Paranoia Airlock is deployed in a dedicated namespace (`sophia-dmz`). It constitutes the only authorized entry point for web data.

---

## Objective

Guarantee that no sensitive data leaks to the Internet, no external code penetrates the system, and only validated textual information is ingested.
