# Module Communication — documentation

État : **en service, en recette**. Le chat (Matrix) et la visio tournent dans l'installation de référence, contrôlés en lecture, et s'affichent dans le dashboard de l'interface. La **première visio avec image** entre un ordinateur et la tablette ancienne a eu lieu dans le dashboard, par le VPN, après trois correctifs en chaîne (voir [Média de la visio](#média-de-la-visio--trois-causes-en-chaîne)). **La messagerie a changé de logiciel** : après un essai sur la vraie tablette, le foyer a retenu **Converse.js et Prosody (XMPP) à la place de Matrix**. La version définitive est **en service**, dans le dashboard, avec « dis à » (Sophia envoie un message au nom de la personne) ; Matrix reste lisible jusqu'à la fin de la recette (voir [Messagerie : de Matrix à XMPP](#messagerie--de-matrix-à-xmpp)). La **recette avec tous les appareils du foyer est en cours** (voir [Recette à faire](#recette-à-faire)).

## Ce que fait le module

- **Chat permanent** : des salons et des discussions directes entre les membres du foyer, dans le navigateur et dans le dashboard. Les messages et les fichiers restent sur le serveur de la maison. Converse.js et Prosody (XMPP) depuis la version définitive ; Matrix (Element) reste lisible jusqu'à la fin de la recette, puis il est démonté.
- **« Dis à »** : on demande à Sophia d'écrire à un membre de la famille ou au salon Famille ; après confirmation, le message part dans la messagerie, au nom de la personne, avec la mention « via Sophia ».
- **Visio** : une salle de visio s'ouvre dans le dashboard ou par un lien ; seuls les comptes admis du foyer la rejoignent.
- **Notifications** sur Android, par un relais local (ntfy), sans service de notification d'un tiers et sans contenu : « Nouveau message », ni texte ni expéditeur.
- **Dans le dashboard** : Messages et Visio s'affichent au centre du [dashboard de l'interface](../../../deploy/okd/apps/chat-interface/README.md), et le volet « Quoi de neuf ? » compte les messages non lus de chacun (en service, vérifié) ; un volet « Demander à Sophia » y est offert, sans lire les messages.

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

navigateur, dashboard (VPN) ──► routeur d'entrée ──► web : oauth2-proxy + nginx (Converse.js) ──► Prosody (WebSocket, fichiers)
                                                                                    └──► passerelle de push ──► ntfy
serveur de l'interface ──► relais « dis à » (une route, un port) ──► Prosody (module HTTP) ──► userinfo du fournisseur d'identité
```

| Élément | Choix | Raison |
|---|---|---|
| Namespaces | deux namespaces dédiés, `sophia-messagerie` (chat) et `sophia-visio` (visio), chacun avec quota, LimitRange, EgressFirewall, refus par défaut en entrée et en sortie, DNS ; **aucune liaison de rôle vers un agent** | la bureautique n'avait plus la place dans son quota ; isoler le chat et la visio de tout le reste |
| Priorité | classe de la bureautique pour tous les pods, **sauf le pont média de la visio**, dans la classe de la voix ([priorités](../../../deploy/okd/cluster/README.md)) | le média d'une visio en cours ne doit pas attendre derrière un travail de fond |
| Images | figées par empreinte ; Synapse 1.163.2, Jitsi `stable-11248-2` | une mise à jour est une décision |

### Chat permanent : Matrix (en service, à remplacer)

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

État : module chargé, route qui répond 401 sans jeton ; sortie de l'interface vers Synapse ouverte ; appelée par l'interface pour « Quoi de neuf ? » : en service, vérifiée. Il disparaîtra avec Matrix ; la messagerie XMPP aura son propre résumé.

### Messagerie : de Matrix à XMPP

**Décision du foyer, ferme après l'essai sur la vraie tablette** : Converse.js (client web) et Prosody (serveur XMPP) remplacent Matrix pour la messagerie de la famille.

**Pourquoi.** Les critères ont été vérifiés dans l'ordre : fonctionner sur la tablette ancienne (Safari 15), compte unique du fournisseur d'identité, aucune sortie réseau qu'on ne puisse couper, notifications, projet vivant. Element Web ne démarre pas sous Safari 15, et les clients Matrix web plus légers échouent aussi : page blanche (expressions régulières en lookbehind), ou projet arrêté. Converse.js tient sur la tablette ancienne, une fois retirés les logos chargés depuis son site ; il est maintenu, et Prosody suit ses correctifs de sécurité. **Risque assumé** : le module de Prosody qui valide un jeton OIDC est un module communautaire, au stade alpha.

**Essai** (namespace jetable, supprimé en bloc à la fin) :

| Élément | Choix | Raison |
|---|---|---|
| Socle | quota, refus par défaut, EgressFirewall limité au cluster ; Prosody sur un volume éphémère | un essai ne laisse rien derrière lui |
| Pod web | nginx et oauth2-proxy (en boucle locale) ; accès réservé à un **groupe d'essai dédié** et à un client OIDC dédié | l'essai ne touche aucun compte hors du groupe |
| Jeton | une route `/credentials` remet au client le jeton d'accès de la session, filtré | Converse.js se connecte sans mot de passe XMPP |
| Prosody | 13.0.7, SASL OAUTHBEARER ; le jeton est validé par l'userinfo du fournisseur d'identité ; le nom du compte XMPP vient de l'userinfo (`preferred_username`), jamais du client ; ni mot de passe XMPP, ni serveur à serveur, ni client en TCP | pas d'usurpation par le nom ; seul le WebSocket est ouvert |
| WebSocket et fichiers | `auth_request` d'oauth2-proxy sur `/xmpp-websocket` et `/file_share/` : sans session, 401 | Prosody accepte **tout** jeton valide du realm (l'userinfo ne vérifie ni le client, ni l'audience, ni le groupe) : sans ce contrôle, un jeton d'une autre application ouvrait la messagerie d'essai |
| Fichiers partagés | `proxy_buffering off` sur `/file_share/` | nginx mettait les fichiers lus en tampon dans un `/tmp` éphémère de 64 Mi : deux lectures d'une vidéo faisaient évincer le pod |
| Noms de Service | **noms complets** en `.svc.cluster.local` | Prosody résout par libunbound, qui n'applique pas les domaines de recherche : un nom court répondait NXDOMAIN, et l'appel userinfo de Prosody, sans délai réglable, restait suspendu |
| Tuile du dashboard | visible des seuls membres du groupe d'essai (`SOPHIA_ESSAI_GROUPES`) ; le vrai contrôle reste l'oauth2-proxy de la page | masquer n'est pas un contrôle |

**Ce qui marche sur la tablette ancienne** : délai d'arrivée, « écrit… », photos dans les deux sens, clavier, rotation, retour après 5 minutes, connexion au-delà de la vie du jeton (renouvelé), discussion directe, salon, retrait d'un membre (`/revoke`).

**Défauts trouvés**, à corriger dans la version définitive (réglage, petit greffon ou retour forcé au dashboard) :

- **pas de barre de mise en forme** : la mise en forme existe (XEP-0393 : `*gras*`, `_italique_`, code entre accents graves), mais se tape à la main ;
- **membre affiché deux fois** dans un salon : occupant présent et entrée de la liste des membres, non fusionnés ;
- **salon resté dans la liste** d'un membre retiré : le signet posé à l'entrée dans le salon n'est pas retiré par `/revoke` ;
- **fenêtre d'invitation non fermée** dans l'autre session du même compte, qui réapparaît comme une nouvelle invitation ;
- **double session** : l'onglet de connexion charge la messagerie au lieu de renvoyer au dashboard ;
- **aucun annuaire** : on ne voit un membre de la famille qu'après l'avoir ajouté par son adresse ;
- lien vers la visio depuis une discussion : le greffon prévu ne marche pas avec la version 14 du client.

#### Messagerie définitive (en service)

Dans le namespace de la messagerie, à côté de Matrix, jusqu'à la fin de la recette :

| Élément | Choix | Raison |
|---|---|---|
| Prosody | 13.0.7, image figée par empreinte ; données sur un **volume local persistant** (`Retain`) ; archives des salons gardées | la messagerie est la mémoire écrite du foyer |
| Comptes | identité tirée de l'userinfo du jeton (OAUTHBEARER, `preferred_username`), jamais d'un mot de passe ; un module de Prosody refuse à la connexion **tout compte hors des groupes du foyer**, en plus de l'oauth2-proxy de la page | le contrôle par groupe ne dépend pas d'une seule couche |
| Ouvertures | ni serveur à serveur, ni inscription, ni client en TCP : le WebSocket seul, derrière oauth2-proxy ; NetworkPolicy fermées, Prosody joignable du seul pod web (et du relais « dis à ») | rien n'entre ni ne sort hors du chemin prévu |
| Web | nginx (Converse.js 14, servi par l'image, empreinte vérifiée ; greffons du foyer) et oauth2-proxy ; politique de sécurité du contenu stricte, affichable dans le **seul dashboard** ; fichiers partagés servis en `sandbox` et `nosniff` | aucune ressource tierce ; un fichier reçu ne peut pas s'exécuter dans la page |
| Contacts | **rien d'office** : chacun ajoute ses contacts par leur adresse, ou passe par le salon Famille | choix du foyer |
| Salon « Famille » | créé d'office pour toute la maison, invités exclus ; **propriétaires : les adultes** ; membre d'office, sans départ volontaire ; un enfant peut créer d'autres salons ; les membres absents ne sont visibles que des propriétaires | un lieu commun garanti, administré par les adultes |
| Historique de Matrix | **non repris** ; Element reste lisible jusqu'à la fin de la recette | une reprise coûtait plus qu'elle ne rapportait |
| Notifications | Android : passerelle de push (XEP-0357) dans le pod de Prosody, vers ntfy ; « Nouveau message », **ni texte ni expéditeur**, lien vers le dashboard ; un sujet par personne, tiré d'une clé secrète, montré à elle seule. Tablette iOS : pastille dans le dashboard, une fois Messages ouvert | aucun contenu ne quitte la messagerie ; pas de service tiers |
| Visio depuis une discussion | bouton qui ouvre la **tuile Visio du dashboard** sur la salle de la discussion ; nom de salle par règle fixe (salon Famille → `famille`, autre salon → tiré de son adresse, discussion à deux → tiré de la paire d'identifiants, condensée) ; la tuile Visio ouvre `famille` par défaut | la visio individuelle passe par la discussion à deux |
| Ressources | web en stratégie `Recreate`, limites dans le quota du namespace | un quota serré ne doit pas bloquer une mise à jour |

**Mise en service** : prérequis (volume, client OIDC et Secret, entrée réseau du fournisseur d'identité), contrôle des groupes du foyer, Secret de la passerelle, images, réglage de ntfy, essai à blanc, application, contrôles HTTP (`/sante` 200 ; jeton, push et WebSocket en 401 sans session ; déconnexion en 302 avec `Clear-Site-Data`), premier essai hors du dashboard, puis tuile du dashboard. Banc local par le chemin de production : 25 étapes.

**Départ d'un membre** : le retirer des groupes du foyer (oauth2-proxy et Prosody refusent toute nouvelle connexion), puis du salon Famille (`/revoke`), puis supprimer son compte Prosody, qui garde sinon son ancien statut jusqu'à sa prochaine connexion.

#### « Dis à » : Sophia écrit au nom de la personne

Dans la discussion avec Sophia, « dis à papa que… » ou « dis à tout le monde que… » : Sophia propose le message, la personne confirme, et le message part **dans la messagerie**, au nom de la personne, vers la discussion à deux ou le salon Famille. Il remplace l'ancien dépôt de messages du chat, retiré.

| Élément | Choix | Raison |
|---|---|---|
| Envoi | un **module HTTP de Prosody** (`POST`, corps de 4 Ko au plus) | le message est un vrai message XMPP, archivé et notifié comme les autres |
| Identité | le chat relaie le **jeton d'accès de la personne** ; Prosody le vérifie par l'userinfo, puis exige le bon client émetteur (`azp`), un groupe du foyer et le **même nom** que le compte ; l'expéditeur est **le compte du jeton**, jamais un champ du corps | personne ne peut écrire au nom d'un autre, pas même le chat |
| Isolement | un **relais** dans le pod de la passerelle n'ouvre au chat qu'**une route et un port** ; le chat n'atteint jamais le port HTTP de Prosody (WebSocket, fichiers) | Prosody ne sait pas réserver un chemin à une source |
| Affichage | mention « **via Sophia** » sous le message (greffon de Converse.js) ; **pas modifiable** (« Éditer » ôté), mais **retirable** par son expéditeur | on sait ce que Sophia a écrit, et on peut le reprendre |
| Limites | **30 messages par jour** et par personne ; journal sans texte | pas d'emballement |
| Sans réglage | sans l'adresse du relais dans le manifeste du chat, « dis à » répond qu'il n'est pas encore ouvert | mise en service en deux temps sans erreur visible |

Choix d'usage : l'analyse de l'intention par le modèle, la confirmation, l'envoi par une règle ; une réponse autre que « oui » n'envoie rien.

### Visio : Jitsi Meet### Visio : Jitsi Meet

Jitsi Meet a remplacé la visio de La Suite numérique, d'abord prévue : son interface ne démarre pas sur les tablettes anciennes du foyer.

**La visio passe par le navigateur seulement**, donc par le dashboard de l'interface (décision du foyer) : `DISABLE_DEEP_LINKING` retire la page « Rejoindre dans l'application », et l'application mobile n'est plus utilisée. La visio dans le navigateur de la tablette ancienne **marche** depuis le réglage de son profil VPN (ci-dessous).

| Élément | Choix | Raison |
|---|---|---|
| Composants | web, Prosody, Jicofo, JVB (le pont média) ; ni base ni cache | le moins de pièces possible |
| Accès | un **adaptateur** maison (Python, bibliothèque standard seule) fait la connexion OIDC au fournisseur d'identité et rend un **jeton signé de 10 minutes, valable pour une seule salle** ; l'invité est refusé par le fournisseur d'identité, et par l'adaptateur s'il passait ; états liés au navigateur et à usage unique ; le journal de l'adaptateur ne contient ni la chaîne de requête ni de secret | Jitsi n'accepte qu'un jeton : l'adaptateur le délivre aux seuls comptes admis |
| Connexion dans le dashboard | **en fenêtre** (`tokenAuthInline`, mécanisme natif de Jitsi), voir ci-dessous | le fournisseur d'identité refuse d'être affiché dans un cadre |
| Média | **un seul port UDP**, exposé par une `externalIP` sur l'adresse VPN du nœud (`${VPN_IP}:${JVB_UDP_PORT}`) ; **pas de NodePort** | le média n'est joignable que par le VPN, jamais depuis le réseau local |
| Réseau | pair-à-pair et STUN coupés ; requêtes vers des tiers coupées ; **candidats d'adresses privées annoncés** (l'adresse VPN en est une) ; canal de pont par le canal de données SCTP | tout passe par le pont de la maison ; rien ne part vers un service extérieur |
| Entrée du média | la NetworkPolicy du pont admet le réseau du VPN **et le groupe `host-network`** sur le port UDP | dans la passerelle partagée d'OVN-Kubernetes, le trafic d'une externalIP arrive au pod avec une source réécrite (voir ci-dessous) |
| UID arbitraire d'OKD | les images Jitsi utilisent s6-overlay, qui refuse un `/run` appartenant à root ; la variable `S6_YES_I_WANT_A_WORLD_WRITABLE_RUN_BECAUSE_KUBERNETES=1` le lui fait accepter | **ni privilège, ni `anyuid`** |
| Sondes | Jicofo n'écoute son API de santé que sur `127.0.0.1` : sonde en `exec` | l'écoute n'est pas élargie pour la sonde |
| Chiffrement | pas de chiffrement de bout en bout | le pont de la maison voit le média, comme tout pont de visio |
| Affichage | affichable par le seul chat de la plateforme (`frame-ancestors` dans `CSP_HEADER`) ; caméra et micro autorisés par l'attribut `allow` du cadre, pour la visio seulement | la visio vit dans le dashboard |

#### Connexion en fenêtre

Quand la visio est passée dans un cadre du dashboard, l'entrée en salle a cessé de marcher : la connexion OIDC se faisait dans le cadre, et le fournisseur d'identité refuse d'y être affiché (« contenu bloqué » sur un ordinateur, rien sur la tablette). On avait vérifié l'affichage dans le cadre, pas l'entrée dans une salle. Décision du foyer : la visio reste dans le dashboard, **seule la connexion passe par une fenêtre**, qui revient à la tuile. Jitsi a ce parcours (`tokenAuthInline`) ; rien n'est ajouté au dashboard.

- Un petit script de configuration, actif **dans un cadre seulement**, active `tokenAuthInline` et ajoute `fenetre=1` à l'adresse de l'adaptateur. Hors cadre, le parcours par redirection reste tel quel.
- En mode fenêtre, l'adaptateur exige un `nonce` de forme fermée (64 caractères hexadécimaux, contrôle exact de toute la chaîne) et le garde dans l'état.
- Au retour du fournisseur d'identité, il sert une **page de retour** (`no-store`, `no-referrer`, CSP sans script en ligne, `frame-ancestors 'none'`) qui poste le jeton à `window.opener`, **vers la seule origine de la visio**, puis se ferme. Une page tierce ne reçoit rien ; un retour volé ou rejoué reçoit 400.
- Les contrôles d'avant restent : état lié au cookie et à usage unique, PKCE, userinfo, groupes.
- **Limites** : Jitsi ne vérifie pas le `nonce` à la réception (il ne sert qu'à reconnaître le mode) ; la protection tient à la cible du message, à l'état et à PKCE. Le jeton n'apparaît dans aucune adresse de page, mais Jitsi le met dans l'adresse de son WebSocket, dans les deux modes (masqué dans son journal).
- **Jeton expiré** : en mode fenêtre, le jeton reste dans l'état de Jitsi, qui ne contrôle son expiration qu'au rechargement ; l'entrée suivante était refusée. Le script de configuration le vide 30 s avant son expiration (action interne `SET_JWT`), pour que l'entrée suivante rouvre la fenêtre. Action interne : à revérifier à chaque montée de version.

#### Média de la visio : trois causes en chaîne

La conférence se montait (les participants entraient dans la salle), mais **aucun flux média ne s'était jamais établi** : les métriques du pont donnaient `ice_succeeded 0` depuis l'installation, et le pont expirait chaque participant au bout de 2 min 48. L'essai à plusieurs appareils avait été renvoyé à la recette, jamais faite. Trois causes se cachaient l'une derrière l'autre :

1. **Le pont n'annonçait pas son adresse.** `JVB_ADVERTISE_PRIVATE_CANDIDATES=false` retire des candidats annoncés toute adresse RFC 1918 ; or l'adresse VPN du nœud en est une. Le navigateur ne recevait aucun candidat. Preuve : l'état de débogage du pont (`advertisePrivateCandidates: false`, 0 paquet reçu ou émis). Correctif : `true`. L'adresse du pod est annoncée aussi, mais elle est injoignable et abandonnée par ICE.
2. **La NetworkPolicy refusait le média.** Le trafic de l'externalIP est bien traduit vers le pod, mais, en passerelle partagée d'OVN-Kubernetes, avec une **source réécrite** en `169.254.0.2` (masquerade de l'hôte). La politique n'admettait que le réseau du VPN : tout restait sans réponse (`[UNREPLIED]` dans la table de suivi des connexions du nœud). Correctif : admettre aussi le groupe `policy-group.network.openshift.io/host-network` sur le port UDP, comme la forge l'est par le groupe `ingress`. Conséquence : la NetworkPolicy ne peut pas filtrer ce trafic par appareil. L'ordinateur a alors établi son média.
3. **La tablette iOS n'envoyait pas son média dans le tunnel.** Son HTTPS passait par le VPN, mais aucun paquet UDP n'arrivait au nœud. Une page de diagnostic (liste des candidats ICE de l'appareil, requêtes STUN vers le pont, cherchées dans la table de suivi des connexions) l'a prouvé : seule l'adresse Wi-Fi figurait parmi les candidats. **Cause** : le WebRTC de WebKit sur iOS (Safari comme Chrome, qui utilise le même moteur) n'énumère que l'interface « par défaut », et libwebrtc la détermine en ouvrant une socket UDP vers `8.8.8.8` (sans rien envoyer). Avec `AllowedIPs` limité au réseau du VPN, cette interface est le Wi-Fi. **Correctif, dans le profil de l'appareil** : `AllowedIPs = ${VPN_NETWORK}, 8.8.8.8/32`. Le VPN devient l'interface « par défaut » pour WebRTC, et le reste d'Internet reste sur le Wi-Fi ou le réseau mobile. Voir le [profil des appareils iOS](../../../deploy/okd/host/wireguard/README.md#appareils-ios--la-visio-et-le-réseau-par-défaut).

Résultat : **première visio avec image** entre l'ordinateur et la tablette ancienne, dans le dashboard, par le VPN ; les deux participants ont ICE et DTLS établis. Les pistes écartées en route : une connexion directe entre appareils (coupée), un relais TURN en TCP (il aurait échoué pour la même raison que l'UDP), l'application mobile, ou un port sur le réseau local (contraires à « tout par le VPN, dans le dashboard »).

**Ce qui fait foi** : l'état de débogage du pont (`iceConnected`, paquets) et la table de suivi des connexions du nœud. Le compteur de la règle nftables du VPN n'est pas un contrôle : il est resté à zéro pendant une visio réussie.

## Clients

| Appareil | Chat | Visio |
|---|---|---|
| Ordinateur | Converse.js dans le dashboard | navigateur, dans le dashboard : **image et son établis** |
| Android | Converse.js dans le dashboard, notifications par l'application ntfy | navigateur, dans le dashboard : à éprouver (le profil VPN par défaut devrait suffire) |
| Tablette ancienne (iOS 15) | Converse.js dans le dashboard, pastille sans notification page fermée | navigateur, dans le dashboard : **image et son établis**, avec le profil VPN iOS |

Tant que Matrix reste lisible : la **première connexion** au chat Matrix passe par deux pages de MAS : la liaison du compte, puis l'autorisation de l'application. Dans le dashboard, la page de connexion de MAS est refusée en cadre : si la session Matrix a expiré, « Se reconnecter » ouvre Element dans un onglet, puis on revient au dashboard.

**Element Web n'est pas pris en charge par Safari 15** : c'est l'une des raisons du passage à Converse.js, qui y fonctionne. La pastille des non-lus n'apparaît qu'une fois Messages ouvert : la messagerie n'est pas chargée en arrière-plan à l'ouverture du dashboard, pour ménager la mémoire de la tablette ancienne.

## Confidentialité et limites

- **Maison seule** : chat et visio ne se joignent que par le VPN.
- **Pas de chiffrement de bout en bout**, ni dans le chat ni dans la visio : l'administrateur du système peut lire les salons. Aucun salon n'est donc « intime ».
- **Médias du chat sans sauvegarde.**
- **Salles de visio non privées entre membres du foyer** : le jeton de visio vaut pour toute salle, et le nom d'une salle à deux se recalcule ; un troisième membre du foyer pourrait y entrer, et serait vu. Les personnes hors du foyer sont refusées. Fermer cette limite demande des jetons limités à une salle : plus tard, à la demande.
- **Présence en veille** : après la fermeture de la page, la session reste en veille jusqu'à 72 h pour les notifications ; la personne paraît présente dans les salons pendant ce temps. Choix assumé du foyer.
- **Notifications** : qui connaîtrait le sujet ntfy d'une personne pourrait lui envoyer de fausses alertes ou voir quand elle en reçoit, jamais un contenu ; le sujet n'est montré qu'à elle.
- **Visio par le navigateur seulement** : l'application mobile de Jitsi, qui envoyait des mesures d'usage à un service tiers, n'est plus utilisée.
- **Résumé des non-lus** : la route n'expose que des comptes, jamais un texte ni un expéditeur, et seulement à la personne elle-même, par son jeton.
- **Déconnexion** : se déconnecter du dashboard ferme aussi les sessions des modules d'une liste fermée, messagerie comprise ; la déconnexion de la messagerie **efface les données du navigateur** (`Clear-Site-Data`, et une page sans session pour la tablette ancienne). Element garde son jeton dans le navigateur, hors de portée du dashboard : limite connue, levée avec le retrait de Matrix.
- **Pas d'agent** dans les salons pour l'instant ; le chat ne reçoit pas les alertes de la plateforme (elles ont leur propre canal, voir [Observabilité](../../concepts/10-observabilite.md)).
- **Adaptateur** : un appareil du VPN peut épuiser sa réserve d'états en mémoire et bloquer les connexions à la visio pendant 10 minutes.

## Recette à faire

- visio à trois appareils : chacun voit les deux autres, sortie puis retour sans recharger, partage d'écran depuis un ordinateur ;
- chaque appareil du foyer passé par la page de diagnostic des candidats, à la maison puis sur le réseau mobile (Android compris) ; la page est retirée ensuite ;
- invité refusé (chat et visio), compte protégé admis ;
- messagerie définitive sur chaque appareil (en cours) : ajout d'un contact par son adresse, salon Famille, notification Android sans contenu, visio depuis une discussion, déconnexion ; puis démontage de Matrix ;
- « dis à » depuis chaque appareil : envoi à deux et à tout le monde, mention « via Sophia », pas d'« Éditer », une réponse autre que « oui » n'envoie rien ;
- résumé des non-lus avec un vrai jeton relayé, dans « Quoi de neuf ? ».

## Prévu

- **Retrait de Matrix** (Synapse, MAS, Element, module de résumé) à la fin de la recette.
- **Boutons de visio directs** vers chaque membre, et salles privées par des jetons limités à une salle : plus tard, à la demande du foyer.
- **Courrier unifié** : décidé, **reporté** derrière les autres projets ; rien n'est ouvert au foyer.
- **Accès par le dashboard seulement**, une fois le dashboard validé sur tous les appareils : une page de l'application ouverte directement sera renvoyée vers le dashboard ; un accès direct reste à l'administrateur, pour le dépannage.
- **Lancer une visio depuis la discussion de Sophia**, et Sophia dans les salons : plus tard, avec les agents.

## Leçons

- Un essai local « sous UID arbitraire » doit aussi reproduire la **propriété des volumes** : sous OKD, un `emptyDir` appartient à root, ce que l'essai local ne montrait pas.
- Un service exposé par `externalIP` sur l'adresse VPN, plutôt que par NodePort, reste injoignable depuis le réseau local. Mais, en passerelle partagée d'OVN-Kubernetes, **le pod voit une source réécrite** (`169.254.0.2`), pas l'adresse de l'appareil : une NetworkPolicy en `ipBlock` du VPN le refuse, et ne peut pas filtrer par appareil.
- « Ne pas annoncer les candidats privés » retire aussi l'adresse VPN, qui est privée : sur un réseau privé, c'est la seule adresse utile.
- **WebRTC sur iOS ne suit pas les routes du VPN** comme le reste du système : il ne propose que l'interface par défaut, déterminée par la route vers `8.8.8.8`. Une page qui affiche les candidats ICE de l'appareil tranche en une minute ce que des heures de journaux n'ont pas tranché.
- Afficher une application dans un cadre ne prouve pas qu'on peut **s'y connecter** dans ce cadre : un fournisseur d'identité refuse d'être encadré. Contrôler le parcours complet, jusqu'à l'action.
- Un compteur de règle de pare-feu à zéro ne prouve pas l'absence de trafic : le chemin réel du paquet peut éviter la chaîne. Ce qui fait foi : l'état du service et la table de suivi des connexions.
- Un logiciel qui résout les noms par sa propre bibliothèque (libunbound pour Prosody) **ignore les domaines de recherche** du pod : écrire les noms de Service en entier, et faire résoudre le banc comme le cluster.
- Un serveur qui valide un jeton par l'userinfo accepte tout jeton du realm, quel que soit le client : garder chaque entrée (WebSocket compris) par l'oauth2-proxy de l'application.
- Une archive faite sur un Mac à partir de fichiers téléchargés porte des attributs étendus (`com.apple.provenance`) que le build binaire d'OKD ne sait pas lire : `COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata`, puis contrôler l'archive avant le build.
- Une condition de flux d'authentification niée se règle par une clé de négation propre à la condition : à vérifier en essai, invité compris.
- Un `add_header` dans une `location` de nginx annule ceux du niveau supérieur : l'en-tête `frame-ancestors` d'Element est répété dans chaque location.
- Un banc qui monte sa propre configuration ne prouve pas celle du déploiement : un module présent au banc manquait au ConfigMap généré par le rendu de production. Le banc monte désormais les ConfigMaps **du rendu de production**.
- Un serveur qui ne sait pas réserver une route à une source se protège par un **relais minimal** devant lui (une route, un port, une taille), pas par une règle réseau sur son port partagé.
