# Glossary

This glossary defines key terms used throughout the SOPHIA documentation.

It includes both general AI concepts and terms specific to the architecture.

---

# AI Concepts

## LLM (Large Language Model)

A machine learning model trained on large text datasets capable of generating and understanding natural language.

Examples include GPT-style models or open-source models such as Llama or Mistral.

---

## RAG (Retrieval-Augmented Generation)

A technique that improves language model responses by retrieving relevant information from an external knowledge base before generating an answer.

This typically involves:

- a vector database
- embeddings
- a retrieval pipeline

---

## Embeddings

Vector representations of text used to compare semantic similarity between documents.

Embeddings allow systems to retrieve relevant information from large document collections.

---

## Vector Database

A database designed to store and search embeddings efficiently.

Common vector databases include:

- Qdrant
- Weaviate
- Pinecone

---

## Agent

A software component capable of performing tasks using AI models and external tools.

Agents may perform actions such as:

- writing code
- querying data
- interacting with APIs
- orchestrating workflows

---

# SOPHIA Architecture Concepts

## SOPHIA

SOPHIA stands for **Sovereign Orchestrator Platform for Holistic Intelligence Architecture**.

It is an experimental architecture designed to orchestrate AI systems within a secure and sovereign infrastructure.

---

## Brain

The **Brain** contains the memory and intellectual structure of a project.

It typically includes:

- specifications
- project configuration
- persistent memory

The Brain does not contain executable code.

---

## Repository

The repository contains the operational artifacts of a project.

Examples include:

- source code
- notebooks
- datasets
- generated outputs

Repositories are usually managed through Git.

---

## Workspace

A workspace is a temporary execution environment used by agents or users.

Characteristics:

- ephemeral
- reproducible
- isolated

Workspaces may run locally or inside containerized environments.

---

## Project

In SOPHIA, **everything is modeled as a project**.

A project represents a unit of work that includes:

- a Brain
- a repository
- one or more workspaces

---

# Security Concepts

## Sas Paranoïaque

An isolated acquisition layer responsible for retrieving information from the internet while protecting the internal infrastructure.

Its responsibilities include:

- isolating web access
- sanitizing content
- preventing data leakage

---

## Tribunal Sémantique

A validation mechanism that evaluates the credibility of external information before integrating it into the knowledge base.

Its purpose is to reduce the risk of ingesting unreliable or AI-generated content.

---

# Infrastructure Concepts

## Namespace

A logical isolation boundary used in Kubernetes environments.

Namespaces allow components to be separated and secured within the same cluster.

---

## DMZ (Demilitarized Zone)

A network segment designed to isolate systems that interact with external networks.

In SOPHIA, the DMZ hosts services responsible for interacting with the public internet.

---

## MCP (Model Context Protocol)

A protocol used to expose tools and capabilities to AI models in a structured way.

MCP allows agents to discover and invoke external capabilities.

---

# Governance Concepts

## Context Management

The process of constructing and controlling the information provided to AI models.

Proper context management helps ensure:

- predictable behavior
- efficient use of context windows
- reduced noise in prompts

---

## Workspace Management

The mechanisms used to manage execution environments for projects and agents.

This includes:

- environment creation
- isolation
- reproducibility
