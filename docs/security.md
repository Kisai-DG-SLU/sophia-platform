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
| Identité et forge | `sophia-identity`, `sophia-git` | SSO, dépôts | **en place** : entrées fermées hors flux prévus. **Réserve** : la règle posée par l'opérateur du fournisseur d'identité ouvre son port HTTP interne à tout le cluster, ce qui annule la restriction ; à corriger |
| Inférence | `sophia-inference` | modèles locaux | **en place** : tout refusé, entrée depuis le routeur de modèles et l'outil d'images seulement, aucune sortie |
| Outils locaux | `sophia-skills` | serveurs MCP | **en place** : aucune sortie hors DNS et modèles d'image, sauf l'outil des fichiers (fournisseur d'identité et port interne de la bureautique) |
| Sas | `sophia-dmz` | acquisition web | **en place** : refus par défaut ; sortie vers le web réservée à l'acquisition |
| Applications | `sophia-apps` | modules | **en place** : refus par défaut en entrée, une règle par application ; plus aucune SCC privilégiée sur le compte par défaut. L'agent de déploiement y est administrateur et pourrait lire les Secrets d'une application : c'est pourquoi l'interface de discussion et l'outil de visualisation en sont sortis |
| Interface de discussion | `sophia-interface` | chat | **en place** : namespace propre, sans aucune liaison vers un agent ; quota, valeurs par défaut, refus par défaut en entrée ; les services joints (base, sas web, outils MCP, modules) n'admettent plus l'interface que depuis ce namespace, l'ancien emplacement est vidé et ses entrées retirées ; les sorties du cockpit vers les applications (relais d'authentification de la cuisine et de la visualisation, route de résumé de la messagerie) sont dans une politique à part, une règle par destination |
| Chat permanent | `sophia-messagerie` | messagerie Matrix du foyer | **en service, en recette** : quota, valeurs par défaut, EgressFirewall, refus par défaut, aucune liaison d'agent ; fédération coupée ; accès réservé aux groupes du foyer, invités refusés ; seule entrée nouvelle : la route de résumé depuis le pod de l'interface |
| Visio | `sophia-visio` | visioconférence | **en service, en recette** : même socle ; média sur un seul port UDP, joignable par le VPN seulement ; pair-à-pair et serveurs tiers coupés ; navigateur seulement, plus d'application mobile |
| Visualisation | `sophia-workflow` | état mesuré de la plateforme, contrôle des miroirs | **en place** : namespace propre, sans liaison vers un agent ; compte de lecture qui ne lit pas les Secrets ; refus par défaut en entrée |
| Bureautique | `sophia-workspace` | fichiers et édition en ligne | **en place** : refus par défaut en entrée, une règle par flux ; l'API pour les outils n'est ouverte qu'au pod de l'outil, sur un port interne en lecture |
| Builds | `sophia-skills-build` | construction des outils MCP | **en place** : aucun compte d'agent ; sortie bornée par un EgressFirewall au registre interne, aux services du cluster, à l'API du cluster et au dépôt de paquets Python |
| Stockage objet | `sophia-storage` | S3 commun | **en place** : refus par défaut en entrée **et** en sortie (DNS seul) ; une identité par application, limitée à son seau ; aucun accès anonyme |
| Agents | namespace des agents | panthéon | **en place** : entrée des agents ouverte au seul répartiteur ; un compte de service et un UID par pod ; une clé du routeur de modèles par agent. **Cible** : les sorties vers Internet, aujourd'hui sans contrôle, à inventorier puis fermer par un EgressFirewall, d'abord en observation |
| Mémoire | `sophia-memory` | base vectorielle, embedding, graphe | **cible** : refus par défaut à appliquer après le service mémoire ; la zone n'est pas encore isolée, et la base vectorielle répond sans clé (collection vide, ingestion suspendue) |
| Développement | `sophia-sandbox` | environnements de développement ; prévu : un cluster virtuel par projet | **en place** : plus aucune SCC privilégiée, un pod privilégié y est refusé ; la passerelle SSH a une SCC propre (celle des UID fixes, plus le seul `SYS_CHROOT`). **Cible** : règle réseau d'administration sur tout le namespace et admission des seules images du registre interne |

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
| Développement | pleins pouvoirs dans son environnement, sans privilège sur le nœud ; prévu : un cluster virtuel éphémère par projet, recréé depuis la forge | aucun accès au déploiement ni aux données de production ; tout est versionné | en recette |
| Déploiement | limité au namespace des applications | approbation du plan, puis de chaque commande | prévu |
| Maintenance | administratrice du cluster | approbation du plan, puis de **chaque** commande | prévu |
| Supervision | lecture seule du cluster et de la métrologie | filtre de secrets sur tout ce qu'elle rend | prévu |

