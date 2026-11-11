# Identité — Keycloak (SSO)

Fournisseur d'identité unique de la plateforme (OIDC) : une personne, un compte, une connexion pour toutes les applications. Les groupes du realm portent les rôles décrits dans le [périmètre fonctionnel](../../../docs/functional-scope.md#utilisateurs-et-rôles).

| Choix | Valeur | Raison |
|---|---|---|
| Installation | operator Keycloak officiel (OLM, catalogue `community-operators`), approbation manuelle | realm et clients décrits en ressources Kubernetes, reproductibles |
| Base | rôle et base dédiés dans le PostgreSQL existant | pas de nouveau volume quand le stockage n'a pas de provisionneur dynamique |
| Nom public | sous le domaine joker des Routes (`auth.apps.example.org`) | couvert par le DNS et le certificat du routeur, résolvable depuis le cluster |
| TLS | terminé par la Route (edge, Redirect) | Keycloak en HTTP dans le cluster, en-têtes `X-Forwarded-*` |

## Fichiers

| Fichier | Contenu |
|---|---|
| `00-namespace-operator.yaml` | namespace, OperatorGroup, Subscription (approbation manuelle) |
| `02-network.yaml` | Keycloak n'accepte, sur son port HTTP, que le routeur et une liste nommée de clients qui l'appellent par son Service interne, et sur son port de gestion que son propre namespace |
| `03-keycloak.yaml` | instance Keycloak (avec la liste des entrées de la politique réseau que crée l'operator) et Route |
| `04-realm-sophia.yaml` | realm : groupes, politique de mots de passe, clients OIDC — interface de discussion (PKCE, secret par *placeholder*), administration de RabbitMQ (client public PKCE, audience `rabbitmq`), interface de Temporal (oauth2-proxy, secret par *placeholder*) ; mappeurs d'audience du jeton relayé par l'interface |
| `ajouter-mappeur-audience.py` | ajoute au client de l'interface un mappeur d'audience vers un service qui reçoit le jeton relayé (ci-dessous) ; lecture seule avec `--dry-run`, rejouable |
| [`sessions/`](sessions/README.md) | Valkey réservé aux sessions des oauth2-proxy : un utilisateur d'ACL par application, persistance AOF, aucune sortie réseau |

## Procédure

1. **Operator** : `oc apply -f 00-namespace-operator.yaml`, approuver l'InstallPlan, attendre le CSV `Succeeded`.
2. **Base** : créer le secret `keycloak-db` (utilisateur, mot de passe aléatoire), puis le rôle et la base dans PostgreSQL 18, dont l'entrée admet déjà le namespace d'identité ([`core/postgres18/03-network.yaml`](../core/postgres18/03-network.yaml)). **Le mot de passe passe par l'entrée standard de `psql`, jamais par la ligne de commande** : les arguments d'`oc exec` sont tracés par l'API.
   ```bash
   KC_DB_PASS=$(openssl rand -base64 30 | tr -d '/+=' | cut -c1-32)
   oc create secret generic keycloak-db -n sophia-identity --from-literal=username=keycloak --from-literal=password="$KC_DB_PASS"
   oc exec -i -n sophia-core deploy/postgres-sophia-18 -- psql -v ON_ERROR_STOP=1 <<SQL
   CREATE ROLE keycloak LOGIN PASSWORD '$KC_DB_PASS';
   CREATE DATABASE keycloak OWNER keycloak;
   REVOKE ALL ON DATABASE keycloak FROM PUBLIC;
   SQL
   unset KC_DB_PASS
   ```
3. **Réseau** : `oc apply -f 02-network.yaml`.
4. **Keycloak** : `oc apply -f 03-keycloak.yaml`, attendre `Ready`. Se connecter avec l'administrateur temporaire créé par l'operator, **créer un administrateur nominatif dans le realm `master`, supprimer le temporaire**.
5. **Realm** : créer le secret du client (`openssl rand -hex 32`), puis `oc apply -f 04-realm-sophia.yaml`, attendre `Done`. Créer les utilisateurs dans la console (e-mail renseigné et vérifié) et les placer dans un groupe.

## Pièges rencontrés

- **Une liste fournie dans l'import remplace les valeurs par défaut du realm.** Déclarer `clientScopes` pour ajouter un scope supprime `profile`, `email`, `basic`… et la connexion échoue en `invalid_scope`. Ajouter, ne pas redéfinir : le mappeur des groupes est porté par le client.
- **L'operator crée sa propre NetworkPolicy, ouverte à tout le cluster.** Sans liste dans le CR (`spec.networkPolicy`), elle ouvre le port HTTP (8080) et le port de gestion (9000) à tous les pods ; comme les politiques s'additionnent, celle de `02-network.yaml` ne filtrait alors rien sur ces ports. Le CR porte donc la même liste de pairs que `sophia-identity-ingress` : **un client de plus par le Service interne = une ligne dans les deux listes**, sinon sa connexion échoue. Les clients qui passent par le nom public passent par le routeur, déjà admis. À appliquer à un moment calme, avec un contrôle de connexion de chaque application ; le pod de Keycloak ne redémarre pas. En service.
- **L'import ne s'applique qu'à la création du realm.** Pour rejouer un import corrigé : supprimer le realm, supprimer la ressource `KeycloakRealmImport`, réappliquer. Sur un realm existant, un client ajouté au fichier s'importe à part, depuis la console (*Clients → Import client*) ; le fichier reste la référence d'une installation neuve.

## Audiences du jeton relayé par l'interface

Quand l'interface de discussion relaie le jeton d'accès de la personne (voir [Relais de l'identité](../../../docs/concepts/12-relais-identite.md)), chaque service destinataire n'accepte que les jetons qui portent **son audience**. Elle est ajoutée au jeton du client de l'interface par un **mappeur d'audience**, un par service :

| Service destinataire | Vérification | Mappeur |
|---|---|---|
| serveur MCP qui échange le jeton (fichiers) | signature, puis échange au nom de son client | audience de client (`included.client.audience`) |
| oauth2-proxy d'une application, pour sa route de résumé du dashboard | `--skip-jwt-bearer-tokens` : vérificateur principal du fournisseur, `client-id` de l'application exigé dans `aud` | audience de client, égale au `client-id` de l'application |
| module qui vérifie lui-même la signature, sans client propre (résumé de la messagerie) | signature par les clés du realm, émetteur, audience, client d'origine, groupes | **audience personnalisée** (`included.custom.audience`, option `--personnalisee`) : aucun client Keycloak n'est créé, puisqu'il ne servirait qu'à l'introspection ou à l'échange |

```bash
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <client-de-l-application> --dry-run
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <client-de-l-application>
python3 deploy/okd/identity/ajouter-mappeur-audience.py sophia-interface <audience-libre> --personnalisee --dry-run
```

- Le script relève d'abord le **mappeur de groupes** du client : `--allowed-group` d'oauth2-proxy compare la valeur exacte, d'où des groupes **sans chemin** (`full.path false`) dans le **jeton d'accès**. Un mappeur non conforme arrête le script.
- Il refuse les cas mal assortis : `--personnalisee` pour un nom qui est un client, ou l'inverse.
- Une nouvelle audience n'arrive qu'au renouvellement du jeton : un 403 juste après, avec un jeton antérieur, est attendu.
- **Jamais `--extra-jwt-issuers`** côté application : ce réglage lance une découverte OIDC sur l'adresse **publique** du fournisseur, que les pods ne joignent pas. Le vérificateur principal (clés par le Service interne, émetteur public) suffit.
- Les en-têtes du realm ne changent pas : la page de connexion reste refusée dans un cadre (le dashboard propose « Se reconnecter »).
- Ces mappeurs sont dans `04-realm-sophia.yaml` pour une installation neuve ; le script sert à les ajouter à un realm existant, puisque l'import ne s'applique qu'à la création.

État : quatre audiences (trois applications, la messagerie) en service, contrôlées par rejeu du script (« existe, non modifié ») et par un jeton invalide refusé en 403 par les deux premières applications ; la troisième (finances), par l'appel réel du dashboard (200, jeton accepté).

## Date de naissance des comptes, lue par une application

La date de naissance de chaque compte vit dans le fournisseur d'identité, saisie par l'administrateur. Chaque application qui en a besoin (âge d'un enfant pour son épargne, tranche d'âge d'un adulte, plus tard des anniversaires) la lit avec **son propre client de lecture**, limité à **un groupe**. Aucune date ne part dans les jetons des personnes.

1. **Attribut `birthdate`** ajouté au profil utilisateur du realm, sans rien retirer (un profil déclaré dans l'import remplacerait le profil par défaut entier) : lecture et écriture réservées à l'administrateur, format ISO imposé (`04/03/2015` est refusé en 400). La personne ne le voit pas dans sa console de compte et ne peut pas l'écrire.
2. **Mappeur `birthdate` retiré de la portée `profile`, avant toute saisie** : la portée par défaut porte ce mappeur, et la date partait dans le jeton d'accès de chaque personne malgré les droits du profil (éprouvé). Sans lui, elle n'y est plus.
3. **Saisie** dans la console d'administration, compte par compte ; vérification par un script qui ne rend que des nombres (date présente, format correct), jamais une date.
4. **Client de lecture** par application : compte de service seul, **aucun rôle de `realm-management`**, une seule **permission fine** `view-members` sur le groupe (permissions fines du realm, version 2). Il lit les membres du groupe et leur date ; il reçoit 403 pour un compte hors du groupe, la liste et la recherche des utilisateurs, les groupes, les rôles, les clients et toute écriture. `query-users` n'est pas nécessaire. Son secret va dans un Secret de l'application ; l'identifiant du groupe, non secret, dans sa configuration. Un même client peut lire plusieurs groupes (par exemple les enfants et les adultes d'une application de finances).

| Piège | Conséquence | Parade |
|---|---|---|
| Les permissions fines n'acceptent que la stratégie unanime (400 pour « affirmative ») et combinent à l'unanimité les permissions d'une même ressource | deux permissions sur un même groupe, une par client, se bloquent : 403 pour les deux | **une politique « clients » par groupe**, qui liste ses clients de lecture, sous **une seule permission** par groupe ; un script qui trouve une autre permission sur le groupe s'arrête sans rien faire |
| Le mappeur `birthdate` de `profile` existe par défaut | la date part dans les jetons dès sa saisie | retirer le mappeur avant la première saisie, et le vérifier |
| Toute personne ajoutée plus tard au groupe | devient lisible par le client | lire un groupe qui contient exactement les comptes voulus |

- **Côté application** : le jeton du client de lecture reste en mémoire ; seuls l'identifiant du compte et sa date sont gardés, en cache mémoire, jamais en base ni dans un journal ; l'âge d'un adulte n'est utilisé qu'en tranche. Le jeton se demande par le Service interne du fournisseur, et l'API d'administration l'accepte.
- **Failles connues** des permissions fines version 2 (CVE-2026-14613, groupes vus par un rôle ; CVE-2026-14615, sous-groupes vus par un groupe parent) : un client de lecture n'y est pas exposé, puisqu'il n'a aucun droit sur les rôles et lit un groupe sans sous-groupe.
- **Retour arrière** : supprimer la permission, la politique, puis le client et son Secret ; retirer l'attribut du profil (les valeurs restent stockées, à effacer compte par compte si voulu) ; recréer le mappeur dans `profile`. Sans permission, les permissions fines activées n'accordent rien.

État : en service. Éprouvé d'abord sur un Keycloak local (même image que la production, sans réseau), puis contrôlé en nombres après l'installation : tous les comptes datés au bon format, aucun mappeur `birthdate` dans `profile`, deux groupes lisibles par le client et quatre refus attendus pour chacun ; première lecture par l'application confirmée au journal.

## Réserver une application à certains groupes : chat permanent et visio

Les clients `matrix` (service d'authentification de Matrix) et `jitsi` (adaptateur de la visio) du [module Communication](../../../docs/modules/communication/documentation.md), installé et en recette, sont **confidentiels**, en flux standard avec **PKCE S256**, avec le mappeur `groups`. Ni MAS ni Jitsi ne savent filtrer par groupe : le refus se fait dans Keycloak, avant que l'application ne voie la personne.

1. **Rôle de client** `acces` sur chaque client, donné aux groupes admis (le foyer, sans les invités).
2. **Flux d'accès propre au client** (`acces-matrix`, `acces-jitsi`) : une **copie du flux navigateur réel du realm**, avec toutes ses étapes (dont le second facteur conditionnel de Keycloak), à laquelle s'ajoute une sous-étape conditionnelle « Condition - user role » sur ce rôle, **niée**, suivie de « Deny access ». Le flux est lié au client (*Authentication flow overrides*), le flux navigateur du realm reste inchangé.
3. **Essai** avec un compte admis **et** un compte invité : le second doit être refusé par Keycloak.

Piège : la négation de la condition se règle par sa clé de configuration `negate` ; une condition mal niée refuse tout le monde, ou personne. Seul l'essai avec les deux comptes le montre.

Applications clientes : [interface de discussion](../apps/chat-interface/README.md), [RabbitMQ](../core/rabbitmq/README.md), [Temporal](../core/temporal/README.md), [bureautique, chat permanent et visio](../office/README.md). Keycloak accepte depuis `sophia-core` les pods de Temporal (clés de signature, jetons des comptes de service) : `02-network.yaml`.
