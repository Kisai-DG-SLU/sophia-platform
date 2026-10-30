# Module Communication — documentation

État : **en service, en recette**. Les deux services tournent dans l'installation de référence, contrôlés en lecture ; une première connexion au chat a créé un salon, et un premier passage par la visio a été vu dans le journal de l'adaptateur. Messages et Visio sont affichables dans le cockpit de l'interface, et le module de résumé des non-lus est chargé dans Synapse. La recette avec les appareils du foyer reste à faire (voir [Recette à faire](#recette-à-faire)).

## Ce que fait le module

- **Chat permanent** : des salons entre les membres du foyer, sur le navigateur (Element Web) et sur les téléphones et tablettes (clients Matrix). Les messages et les fichiers restent sur le serveur de la maison.
- **Visio** : une salle de visio s'ouvre par un lien, posé par exemple dans un salon du chat ; seuls les comptes admis du foyer la rejoignent.
- **Notifications** sur Android, par un relais local, sans service de notification d'un tiers.
- **Dans le cockpit** : Messages (Element) et Visio s'affichent au centre du [cockpit de l'interface](../../../deploy/okd/apps/chat-interface/README.md), et le volet « Quoi de neuf ? » pourra compter les messages non lus de chacun.

## Architecture

```
navigateur, client Matrix (VPN) ──► routeur d'entrée ──► Element Web
                                                    ├──► Synapse ──► PostgreSQL 18 (base synapse)
                                                    │        └──► ntfy (notifications)
                                                    └──► MAS ──► fournisseur d'identité (OIDC, PKCE) ; PostgreSQL 18 (base mas)

navigateur seulement (VPN) ──► routeur d'entrée ──► web Jitsi ──► Prosody ◄── Jicofo
                            └──► adaptateur ──► fournisseur d'identité (OIDC) → jeton de salle
média (UDP, VPN seulement) ──► ${VPN_IP}:${JVB_UDP_PORT} ──► JVB

serveur de l'interface ──► Synapse, port HTTP (module de résumé) ──► clés publiques du realm (par le routeur)
```

| Élément | Choix | Raison |
|---|---|---|
| Namespaces | deux namespaces dédiés, `sophia-messagerie` (chat) et `sophia-visio` (visio), chacun avec quota, LimitRange, EgressFirewall, refus par défaut en entrée et en sortie, DNS ; **aucune liaison de rôle vers un agent** | la bureautique n'avait plus la place dans son quota ; isoler le chat et la visio de tout le reste |
| Priorité | classe de la bureautique pour tous les pods, **sauf le pont média de la visio**, dans la classe de la voix ([priorités](../../../deploy/okd/cluster/README.md)) | le média d'une visio en cours ne doit pas attendre derrière un travail de fond |
| Images | figées par empreinte ; Synapse 1.163.2, Jitsi `stable-11248-2` | une mise à jour est une décision |

### Chat permanent : Matrix

| Élément | Choix | Raison |
|---|---|---|
| Serveur | Synapse, base `synapse` sur PostgreSQL 18 partagé (collation `C`, exigée par Synapse) | la base commune de la plateforme ; une base et un rôle propres, les accès croisés refusés |
| Connexion | **MAS** (Matrix Authentication Service) délègue l'authentification au fournisseur d'identité de la plateforme (OIDC, PKCE) ; base `mas` propre | connexion unique, aucun mot de passe Matrix ; MAS est le chemin d'authentification actuel de Matrix |
| Accès | réservé aux groupes du foyer : un rôle de client dans le fournisseur d'identité, et un flux de connexion qui **refuse le groupe des invités** | MAS ne filtre pas par groupe : le refus se fait avant, chez le fournisseur d'identité |
| Fédération | **coupée** | le serveur ne parle à aucun autre serveur Matrix ; rien ne sort |
| Chiffrement de bout en bout | **coupé par défaut** pour les nouveaux salons (réglage servi aux clients par le serveur) | choix du foyer. **Conséquence assumée** : l'administrateur du serveur peut lire les salons |
| Médias | 50 Mo au plus par fichier ; volume logique dédié de 10 Gio, PV `Retain` ; **sans sauvegarde** | une perte des médias est acceptée ; les messages sont dans la base |
| Notifications | **ntfy** dans le même namespace, en UnifiedPush : la notification ne porte ni le texte ni l'expéditeur ; Synapse ne sort que vers MAS, ntfy et le nom public du fournisseur d'identité (clés publiques, pour le module de résumé) | aucune passerelle de notification d'un tiers |
| Client web | Element Web, configuration sans adresse externe ; affichable par le seul chat de la plateforme (`frame-ancestors`) | servi par la plateforme ; sans cet en-tête, Element était affichable par n'importe quelle page |
| Résumé des non-lus | un **module Python monté dans Synapse** expose une route de résumé pour le volet « Quoi de neuf ? » de l'interface (voir ci-dessous) | compte exact par la fonction même de Synapse, aucun secret nouveau |

