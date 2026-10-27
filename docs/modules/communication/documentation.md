# Module Communication — documentation

État : **installé, en recette**. Les deux services tournent dans l'installation de référence, contrôlés en lecture ; une première connexion au chat a créé un salon, et un premier passage par la visio a été vu dans le journal de l'adaptateur. La recette avec les appareils du foyer reste à faire (voir [Recette à faire](#recette-à-faire)).

## Ce que fait le module

- **Chat permanent** : des salons entre les membres du foyer, sur le navigateur (Element Web) et sur les téléphones et tablettes (clients Matrix). Les messages et les fichiers restent sur le serveur de la maison.
- **Visio** : une salle de visio s'ouvre par un lien, posé par exemple dans un salon du chat ; seuls les comptes admis du foyer la rejoignent.
- **Notifications** sur Android, par un relais local, sans service de notification d'un tiers.

## Architecture

```
navigateur, client Matrix (VPN) ──► routeur d'entrée ──► Element Web
                                                    ├──► Synapse ──► PostgreSQL 18 (base synapse)
                                                    │        └──► ntfy (notifications)
                                                    └──► MAS ──► fournisseur d'identité (OIDC, PKCE) ; PostgreSQL 18 (base mas)

navigateur, application Jitsi (VPN) ──► routeur d'entrée ──► web Jitsi ──► Prosody ◄── Jicofo
                                    └──► adaptateur ──► fournisseur d'identité (OIDC) → jeton de salle
média (UDP, VPN seulement) ──► ${VPN_IP}:${JVB_UDP_PORT} ──► JVB
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
| Notifications | **ntfy** dans le même namespace, en UnifiedPush : la notification ne porte ni le texte ni l'expéditeur ; Synapse ne sort que vers MAS et ntfy | aucune passerelle de notification d'un tiers |
| Client web | Element Web, configuration sans adresse externe | servi par la plateforme |

### Visio : Jitsi Meet

Jitsi Meet a remplacé la visio de La Suite numérique, d'abord prévue : son interface ne démarre pas sur les tablettes anciennes du foyer, alors que l'application mobile de Jitsi les accepte (iOS 15.1 au moins).

| Élément | Choix | Raison |
|---|---|---|
| Composants | web, Prosody, Jicofo, JVB (le pont média) ; ni base ni cache | le moins de pièces possible |
| Accès | un **adaptateur** maison (Python, bibliothèque standard seule) fait la connexion OIDC au fournisseur d'identité et rend un **jeton signé de 10 minutes, valable pour une seule salle** ; l'invité est refusé par le fournisseur d'identité, et par l'adaptateur s'il passait ; états liés au navigateur et à usage unique ; le journal de l'adaptateur ne contient ni la chaîne de requête ni de secret | Jitsi n'accepte qu'un jeton : l'adaptateur le délivre aux seuls comptes admis |
| Média | **un seul port UDP**, exposé par une `externalIP` sur l'adresse VPN du nœud (`${VPN_IP}:${JVB_UDP_PORT}`), relayé par une règle de la table nftables du VPN ; **pas de NodePort** | le média n'est joignable que par le VPN, jamais depuis le réseau local ; le pont voit l'adresse VPN réelle des appareils |
| Réseau | pair-à-pair et STUN coupés ; requêtes vers des tiers coupées ; candidats d'adresses privées non annoncés ; canal de pont par le canal de données SCTP | tout passe par le pont de la maison ; rien ne part vers un service extérieur |
| UID arbitraire d'OKD | les images Jitsi utilisent s6-overlay, qui refuse un `/run` appartenant à root ; la variable `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` le lui fait accepter | **ni privilège, ni `anyuid`** |
| Sondes | Jicofo n'écoute son API de santé que sur `127.0.0.1` : sonde en `exec` | l'écoute n'est pas élargie pour la sonde |
| Chiffrement | pas de chiffrement de bout en bout | le pont de la maison voit le média, comme tout pont de visio |

## Clients

| Appareil | Chat | Visio |
|---|---|---|
| Ordinateur | navigateur (Element Web) | navigateur |
| Android | Element X, notifications par ntfy | application Jitsi Meet |
| Tablette ancienne (iOS 15) | Element classique | application Jitsi Meet |

La **première connexion** au chat passe par deux pages de MAS : la liaison du compte, puis l'autorisation de l'application. L'application mobile de Jitsi se règle sur chaque appareil : adresse du serveur de la maison, rapports de plantage coupés, pair-à-pair coupé.

## Confidentialité et limites

- **Maison seule** : chat et visio ne se joignent que par le VPN.
- **Pas de chiffrement de bout en bout**, ni dans le chat (par défaut) ni dans la visio : l'administrateur du système peut lire les salons. Aucun salon n'est donc « intime ».
- **Médias du chat sans sauvegarde.**
- **Application mobile de Jitsi** : elle envoie des mesures d'usage à un service tiers (pas le contenu des visios) ; accepté en connaissance de cause, faute d'autre client compatible avec les tablettes anciennes.
- **Pas d'agent** dans les salons pour l'instant ; le chat ne reçoit pas les alertes de la plateforme (elles ont leur propre canal, voir [Observabilité](../../concepts/10-observabilite.md)).
- **Adaptateur** : un appareil du VPN peut épuiser sa réserve d'états en mémoire et bloquer les connexions à la visio pendant 10 minutes.

## Recette à faire

- visio à trois appareils au moins, et compteur de la règle UDP du VPN qui augmente ;
- invité refusé (chat et visio), compte protégé admis ;
- Element classique sur tablette ancienne, Element X avec ntfy sur Android, application Jitsi ;
- message envoyé dans un salon, sans chiffrement.

## Prévu

- **Courrier unifié** : prévu, en préparation ; non ouvert.
- **Lancer une visio depuis la discussion de Sophia**, et Sophia dans les salons : plus tard, avec les agents.

## Leçons

- Un essai local « sous UID arbitraire » doit aussi reproduire la **propriété des volumes** : sous OKD, un `emptyDir` appartient à root, ce que l'essai local ne montrait pas.
- Un service exposé par `externalIP` sur l'adresse VPN, plutôt que par NodePort, reste injoignable depuis le réseau local et voit la vraie adresse du client.
- Une condition de flux d'authentification niée se règle par une clé de négation propre à la condition : à vérifier en essai, invité compris.