- **Aucun agent n'accède au moteur de workflows ni n'écrit sur le bus** : le répartiteur en est le seul client et le seul éditeur.
- **Identité prouvée** : chaque demande présente un jeton de compte de service projeté, de courte durée, vérifié auprès de l'API Kubernetes.
- **Une clé par exécutant**, connue de lui et du répartiteur seulement.
- **Une clé du routeur de modèles par agent**, limitée au modèle local de fond et à l'embedding ; la clé maître du routeur ne sort plus de son pod, et elle a été renouvelée ([Modèles par rôle](concepts/13-modeles-par-role.md)).
- **Outils web des agents sans adresses internes** (`allow_private_urls` coupé, contre la falsification de requêtes vers le cluster) ; catalogue de modèles en ligne coupé.
- **Alertes de l'administrateur hors de la plateforme** : un bot dédié, qui n'écrit qu'à l'administrateur, reçoit les alertes `warning` et `critical` des deux Alertmanager ; son jeton n'existe que dans les deux namespaces de supervision ; aucun agent n'y a accès ([Observabilité](concepts/10-observabilite.md)).
- **Disponibilité de l'administration** : le pod de lecture du cluster et la forge Git sont dans une classe de priorité qu'aucune autre charge ne peut évincer ([`deploy/okd/cluster/`](../deploy/okd/cluster/)).
- **Validations humaines** par un seul chemin aujourd'hui, l'interface du moteur de workflows, réservée au groupe d'administration (l'interface de discussion, avec le jeton de la personne relayé, viendra en premier chemin) ; l'auteur authentifié de chaque signal est vérifié contre la liste des approbateurs ; une approbation ne vaut qu'une fois.

---

## Acquisition de données externes

Les informations externes sont récupérées par une couche d'isolation dédiée. La couche DMZ extrait, nettoie, retire le contenu exécutable et livre au système interne un texte purifié.

Ce mécanisme empêche les scripts malveillants et les mécanismes de traçage de pénétrer dans la plateforme. Rien de ce qui vient du web n'est mémorisé tant que le [Tribunal Sémantique](concepts/05-tribunal-semantique.md) n'est pas en service.

---

## Protection des données