#### Résumé des non-lus pour l'interface

Synapse n'accepte que les jetons de MAS : le serveur de l'interface ne peut pas lui demander les non-lus d'une personne avec le jeton qu'il relaie. Trois voies ont été pesées : un accès d'administration à MAS (compte exact, mais un secret qui peut tout faire dans MAS), la lecture directe de la base de Synapse (refaire son calcul, fragile aux mises à jour), ou un module dans Synapse. Choix : **le module**.

- **Le module vérifie lui-même le jeton relayé** : signature par les clés publiques du realm, émetteur, dates, **audience personnalisée** propre à cette route (posée par un mappeur sur le client de l'interface, sans client du fournisseur d'identité, puisque rien n'est introspecté ni échangé), client d'origine (l'interface) et groupes du foyer : les invités sont exclus.
- **Ce qu'il rend** : un compte par salon non lu, mentions en tête ; **jamais un texte ni un expéditeur**. `no-store`.
- **Erreurs** : 401 pour un jeton refusé, 503 pour toute autre erreur ; Synapse démarre même si le module est en panne. **Retrait en une ligne** de configuration.
- **Mise à jour de Synapse** : le module appelle une fonction interne de Synapse ; un test échoue si sa signature change, à relancer avant chaque mise à jour.
- **Condition** : le compte Matrix est trouvé par l'identifiant de la personne chez le fournisseur d'identité : **un identifiant ne doit jamais passer d'une personne à une autre**.
- **Réseau** : entrée de Synapse depuis le pod de l'interface, sur son port HTTP. La route reste aussi joignable par l'adresse publique de Synapse, dans le VPN : c'est le jeton qui la garde.

État : module chargé, route qui répond 401 sans jeton ; sortie de l'interface vers Synapse ouverte ; l'appel par l'interface n'est pas encore codé (prévu).

### Visio : Jitsi Meet

Jitsi Meet a remplacé la visio de La Suite numérique, d'abord prévue : son interface ne démarre pas sur les tablettes anciennes du foyer, alors que l'application mobile de Jitsi les acceptait (iOS 15.1 au moins).

**La visio passe désormais par le navigateur seulement**, donc par le cockpit de l'interface (décision du foyer) : `DISABLE_DEEP_LINKING` retire la page « Rejoindre dans l'application », et l'application mobile n'est plus utilisée. Conséquence : la visio dans le navigateur de la tablette ancienne (Safari 15) **n'est pas encore éprouvée** ; elle est à l'étape de recette.

| Élément | Choix | Raison |
|---|---|---|
| Composants | web, Prosody, Jicofo, JVB (le pont média) ; ni base ni cache | le moins de pièces possible |
| Accès | un **adaptateur** maison (Python, bibliothèque standard seule) fait la connexion OIDC au fournisseur d'identité et rend un **jeton signé de 10 minutes, valable pour une seule salle** ; l'invité est refusé par le fournisseur d'identité, et par l'adaptateur s'il passait ; états liés au navigateur et à usage unique ; le journal de l'adaptateur ne contient ni la chaîne de requête ni de secret | Jitsi n'accepte qu'un jeton : l'adaptateur le délivre aux seuls comptes admis |
| Média | **un seul port UDP**, exposé par une `externalIP` sur l'adresse VPN du nœud (`${VPN_IP}:${JVB_UDP_PORT}`), relayé par une règle de la table nftables du VPN ; **pas de NodePort** | le média n'est joignable que par le VPN, jamais depuis le réseau local ; le pont voit l'adresse VPN réelle des appareils |
| Réseau | pair-à-pair et STUN coupés ; requêtes vers des tiers coupées ; candidats d'adresses privées non annoncés ; canal de pont par le canal de données SCTP | tout passe par le pont de la maison ; rien ne part vers un service extérieur |
| UID arbitraire d'OKD | les images Jitsi utilisent s6-overlay, qui refuse un `/run` appartenant à root ; la variable `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` le lui fait accepter | **ni privilège, ni `anyuid`** |
| Sondes | Jicofo n'écoute son API de santé que sur `127.0.0.1` : sonde en `exec` | l'écoute n'est pas élargie pour la sonde |
| Chiffrement | pas de chiffrement de bout en bout | le pont de la maison voit le média, comme tout pont de visio |
| Affichage | affichable par le seul chat de la plateforme (`frame-ancestors` dans `CSP_HEADER`) ; caméra et micro autorisés par l'attribut `allow` du cadre, pour la visio seulement | la visio vit dans le cockpit |

## Clients

| Appareil | Chat | Visio |
|---|---|---|
| Ordinateur | navigateur (Element Web) | navigateur |
| Android | Element X, notifications par ntfy ; Element Web dans le cockpit | navigateur, dans le cockpit |
| Tablette ancienne (iOS 15) | Element classique | navigateur, dans le cockpit : à éprouver |

La **première connexion** au chat passe par deux pages de MAS : la liaison du compte, puis l'autorisation de l'application. Dans le cockpit, la page de connexion de MAS est refusée en cadre : si la session Matrix a expiré, « Se reconnecter » ouvre Element dans un onglet, puis on revient au cockpit.

**Element Web n'est pas pris en charge par Safari 15** : sur la tablette ancienne, le module Messages du cockpit ne marche donc pas tel quel. Options, à trancher après l'essai sur l'appareil : garder Element classique sur cette tablette (recommandé), un client Matrix web plus léger, ou une vue des messages faite par l'interface elle-même.

## Confidentialité et limites

- **Maison seule** : chat et visio ne se joignent que par le VPN.
- **Pas de chiffrement de bout en bout**, ni dans le chat (par défaut) ni dans la visio : l'administrateur du système peut lire les salons. Aucun salon n'est donc « intime ».
- **Médias du chat sans sauvegarde.**
- **Visio par le navigateur seulement** : l'application mobile de Jitsi, qui envoyait des mesures d'usage à un service tiers, n'est plus utilisée.
- **Résumé des non-lus** : la route n'expose que des comptes, jamais un texte ni un expéditeur, et seulement à la personne elle-même, par son jeton.
- **Pas d'agent** dans les salons pour l'instant ; le chat ne reçoit pas les alertes de la plateforme (elles ont leur propre canal, voir [Observabilité](../../concepts/10-observabilite.md)).
- **Adaptateur** : un appareil du VPN peut épuiser sa réserve d'états en mémoire et bloquer les connexions à la visio pendant 10 minutes.

## Recette à faire

- visio à trois appareils au moins, et compteur de la règle UDP du VPN qui augmente ;
- invité refusé (chat et visio), compte protégé admis ;
- Element classique sur tablette ancienne, Element X avec ntfy sur Android ;
- visio dans le navigateur sous Android, sans page « Rejoindre dans l'application » ; visio et Element Web dans le navigateur de la tablette ancienne ;
- Element dans le cockpit : session conservée, un message envoyé ;
- message envoyé dans un salon, sans chiffrement ;
- résumé des non-lus avec un vrai jeton relayé, quand l'interface l'appellera.

## Prévu

- **Courrier unifié** : décidé, **reporté** derrière les autres projets ; rien n'est ouvert au foyer.
- **Accès par le cockpit seulement**, une fois le cockpit validé sur tous les appareils : une page de l'application ouverte directement sera renvoyée vers le cockpit ; les clients natifs du chat ne sont pas concernés ; un accès direct reste à l'administrateur, pour le dépannage.
- **Lancer une visio depuis la discussion de Sophia**, et Sophia dans les salons : plus tard, avec les agents.

## Leçons

- Un essai local « sous UID arbitraire » doit aussi reproduire la **propriété des volumes** : sous OKD, un `emptyDir` appartient à root, ce que l'essai local ne montrait pas.
- Un service exposé par `externalIP` sur l'adresse VPN, plutôt que par NodePort, reste injoignable depuis le réseau local et voit la vraie adresse du client.
- Une condition de flux d'authentification niée se règle par une clé de négation propre à la condition : à vérifier en essai, invité compris.
- Un `add_header` dans une `location` de nginx annule ceux du niveau supérieur : l'en-tête `frame-ancestors` d'Element est répété dans chaque location.
