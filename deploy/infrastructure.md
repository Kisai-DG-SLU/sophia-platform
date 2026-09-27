# Infrastructure de Reference

Ce document decrit l'infrastructure utilisee pour le Proof of Concept (POC) de l'architecture SophIA. Cette configuration est une implementation possible parmi d'autres et ne constitue pas un prerequis.

## Principe d'agnosticisme

L'architecture SophIA est concue pour etre :

- **Hardware-agnostique.** Aucune dependance materielle specifique. L'infrastructure peut etre adaptee aux contraintes budgetaires, de performance et de souverainete de chaque organisation.
- **Software-agnostique.** Chaque composant logiciel peut etre remplace par une alternative equivalente, qu'elle soit open-source, proprietaire ou developpee en interne.

Les choix techniques documentes ici sont des exemples valides par l'experience du POC, pas des obligations.

## Configuration du POC

L'infrastructure de reference pour ce POC repose sur les elements suivants :

- **Orchestration :** Single Node OKD (OpenShift Kubernetes Distribution)
- **Memoire vive :** 512 Go RAM
- **Acceleration :** 1 GPU 16 Go
- **Stockage :** Volumes persistants sur disques locaux

Cette configuration permet de faire fonctionner l'integralite de la stack (orchestration, inference locale, base vectorielle, Git, outils) sur un noeud unique, ce qui est suffisant pour un POC et les phases initiales de deploiement.

## Substitutions possibles

| Composant | Exemple POC | Alternatives possibles |
|:----------|:------------|:----------------------|
| Orchestration conteneurs | OKD | Kubernetes, K3s, Rancher, EKS, AKS |
| Inference locale | Ollama / llama.cpp | vLLM, LocalAI, inference maison |
| Routage de modeles | LiteLLM | Portkey, gateway maison |
| Base vectorielle | Qdrant | Weaviate, Milvus, Pinecone, FAISS |
| Git / versionning | Forgejo | Gitea, GitLab CE, GitHub Enterprise |
| Moteur de workflows | n8n | Node-RED, StackStorm, Temporal |
| Base relationnelle | PostgreSQL | MariaDB, MySQL |
| Environnement dev | OpenCode / Jupyter | VS Code Server, Coder, Theia |
| Acquisition web | Sas Paranoiaque | outillage maison, proxy dedie |

Cette liste n'est pas exhaustive. Elle illustre la philosophie de l'architecture : aucune brique n'est indispensable en soi, seule la coherence de l'ensemble compte.

## Pre-requis generaux

Quel que soit le choix d'infrastructure, les prerequis suivants s'appliquent :

- un environnement de conteneurisation (Kubernetes ou equivalent)
- un mecanisme d'isolation reseau (network policies)
- un stockage persistant pour les bases de donnees et depots, prepare et dimensionne comme decrit dans [stockage persistant](stockage-persistant.md)
- un acces securise (VPN ou equivalent) pour les administrateurs et utilisateurs
