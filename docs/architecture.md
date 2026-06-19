# Architecture SophIA

SophIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) est une architecture ouverte et experimentale conque pour orchestrer des systemes d'intelligence artificielle dans un environnement souverain et securise.

La plateforme assemble des composants open-source en une infrastructure coherente qui permet aux organisations de deployer, gouverner et exploiter des systemes d'IA tout en preservant le controle de leurs donnees et de leur infrastructure.

---

## Principes architecturaux

La conception de SophIA est guidee par plusieurs principes fondamentaux :

- Souverainete sur les donnees, les modeles et l'infrastructure
- Isolation reseau stricte entre les composants critiques
- Integration modulaire de technologies open-source
- Deploiement reproductible de l'infrastructure
- Auditabilite des interactions IA

L'architecture est conque pour etre **logiciel-agnostique** et **materiel-agnostique**. Chaque composant peut etre remplace par une alternative equivalente, qu'elle soit open-source, proprietaire ou developpee en interne. Les choix effectues dans l'implementation de reference sont des exemples parmi de nombreuses configurations possibles.

---

## Architecture haut niveau

SophIA repose sur une plateforme Kubernetes (OKD / OpenShift). L'architecture suit un modele Hub and Spoke : les services cognitifs centraux sont isoles dans des namespaces dedies, tandis que les environnements de developpement et d'application sont separes dans des zones distinctes.

```
                +-----------------------+
                |     sophia-core       |
                |  Orchestration IA     |
                +-----------+-----------+
                            |
        ----------------------------------------------
        |                    |                       |
+---------------+   +---------------+      +---------------+
| sophia-git    |   | sophia-memory |      | sophia-skills |
| Code & specs  |   | Base vecto.   |      | Serveurs MCP  |
+---------------+   +---------------+      +---------------+
                                                    |
                                              +-----------+
                                              | inference |
                                              | modeles   |
                                              +-----------+
                                                    |
                                              +-----------+
                                              |   DMZ     |
                                              | web data  |
                                              +-----------+
```

---

## Namespaces centraux

### sophia-core

Couche d'orchestration centrale. Responsabilites : routage des modeles, orchestration des agents, flux d'execution, acces API.

Technologies (exemple) : LiteLLM, moteurs d'orchestration, journalisation et telemetrie.

### sophia-inference

Environnement d'execution locale des modeles. Responsabilites : hebergement de modeles locaux, inference CPU/GPU, isolation de l'execution.

Technologies (exemple) : Ollama, llama.cpp.

### sophia-memory

Couche de connaissance persistante. Responsabilites : stockage vectoriel, indexation RAG, persistence des connaissances.

Technologies (exemple) : Qdrant.

### sophia-git

Couche de gouvernance des connaissances et du code. Responsabilites : memoire de projet, stockage des specifications, versionnement du code.

Technologies (exemple) : Forgejo.

### sophia-skills

Outils et capacites contextuelles. Responsabilites : serveurs MCP, injection de contexte, execution d'outils pour les agents.

### sophia-dmz

Couche d'acquisition web securisee. Responsabilites : extraction web externe, nettoyage, mecanismes anti-tracage.

---

## Zones de developpement et d'execution

Des namespaces supplementaires fournissent des environnements controles :

| Namespace        | Role                                |
|------------------|-------------------------------------|
| sophia-sandbox   | environnements de developpement     |
| sophia-test      | validation CI/CD                    |
| sophia-apps      | interfaces utilisateur              |
| prod-*           | charges de travail locataires       |

---

## Plateforme d'infrastructure

L'implementation de reference de l'architecture SophIA fonctionne actuellement sur un cluster Kubernetes mono-noeud (OKD) deploye sur un serveur bare-metal.

Caracteristiques principales :

- Orchestration Kubernetes
- Politiques reseau strictes via des mecanismes d'isolation
- Stockage persistant
- Conception materiel-agnostique (toute infrastructure repondant aux exigences peut etre substituce)

La configuration materielle specifique utilisee pour le Proof of Concept est documentee dans la section deploiement. Elle est intentionnellement non-prescriptive : chaque organisation doit adapter les choix d'infrastructure a son propre contexte, echelle et exigences de securite.

---

## Statut

L'architecture est actuellement experimentale. Les composants d'infrastructure initiaux sont operationnels et la documentation est progressivement publiee.
