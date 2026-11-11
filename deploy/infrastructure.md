# Infrastructure de Référence

Ce document décrit l'infrastructure utilisée pour le Proof of Concept (POC) de l'architecture SophIA. Cette configuration est une implémentation possible parmi d'autres et ne constitue pas un prérequis.

## Principe d'agnosticisme

L'architecture SophIA est conçue pour être :

- **Hardware-agnostique.** Aucune dépendance matérielle spécifique. L'infrastructure peut être adaptée aux contraintes budgétaires, de performance et de souveraineté de chaque organisation.
- **Software-agnostique.** Chaque composant logiciel peut être remplacé par une alternative équivalente, qu'elle soit open-source, propriétaire ou développée en interne.

Les choix techniques documentés ici sont des exemples validés par l'expérience du POC, pas des obligations.

## Configuration du POC

L'infrastructure de référence pour ce POC repose sur les éléments suivants :

- **Orchestration :** Single Node OKD (OpenShift Kubernetes Distribution)
- **Mémoire vive :** 512 Go RAM
- **Accélération :** 1 GPU 16 Go
- **Stockage :** Volumes persistants sur disques locaux ; un volume logique XFS dédié, extensible à chaud, pour chaque donnée qui grossit (base relationnelle, base vectorielle, stockage objet, forge), avec une alerte de remplissage — voir [stockage persistant](stockage-persistant.md)

Cette configuration permet de faire fonctionner l'intégralité de la stack (orchestration, inférence locale, base vectorielle, Git, outils) sur un noeud unique, ce qui est suffisant pour un POC et les phases initiales de déploiement.

## Substitutions possibles

| Composant | Exemple POC | Alternatives possibles |
|:----------|:------------|:----------------------|
| Orchestration conteneurs | OKD | Kubernetes, K3s, Rancher, EKS, AKS |
| Inférence locale | llama.cpp | vLLM, Ollama, LocalAI, inférence maison |
| Routage de modèles | LiteLLM | Portkey, gateway maison |
| Base vectorielle | Qdrant | Weaviate, Milvus, Pinecone, FAISS |
| Git / versionning | Forgejo | Gitea, GitLab CE, GitHub Enterprise |
| Moteur de workflows | Temporal (agents), n8n (automatisations) | Node-RED, StackStorm, Argo Workflows |
| Base relationnelle | PostgreSQL | MariaDB, MySQL |
| Environnement dev | OpenCode / Jupyter | VS Code Server, Coder, Theia |
| Acquisition web | Sas Paranoïaque | outillage maison, proxy dédié |

Cette liste n'est pas exhaustive. Elle illustre la philosophie de l'architecture : aucune brique n'est indispensable en soi, seule la cohérence de l'ensemble compte.

## Pré-requis généraux

Quel que soit le choix d'infrastructure, les prérequis suivants s'appliquent :

- un environnement de conteneurisation (Kubernetes ou équivalent)
- un mécanisme d'isolation réseau (network policies)
- un stockage persistant pour les bases de données et dépôts, préparé et dimensionné comme décrit dans [stockage persistant](stockage-persistant.md)
- un accès sécurisé (VPN ou équivalent) pour les administrateurs et utilisateurs
