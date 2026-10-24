# Modèle de sécurité SophIA

La sécurité est un principe fondamental de conception de SophIA.

L'architecture suit une approche Zero Trust : chaque composant est isolé et n'est autorisé à communiquer qu'avec les services explicitement prévus. Ce document distingue ce qui est **en place** dans l'installation de référence de ce qui est **cible** : une promesse de sécurité non tenue ne s'écrit pas au présent.

---

## Principes fondamentaux

- accès réseau par moindre privilège ;
- isolation entre les namespaces ;
- connectivité externe contrôlée ;
- décisions par des règles sans modèle, validation humaine imposée par le code ;
- infrastructure reproductible ;
- traçabilité des interactions avec l'IA.

---

## Segmentation réseau

Chaque namespace appartient à une zone de sécurité. Les communications sont restreintes par des NetworkPolicies Kubernetes ; le principe est un **refus par défaut en entrée** (`default-deny-ingress`) dans chaque namespace, puis une règle par flux légitime. Les sorties sont bornées par les règles propres à chaque application et, pour les zones sensibles, par un EgressFirewall.

| Zone | Namespaces | Rôle | État de l'isolation |
|---|---|---|---|
| Orchestration | `sophia-core` | routeur de modèles, répartiteur, workflows, bus, base relationnelle | **en place** : refus par défaut en entrée, une règle par service (le routeur de modèles n'admet que les applications, les agents, le développement, la mémoire, le routeur d'entrée et le réseau du nœud) ; sorties bornées par un EgressFirewall |
| Identité et forge | `sophia-identity`, `sophia-git` | SSO, dépôts | **en place** : entrées fermées hors flux prévus |
| Inférence | `sophia-inference` | modèles locaux | **en place** : tout refusé, entrée depuis le routeur de modèles et l'outil d'images seulement, aucune sortie |
| Outils locaux | `sophia-skills` | serveurs MCP | **en place** : aucune sortie hors DNS et modèles d'image |
| Sas | `sophia-dmz` | acquisition web | **en place** : refus par défaut ; sortie vers le web réservée à l'acquisition |
| Applications | `sophia-apps` | interfaces et modules | **en place** : refus par défaut en entrée, une règle par application |
| Agents | namespace des agents | panthéon | **en place** : entrée des agents ouverte au seul répartiteur ; un compte de service et un UID par pod |
| Mémoire | `sophia-memory` | base vectorielle, embedding, graphe | **cible** : refus par défaut à appliquer après l'inventaire des appelants ; la zone n'est pas encore isolée |
| Développement | `sophia-sandbox` | environnements de développement, clusters enfants | **cible** : refus par défaut à appliquer |

Chaque refus par défaut est appliqué un namespace à la fois : inventaire des flux légitimes, retour arrière prêt, vérification par le vrai chemin (codes HTTP des Routes, puis parcours dans le navigateur) avant et après.

### Accès à la plateforme : VPN uniquement

La plateforme ne se joint que par un VPN WireGuard, y compris depuis le réseau local ; le réseau local n'est jamais joignable depuis le VPN. Sur le nœud, une table nftables dédiée, indépendante d'OVN-Kubernetes, distingue deux plages : **administration** (tout le nœud, Forgejo) et **utilisateurs** (HTTP/HTTPS seulement), et ne relaie rien d'autre que Forgejo pour l'administration. Un garde-fou vérifie que cette table reste lisible par la version de nft embarquée dans OVN-Kubernetes ; sinon il la retire et alerte, sans jamais couper le VPN, seul chemin d'administration. Voir `deploy/okd/host/wireguard/`.

---

## Composants sans accès réseau

Certains namespaces sont isolés des réseaux externes, afin d'éliminer tout risque d'exfiltration : leurs modèles et données sont déposés depuis le nœud, à des révisions et empreintes figées.

| Namespace | État dans l'installation de référence |
|---|---|
| sophia-inference | **en place** : tout refusé, entrée depuis le routeur de modèles et l'outil d'images seulement, aucune sortie |
| sophia-skills | **en place** : aucune sortie hors DNS et modèles d'image |
| sophia-memory | **cible** : ni refus par défaut, ni sortie bornée aujourd'hui |

---

## Droits des agents

Les agents sont des exécutants, joints par le seul répartiteur, qui décide par des règles sans modèle (voir [Panthéon Agentique](concepts/08-pantheon-agentique.md)).

| Agent | Droits | Garde-fou | État |
|---|---|---|---|
| Développement | pleins pouvoirs dans son environnement, un cluster enfant par projet | aucun accès au déploiement ni aux données de production ; tout est versionné | en recette |
| Déploiement | limité au namespace des applications | approbation du plan, puis de chaque commande | prévu |
| Maintenance | administratrice du cluster | approbation du plan, puis de **chaque** commande | prévu |
| Supervision | lecture seule du cluster et de la métrologie | filtre de secrets sur tout ce qu'elle rend | prévu |

- **Aucun agent n'accède au moteur de workflows ni n'écrit sur le bus** : le répartiteur en est le seul client et le seul éditeur.
- **Identité prouvée** : chaque demande présente un jeton de compte de service projeté, de courte durée, vérifié auprès de l'API Kubernetes.
- **Une clé par exécutant**, connue de lui et du répartiteur seulement.
- **Validations humaines** par un seul chemin, l'interface du moteur de workflows, réservée au groupe d'administration ; l'auteur authentifié de chaque signal est vérifié contre la liste des approbateurs ; une approbation ne vaut qu'une fois.

---

## Acquisition de données externes

Les informations externes sont récupérées par une couche d'isolation dédiée. La couche DMZ extrait, nettoie, retire le contenu exécutable et livre au système interne un texte purifié.

Ce mécanisme empêche les scripts malveillants et les mécanismes de traçage de pénétrer dans la plateforme. Rien de ce qui vient du web n'est mémorisé tant que le [Tribunal Sémantique](concepts/05-tribunal-semantique.md) n'est pas en service.

---

## Protection des données

- contrôle d'accès strict : SSO, groupes, clés restreintes par client du routeur de modèles ;
- secrets gérés par Kubernetes : les manifestes n'en contiennent aucun ; une valeur trouvée dans l'historique d'un dépôt est changée, sans réécrire l'historique ;
- journalisation d'audit ;
- volumes chiffrés : **cible**, pas encore en place (volumes locaux non chiffrés).

Les données persistantes (bases vectorielles, bases relationnelles, dépôts) sont sur des volumes locaux du serveur ; leur chiffrement au repos est à mettre en place.

---

## Journalisation des interactions

- **En place** : journal des requêtes du routeur de modèles (routage, coûts, refus) ; historique de chaque workflow de délégation (30 jours), avec l'auteur de chaque approbation ; événements datés publiés par le répartiteur.
- **Cible** : historisation brute des échanges dans Git, pour l'audit, le rejeu et le sourçage ; alertes et workflow « incident » (voir [Observabilité](concepts/10-observabilite.md)).

---

## Améliorations prévues

- filtre anti-fuite (DLP) avant toute sortie vers un modèle extérieur ;
- Tribunal Sémantique avant toute mémorisation venue du web ;
- refus par défaut dans `sophia-memory` et `sophia-sandbox` ;
- TLS mutuel entre le répartiteur et les exécutants ;
- volumes chiffrés.
