# Relais de l'identité de la personne vers un outil MCP

Cette fiche dit comment l'interface de discussion permet à un outil MCP d'**agir sous l'identité de la personne** qui parle, sans jamais donner son jeton au modèle ni à un outil qui n'en a pas besoin. Elle applique le motif de l'[Automation Déterministe](09-automation-deterministe.md) : le modèle repère l'intention, des règles décident, le serveur exécute.

L'exemple en service est la recherche dans les fichiers de la personne (La Suite Drive) depuis le chat ; le même chemin servira à tout outil qui doit voir « ce que cette personne a le droit de voir ».

---

## Problème

Un outil qui lit les documents d'une famille ou d'une équipe ne doit montrer à chacun que les siens. Deux raccourcis sont à écarter :

- un **compte de service qui lit tout**, puis un filtre dans l'outil : une erreur de filtre, et tout le monde voit tout ;
- le **jeton de la personne relayé tel quel** jusqu'au service : n'importe quel jeton du chat, s'il fuyait, ouvrirait alors le service.

Le droit doit rester celui du service lui-même, et chaque saut ne doit recevoir que le jeton émis pour lui.

---

## La chaîne

```
navigateur ──► oauth2-proxy ──► nginx ──► API du chat ──► MCP ──► fournisseur d'identité (échange)
               (jeton de la      (relais sur    (liste fermée   │
                session)          une route)     de serveurs)   └──► service (introspection)
```

| Saut | Ce qu'il fait | Ce qu'il refuse |
|---|---|---|
| **oauth2-proxy** | `--pass-access-token=true` : ajoute le jeton d'accès de la session en en-tête `X-Forwarded-Access-Token` ; `--cookie-refresh` **plus court que la vie du jeton d'accès** (par exemple 4 minutes pour un jeton de 5) | une valeur de cet en-tête envoyée par le navigateur est supprimée avant l'injection |
| **nginx** | relaie le jeton vers l'API du chat **sur la seule route de discussion**, sous un en-tête interne (`X-Sophia-Jeton`) | le vide sur toutes les autres routes, et ne le transmet **jamais** à la passerelle de modèles ; une valeur forgée de l'en-tête interne est écrasée ; le format du journal ne contient aucun en-tête |
| **API du chat** | envoie `Authorization: Bearer …` aux seuls serveurs MCP de la liste fermée `SOPHIA_MCP_JETON_URLS`, pour les outils qui déclarent `sophia/jeton` | le jeton n'est jamais écrit en base ni dans un journal, jamais montré au modèle, jamais mis dans les arguments d'un outil ; un outil d'un autre serveur qui demanderait le jeton ne le reçoit pas ; les outils à jeton ne sont jamais proposés au modèle : le serveur les appelle lui-même, après la décision des règles |
| **MCP** | vérifie le jeton (ci-dessous), puis l'**échange** contre un jeton émis pour lui | aucun en-tête d'identité n'est cru ; l'identité est le `sub` du jeton vérifié |
| **Service** | **introspecte** le jeton échangé auprès du fournisseur d'identité et applique ses propres droits | un jeton qui ne vient pas du MCP |

### Vérification par le MCP

Localement, avant tout appel :

- signature, par les clés publiques du realm (JWKS) ;
- `iss` = l'émetteur public du realm (`${OIDC_ISSUER}`), même si le MCP joint le fournisseur par son adresse interne ;
- `exp` ;
- `aud` contient le client du MCP (`${MCP_CLIENT_ID}`), ajouté au jeton du chat par un mappeur d'audience ;
- `azp` = le client du chat (`${CHAT_CLIENT_ID}`) ;
- `groups` contient l'un des groupes permis (`${ALLOWED_GROUPS}`) : la règle du chat est doublée ici.

### Échange de jeton

Le MCP échange le jeton (Keycloak **Standard Token Exchange V2**, RFC 8693) au nom de son **client confidentiel** `${MCP_CLIENT_ID}`, contre un jeton d'**audience du service** (`${SERVICE_CLIENT_ID}`), avec `scope=openid`. Ce qu'il faut savoir de Keycloak 26 :

- la fonction est active par défaut ; elle s'allume **par client**, sur le client demandeur, qui doit être confidentiel ;
- le jeton présenté doit porter le demandeur dans son `aud` : d'où le mappeur d'audience sur le client du chat ;
- le paramètre `audience` **filtre, il n'ajoute rien** : le demandeur doit avoir lui-même un mappeur qui met l'audience du service ;
- pas de jeton de rafraîchissement par échange : le MCP n'en a pas besoin ;
- le secret du client du MCP est dans un Secret de son namespace, créé par l'administrateur, jamais affiché.

Pourquoi échanger : le service n'accepte alors que des jetons **émis pour le MCP**. Le jeton du chat, s'il fuyait, n'ouvrirait pas son API. Le jeton échangé n'est ni journalisé ni gardé au-delà de l'appel (une session MCP par appel).

### Introspection par le service

