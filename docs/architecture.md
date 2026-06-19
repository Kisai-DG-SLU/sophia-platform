# Architecture SophIA

SophIA (Sovereign Orchestrator Platform for Holistic Intelligence Architecture) est une architecture ouverte et experimentale conque pour orchestrer des systemes d'intelligence artificielle dans un environnement souverain et securise.

La plateforme assemble des composants open-source en une infrastructure coherente qui permet aux organisations de deployer, gouverner et exploiter des systemes d'IA tout en preservant le controle de leurs donnees et de leur infrastructure.

---

## Principes architecturaux

La conception de SophIA est guidee par plusieurs principes fondamentaux :

- Souverainete sur les donnees, les modeles et l'infrastructure
- **Model-agnostique** : l'architecture ne depend d'aucun modele specifique. Chaque agent, etant un pod autonome, peut utiliser un modele different -- du plus petit modele local au plus grand modele public. L'intelligence du systeme reside dans l'architecture, pas dans le modele.
- Isolation reseau stricte entre les composants critiques
- Integration modulaire de technologies open-source
- Deploiement reproductible de l'infrastructure
- Auditabilite des interactions IA

L'architecture est conque pour etre **model-agnostique**, **logiciel-agnostique** et **materiel-agnostique**. Chaque composant peut etre remplace par une alternative equivalente, qu'elle soit open-source, proprietaire ou developpee en interne. Les choix effectues dans l'implementation de reference sont des exemples parmi de nombreuses configurations possibles.

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

## Architecture anti-hallucination

La plateforme est concue pour restreindre les hallucinations non pas par le modele, mais par l'architecture elle-meme. Les mecanismes suivants sont independants du modele sous-jacent :

- **Confinement RBAC** : chaque agent a des permissions strictement minimales. Meme si un agent hallucine une commande destructrice, le cluster Kubernetes la rejette (principe du moindre privilege).
- **HITL par code** : Athena et Ouranos ont leurs actions de mutation interceptees par un verrou HITL au niveau du terminal. Aucune action critique n'est executee sans validation humaine, quelque soit le modele.
- **Format de sortie impose** : les sous-agents communiquent exclusivement en JSON strict. Tout ecart de format est detecte et rejete.
- **Isolation reseau** : les NetworkPolicies empechent tout agent de communiquer en dehors de son perimetre autorise.
- **Supervision** : Dionysos observe en lecture seule l'ensemble du systeme et peut alerter sur des comportements anormaux.

Ces mecanismes fonctionnent avec n'importe quel modele, du plus petit (quelques milliards de parametres) au plus grand. L'architecture ne suppose aucune capacite agentique intrinseque du modele -- le comportement agentique est enforce par la structure des pods, le RBAC et les contraintes d'infrastructure.

---

## Statut

L'architecture est actuellement experimentale. Les composants d'infrastructure initiaux sont operationnels et la documentation est progressivement publiee.
