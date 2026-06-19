# Le Pantheon Agentique : Specialisation et Confinement

Le **Pantheon Agentique** est l'ensemble des agents specialises qui operent au sein de l'architecture SophIA. Chaque agent possede un role, des droits et un perimetre d'action strictement definis.

L'objectif est de specialiser les comportements plutot que de confier l'ensemble des taches a un agent generaliste, qui serait plus difficile a controler et a auditer.

---

## Principe de conception

Dans une architecture multi-agents, le risque principal est la dilution des responsabilites. Un agent capable de tout faire est un agent capable de faire n'importe quoi.

Le Pantheon Agentique repond a ce probleme en appliquant deux regles strictes :

1. **Un agent, un domaine.** Chaque agent est specialise dans un type de tache et ne peut pas en exercer d'autre.
2. **Droits minimaux.** Chaque agent dispose des permissions strictement necessaires a l'execution de ses taches, et rien de plus.

Cette approche permet de limiter l'impact d'un comportement errone ou malveillant : un agent compromis ne peut pas sortir de son domaine.

**Model-agnostique par conception.** Chaque agent etant un pod independant, chaque agent peut utiliser un modele different. Un agent pourrait meme fonctionner sans modele agentique dedie -- le comportement agentique (specialisation, confinement, format de sortie) est enforce par l'infrastructure Kubernetes, pas par le modele. Cela signifie que la plateforme peut integrer des modeles de tailles et de capacites tres differentes, voire des outils non-base sur l'IA.

---

## Les agents

L'architecture definit quatre roles agentiques fondamentaux. Cette liste n'est pas exhaustive et peut etre etendue selon les besoins de l'organisation.

### Hephaistos (developpement)

Agent charge du developpement de nouveaux outils et composants. Il opere exclusivement dans un environnement sandbox sterile, isole du systeme de production.

Son perimetre :

- creation de code dans un environnement isole
- execution de tests dans la sandbox
- soumission de composants valides au circuit de validation

Il n'a aucun acces au deploiement, a la memoire persistante, ni aux donnees de production.

### Ouranos (deploiement)

Agent charge du deploiement et de l'exposition des composants valides par le circuit de validation.

Son perimetre :

- deploiement dans les espaces de preproduction et production
- exposition des services via les interfaces autorisees
- application des configurations validees

Il n'a aucun acces au code source en cours de developpement ni aux donnees brutes non validees.

### Athena (maintenance)

Agent charge de la maintenance de la plateforme et de l'application des correctifs.

Son perimetre :

- surveillance de l'etat des composants
- application des correctifs valides
- execution de taches de maintenance planifiees

Athena est soumis a une regle de securite specifique : toute action impactant le systeme est soumise a un script externe deterministe qui valide ou rejette l'operation, independamment de la decision du modele. Ce mecanisme, appele Human-In-The-Loop (HITL) impose par code, garantit qu'aucune action critique n'est executee sur la seule base d'une inference.

### Dionysos (supervision)

Agent charge de la supervision de l'ensemble de l'architecture et des autres agents.

Son perimetre :

- surveillance du comportement des agents
- detection d'anomalies et d'ecarts
- remontee d'alertes

Dionysos a un acces en lecture seule a l'ensemble du systeme. Il peut alerter mais ne peut pas agir directement sur les composants.

---

## Confinement et isolation

Chaque agent opere dans un namespace Kubernetes dedie, avec des NetworkPolicies restreignant ses communications entrantes et sortantes.

Les agents ne peuvent pas communiquer entre eux directement. Toute interaction entre agents transite par l'orchestrateur central (`sophia-core`), qui applique les regles de routage et de securite.

---

## Position dans l'architecture

Le Pantheon Agentique s'appuie sur :

- l'orchestrateur (`sophia-core`) pour le routage des demandes vers l'agent approprie
- les workspaces (`sophia-sandbox`) pour les environnements d'execution isolee
- les outils MCP (`sophia-skills`) pour les capacites externes
- le circuit de validation automatise et humain pour valider les actions avant deploiement

---

## Objectif

Le Pantheon Agentique permet de structurer l'intelligence du systeme en domaines specialises, chacun etant isole, auditable et controlede maniere independante. Cette architecture reduit la surface d'attaque, facilite le debogage et permet une evolution progressive par ajout ou remplacement d'agents sans impact sur le reste du systeme.