- Le service introspecte avec son propre client. Depuis Keycloak 26, l'introspection **exige que ce client soit dans l'`aud`** du jeton, sinon elle répond `active: false` ; les options qui désactivent ce contrôle sont dépréciées et ne sont pas utilisées.
- Il lit la provenance dans `client_id` (= le client du MCP), seule valeur permise.
- Son API pour jeton relayé est servie sur un **port interne réservé** (`${SERVICE_API_PORT}`), sans Route, **en GET seulement** ; le port public répond 404 sur ce chemin. Une NetworkPolicy ne l'ouvre qu'au pod du MCP.
- Les actions permises par l'API sont une liste blanche réduite à la lecture.
- Les droits sont **ceux du service** : la personne ne voit que ses éléments et ceux qu'on lui a partagés. Aucun compte n'est créé par cette voie.

---

## Sorties sans URL, liens construits par le chat

- L'outil rend un **schéma fermé** : identifiant (UUID), nom, genre, type, chemin lisible, date, « modifiable ». **Aucune URL** : une adresse renvoyée serait ignorée.
- Le chat construit chaque lien : base de la liste fermée des applications, gabarit de chemin de la liste fermée, identifiant qui doit être un UUID (sinon la ligne est écartée). Une dernière garde vérifie, avant l'envoi, que tout lien de la réponse commence par une base permise.
- La réponse est **écrite par le serveur**, sans rappeler le modèle. Les noms sont des données, peut-être écrites par quelqu'un d'autre (un partage) : caractères de contrôle retirés, longueur bornée, caractères Markdown échappés.
- Dans l'historique, la liste est remplacée par un résumé avant tout appel au modèle : les noms de fichiers ne partent vers aucun modèle.
- Erreurs fermées, traduites en phrases par le chat : jeton absent ou expiré, compte jamais ouvert dans le service, service injoignable.

---

## Réseau

Sortie du MCP : DNS, le fournisseur d'identité (clés publiques et échange) et le port interne du service, **rien d'autre**. Entrée du MCP : la seule interface de discussion. La vérification de signature et l'échange imposent la sortie vers le fournisseur d'identité ; sans échange, elle disparaîtrait, au prix décrit plus haut.

---

## Pièges rencontrés

| Piège | Effet | Parade |
|---|---|---|
| `--cookie-refresh` d'une heure pour un jeton d'accès de 5 minutes | le jeton relayé est expiré la plupart du temps | rafraîchir la session en dessous de la vie du jeton, sans toucher au realm |
| nginx transmet par défaut tous les en-têtes reçus | sans règle explicite, le jeton partirait vers la passerelle de modèles et vers toutes les routes de l'API | chaque bloc `proxy_pass` pose ou vide l'en-tête ; éprouvé avec le binaire nginx et de faux services, route par route |
| Sans `--pass-access-token`, oauth2-proxy laisse passer l'en-tête | une valeur forgée par le navigateur arriverait jusqu'à nginx | l'option active, oauth2-proxy supprime la valeur reçue avant d'injecter la sienne ; nginx écrase de toute façon l'en-tête interne |
| Description d'un client de plus de 255 caractères | Keycloak répond 500 à l'import (colonne de 255) ; rien n'est créé | le script d'import refuse tout champ texte trop long, avant toute connexion |
| EgressFirewall d'un namespace de build en refus final | le build reste bloqué au clonage : l'API du cluster, jointe par le Service `kubernetes`, aboutit au nœud sur un port hors des plages permises | une règle vers les nœuds du plan de contrôle sur le port de l'API (`${CLUSTER_API_PORT}`), avant le refus, dans tout namespace qui lance des builds |
| Image de base qui installe des paquets | bloquée par l'EgressFirewall du build | une image qui contient déjà l'interpréteur, importée par le registre interne ; dépendances figées par empreinte |
| Serveur relais interne sans `X-Forwarded-Proto` | le service (Django en production) répond 301 vers https : « service injoignable » | reprendre dans le serveur interne les en-têtes `proxy_set_header` du serveur public ; tester les en-têtes attendus, pas seulement l'aiguillage |
| Journal INFO du client HTTP du MCP | l'URL du service, donc la recherche de la personne, finit dans le journal | ce journal passe en WARNING, avec un test qui échoue sans le correctif |
| Titre sans extension | un document créé dans le service depuis un modèle garde un titre sans extension : le bouton d'édition disparaissait | bouton d'édition si « modifiable » **et** type bureautique par l'extension **ou** le type MIME, dans une liste fermée |

---

## État

| Élément | État |
|---|---|
| Relais du jeton (oauth2-proxy, nginx, liste fermée) | en service |
| MCP « fichiers » : vérification, échange, recherche par le nom, liens construits par le chat | en service |
| Lecture du contenu d'un document, réservée aux modèles locaux | conçu |
| Validations humaines par le chat, avec le même jeton relayé | prévu (voir [Observabilité](10-observabilite.md)) |

---

## Ce que la fiche ne fait pas

- Aucun outil ne reçoit le jeton parce qu'il le demande : seule la liste fermée décide.
- Le modèle ne voit jamais un jeton, une adresse ni un identifiant, et n'en écrit aucun.
- Le MCP ne décide d'aucun droit : le service garde le sien.

---

## Position dans l'architecture

- identité et SSO : `sophia-identity` ([`deploy/okd/identity/`](../../deploy/okd/identity/)) ;
- interface de discussion : `sophia-apps` ([`deploy/okd/apps/chat-interface/`](../../deploy/okd/apps/chat-interface/)) ;
- outils MCP sans Internet : `sophia-skills` ;
- protections d'ensemble : [Modèle de sécurité](../security.md).
