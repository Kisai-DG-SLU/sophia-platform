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
| Applications | `sophia-apps` | interfaces et modules | **en place** : refus par défaut en entrée, une règle par application. L'agent de déploiement y est administrateur et pourrait lire les Secrets d'une application : l'interface de discussion et l'outil de visualisation reçoivent chacun leur namespace (**prévu** : conçus, manifestes prêts), sans aucune liaison vers un agent, et l'école sa propre adresse |
| Stockage objet | `sophia-storage` | S3 commun | **en place** : refus par défaut en entrée **et** en sortie (DNS seul) ; une identité par application, limitée à son seau ; aucun accès anonyme |
| Agents | namespace des agents | panthéon | **en place** : entrée des agents ouverte au seul répartiteur ; un compte de service et un UID par pod ; une clé du routeur de modèles par agent. **Cible** : les sorties vers Internet, aujourd'hui sans contrôle, à inventorier puis fermer par un EgressFirewall, d'abord en observation |
| Mémoire | `sophia-memory` | base vectorielle, embedding, graphe | **cible** : refus par défaut à appliquer après le service mémoire ; la zone n'est pas encore isolée, et la base vectorielle répond sans clé |
| Développement | `sophia-sandbox` | environnements de développement, clusters enfants | **cible** : refus par défaut à appliquer |

Gabarits : `deploy/okd/apps/00-default-deny.yaml`, `deploy/okd/core/network/default-deny-ingress.yaml` et la règle d'entrée du routeur de modèles, `deploy/okd/core/litellm/network-policy.yaml`.

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
- **Une clé du routeur de modèles par agent**, limitée au modèle local de fond et à l'embedding ; la clé maître du routeur ne sort plus de son pod, puis se renouvelle.
- **Outils web des agents sans adresses internes** (`allow_private_urls` coupé, contre la falsification de requêtes vers le cluster) ; catalogue de modèles en ligne coupé.
- **Disponibilité de l'administration** : le pod de lecture du cluster et la forge Git sont dans une classe de priorité qu'aucune autre charge ne peut évincer ([`deploy/okd/cluster/`](../deploy/okd/cluster/)).
- **Validations humaines** par un seul chemin aujourd'hui, l'interface du moteur de workflows, réservée au groupe d'administration (l'interface de discussion, avec le jeton de la personne relayé, viendra en premier chemin) ; l'auteur authentifié de chaque signal est vérifié contre la liste des approbateurs ; une approbation ne vaut qu'une fois.

---

## Acquisition de données externes

Les informations externes sont récupérées par une couche d'isolation dédiée. La couche DMZ extrait, nettoie, retire le contenu exécutable et livre au système interne un texte purifié.

Ce mécanisme empêche les scripts malveillants et les mécanismes de traçage de pénétrer dans la plateforme. Rien de ce qui vient du web n'est mémorisé tant que le [Tribunal Sémantique](concepts/05-tribunal-semantique.md) n'est pas en service.

---

## Protection des données

- contrôle d'accès strict : SSO, groupes, clés restreintes par client du routeur de modèles ;
- un outil qui agit pour la personne reçoit son identité par un jeton relayé sur une seule route, vers une liste fermée de serveurs, vérifié puis échangé contre un jeton émis pour l'outil ; le service garde ses propres droits, et le modèle ne voit jamais le jeton (voir [Relais de l'identité](concepts/12-relais-identite.md)) ;
- secrets gérés par Kubernetes : les manifestes n'en contiennent aucun ; un Secret se crée par l'entrée standard, jamais en argument d'une commande (visible dans la liste des processus), et aucune valeur n'est affichée ; une valeur trouvée dans l'historique d'un dépôt est changée, sans réécrire l'historique ;
- lecture des dépôts par une clé de déploiement en lecture seule, propre à chaque dépôt, jamais par le jeton d'un administrateur de la forge : **en place** pour la synchronisation des contenus de l'école, **prévu** pour les builds de l'interface et de l'outil de visualisation ;
- journalisation d'audit ;
- volumes chiffrés : **cible**, pas encore en place (volumes locaux non chiffrés).

Les données persistantes (bases vectorielles, bases relationnelles, dépôts) sont sur des volumes locaux du serveur ; leur chiffrement au repos est à mettre en place.

---

## Journalisation des interactions

- **En place** : journal des requêtes du routeur de modèles (routage, coûts, refus) ; historique de chaque workflow de délégation (30 jours), avec l'auteur de chaque approbation ; événements datés publiés par le répartiteur.
- **En place** : métrologie des services et règles d'alerte, dont le retrait du filtre VPN par son garde-fou (voir [Observabilité](concepts/10-observabilite.md)).
- **Cible** : historisation brute des échanges dans Git, pour l'audit, le rejeu et le sourçage ; routage des alertes vers le répartiteur et workflow « incident ».

---

## Améliorations prévues

- filtre anti-fuite (DLP) avant toute sortie vers un modèle extérieur ;
- Tribunal Sémantique avant toute mémorisation venue du web ;
- refus par défaut dans `sophia-memory` et `sophia-sandbox` ;
- contrôle des sorties du namespace des agents ;
- namespaces dédiés pour l'interface de discussion et l'outil de visualisation ;
- renouvellement de la clé maître du routeur de modèles ;
- TLS mutuel entre le répartiteur et les exécutants ;
- volumes chiffrés.