- contrôle d'accès strict : SSO, groupes ; modèles imposés par le serveur selon le rôle (enfants et invités sur le modèle local), une clé virtuelle du routeur de modèles par usage, la clé maître confinée au routeur (voir [Modèles par rôle](concepts/13-modeles-par-role.md)) ;
- un outil qui agit pour la personne reçoit son identité par un jeton relayé sur une seule route, vers une liste fermée de serveurs, vérifié puis échangé contre un jeton émis pour l'outil ; le service garde ses propres droits, et le modèle ne voit jamais le jeton (voir [Relais de l'identité](concepts/12-relais-identite.md)) ; vers une route de résumé du cockpit, le jeton est vérifié tel quel : audience propre à l'application (ajoutée par un mappeur sur le client de l'interface), aucun émetteur supplémentaire, un jeton refusé reçoit 403 et jamais une redirection ;
- applications affichées dans le cockpit : chacune n'accepte d'être affichée en cadre que par l'interface (`frame-ancestors`), la liste des cadres de l'interface est fermée et testée, et un message d'un cadre n'est accepté que s'il vient de l'origine **et** du cadre attendus ; la page de connexion du fournisseur d'identité reste refusée dans un cadre (« Se reconnecter » ouvre un onglet). Prévu : l'accès aux applications par le cockpit seul, avec une exception pour l'administrateur ; c'est une règle d'usage, pas une barrière de sécurité, chaque application gardant sa propre connexion ;
- sorties du modèle qui quittent la conversation encadrées par des contrôles déterministes : un lieu tiré par le modèle n'est retenu que s'il figure dans le message ou parmi les lieux enregistrés, un identifiant de document vient du résultat d'un outil et jamais du modèle, un chemin ouvert dans le cockpit a une forme fermée revérifiée par le navigateur, un lieu par coordonnées n'est inséré que par le serveur (les coordonnées venues du modèle sont retirées) et un service extérieur de météo ne reçoit que le centre de la commune, arrondi ; l'insertion de texte dans un document ouvert (en service) n'a lieu que si l'analyse la demande et qu'un document modifiable est ouvert, en texte brut assaini et borné, par une liste fermée de messages ; le contexte d'une application (module, page) n'ajoute qu'une ligne au message système, jamais un droit ;
- secrets gérés par Kubernetes : les manifestes n'en contiennent aucun ; un Secret se crée par l'entrée standard, jamais en argument d'une commande (visible dans la liste des processus), et aucune valeur n'est affichée ; une valeur trouvée dans l'historique d'un dépôt est changée, sans réécrire l'historique ;
- lecture des dépôts par une clé de déploiement en lecture seule, propre à chaque dépôt, jamais par le jeton d'un administrateur de la forge : **en place** pour la synchronisation des contenus de l'école et pour les builds de l'interface et de l'outil de visualisation. **Reste** : le jeton de l'administrateur de la forge sert encore à pousser et à d'autres builds ; inventaire de ses usages puis jetons limités par usage ;
- base relationnelle : **un rôle par base, sans superutilisateur** ; le superutilisateur ne se connecte qu'en local ;
- confiance des relais d'authentification : l'oauth2-proxy de l'interface ne croit l'adresse client transmise que si elle vient du routeur d'entrée ; de même pour tous les autres oauth2-proxy (modules, visualisation, interface des workflows) ;
- interface et appareils du foyer sans dépendance externe : polices et bibliothèques du navigateur servies par l'image, aucun CDN dans la politique de sécurité du contenu ;
- chat permanent et visio sans chiffrement de bout en bout, choix assumé : un administrateur de la plateforme peut lire les salons ; les médias du chat n'ont pas de sauvegarde ;
- jetons masqués dans les journaux d'accès des relais ; journaux du routeur de modèles en `INFO`, jamais en `DEBUG` (qui écrirait chaque requête entière) ;
- rétention : journal détaillé du routeur de modèles et historique des workflows 30 jours ; corbeille du stockage objet 30 jours ; métrologie 15 jours ; conversations et applications sans purge automatique ;
- **sauvegardes planifiées : cible**. Aujourd'hui, des sauvegardes complètes manuelles avant chaque opération ; les dépôts de la forge ont chacun **un** miroir privé chez un hébergeur externe, contrôlé toutes les heures ([module Visualisation](modules/visualisation/README.md)) ; le travail se fait dans la forge seulement, et la branche par défaut des miroirs publics est protégée contre la poussée forcée et la suppression, et certains dépôts n'en ont jamais (transcripts des sessions d'assistance au code). Cible : une sauvegarde chiffrée en Europe pour les dépôts sensibles, obligatoire dans un cadre professionnel ;
- **minimisation des notes de travail** : les suivis et plans lus par les assistants de code ne contiennent ni prénom d'enfant ni donnée sensible (santé, scolarité, adresse), mais des rôles ; un hook avant commit refuse les termes interdits par leurs empreintes (HMAC), sans jamais les afficher ; l'historique n'est pas réécrit ;
- journalisation d'audit ;
- double authentification : **cible** ;
- volumes chiffrés : **cible**, pas encore en place (volumes locaux non chiffrés).

Les données persistantes (bases vectorielles, bases relationnelles, dépôts) sont sur des volumes locaux du serveur ; leur chiffrement au repos est à mettre en place.

---

## Journalisation des interactions

- **En place** : journal des requêtes du routeur de modèles (routage, coûts, refus) ; historique de chaque workflow de délégation (30 jours), avec l'auteur de chaque approbation ; événements datés publiés par le répartiteur.
- **En place** : métrologie des services et règles d'alerte, dont le retrait du filtre VPN par son garde-fou ; alertes filtrées (avertissements et critiques, un message par problème, avis de résolution) envoyées à l'administrateur hors de la plateforme ; copie vers le répartiteur, qui les journalise (voir [Observabilité](concepts/10-observabilite.md)).
- **Cible** : historisation brute des échanges dans Git, pour l'audit, le rejeu et le sourçage ; registre durable des incidents et workflow « incident » ; métrologie sur volume persistant (15 jours en mémoire du pod aujourd'hui).

---

## Améliorations prévues

- filtre anti-fuite (DLP) avant toute sortie vers un modèle extérieur ;
- Tribunal Sémantique avant toute mémorisation venue du web ;
- refus par défaut dans `sophia-memory` ; règle réseau d'administration et admission des images dans `sophia-sandbox` ;
- contrôle des sorties du namespace des agents ;
- restriction du port interne du fournisseur d'identité aux namespaces clients ;
- accès aux applications par le cockpit seul, exception pour l'administrateur ;
- veille des mises à jour et des failles des images figées (scanner local, demandes de mise à jour ouvertes sans fusion automatique, rapport à l'administrateur) ;
- sauvegardes planifiées et chiffrées, avec essai de restauration ;
- double authentification pour les comptes d'administration et les responsables ;
- TLS mutuel entre le répartiteur et les exécutants ;
- volumes chiffrés.
