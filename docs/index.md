# Documentation SophIA

Bienvenue dans la documentation de l'architecture SophIA.

---

## Vue d'ensemble

- [Architecture](architecture.md) — Principes, composants et organisation haut niveau
- [Vision](vision.md) — Objectifs et motivations du projet
- [Problem Space](problem-space.md) — Problématique adressée par SophIA
- [Security](security.md) — Modèle de sécurité et isolation
- [Roadmap](roadmap.md) — Étapes et planification
- [Glossary](glossary.md) — Lexique des termes

---

## Concepts architecturaux

| # | Concept | Description |
|---|---------|-------------|
| 00 | [Project Model](concepts/00-project-model.md) | Modèle de gestion de projet et espaces de travail |
| 01 | [Context Management](concepts/01-context-management.md) | Gestion du contexte pour les interactions avec les modèles |
| 02 | [Workspace Management](concepts/02-workspace-management.md) | Isolation et gestion des environnements de travail |
| 03 | [RAG 5D](concepts/03-rag-5d.md) | Topologie de la connaissance en cinq dimensions |
| 04 | [Sas Paranoïaque](concepts/04-sas-paranoiaque.md) | Acquisition web isolée et sécurisée |
| 05 | [Tribunal Sémantique](concepts/05-tribunal-semantique.md) | Validation de confiance avant ingestion RAG |
| 06 | [Ghost Search](concepts/06-ghost-search.md) | Requêtes leurres pour masquer les intentions |
| 07 | [DLP Filter](concepts/07-dlp-filter.md) | Détection et blocage des fuites de données |
| 08 | [Panthéon Agentique](concepts/08-pantheon-agentique.md) | Agents spécialisés, confinement et isolation |
| 09 | [Automation Déterministe](concepts/09-automation-deterministe.md) | Workflows déterministes avec n8n |

---

## Développement

- [OpenCode Workflow](development/opencode-workflow.md) — Workflow de développement avec OpenCode
- [Test Orchestration](development/test-orchestration.md) — Orchestration des tests et validation

---

## Déploiement

- [Aperçu du déploiement](../deploy/README.md) — Exemple de déploiement sur OKD
- [Infrastructure POC](../deploy/infrastructure.md) — Spécification du Proof of Concept
