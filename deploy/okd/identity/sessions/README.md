# Sessions d'oauth2-proxy côté serveur (Valkey)

Les applications protégées par oauth2-proxy (le chat et les autres applications web du foyer) rangent leurs sessions dans un **Valkey réservé aux sessions**, à côté de Keycloak. Le cookie du navigateur ne porte plus qu'un ticket d'une centaine d'octets. En service pour toutes les applications derrière oauth2-proxy.

## Pourquoi

Avec le stockage par cookie, une session de plus de 4 000 octets est découpée en morceaux (`<cookie>_0`, `<cookie>_1`…). oauth2-proxy (v7.15.5) lit d'abord un cookie **entier** du même nom, et l'enregistrement de morceaux ne l'efface pas : une session ancienne reste relue à chaque requête, à côté des nouveaux morceaux. L'en-tête `Cookie` dépasse alors la limite du serveur web derrière oauth2-proxy (8 Ko pour nginx) et la requête échoue en 400, sur un appareil qui garde une vieille session. La correction amont est encore ouverte.

Avec le stockage côté serveur, la session est dans Valkey, chiffrée (AES) par un secret propre au ticket, qui n'existe que dans le cookie du navigateur : sans le cookie, ce que Valkey garde sur disque est illisible.

## Choix

| Choix | Valeur | Raison |
|---|---|---|
| Placement | namespace d'identité, à côté de Keycloak | la session fait partie de l'authentification ; les oauth2-proxy sortent déjà vers ce namespace |
| Partage | une instance pour toutes les applications, **un utilisateur d'ACL par application** | pas de lecture croisée ; une instance par application donnerait autant de pods et de volumes pour quelques Mo |
| Cloisonnement des clés | chaque utilisateur ne voit que les clés de son cookie (`~<cookie>-*`) | le motif couvre les sessions (`<cookie>-<ticket>`) et le verrou de rafraîchissement (`<cookie>-<ticket>.lock`), sans toucher aux clés d'une autre application |
| Commandes | celles d'oauth2-proxy seulement : `GET`, `SET`, `DEL`, `PING`, `EXISTS`, `EVALSHA` et `EVAL` (verrou de rafraîchissement par scripts Lua), connexion (`HELLO`, `AUTH`, `CLIENT SETINFO`) | relevées dans le code d'oauth2-proxy, de son verrou et de son client Redis ; un essai réel sur un faux local n'a journalisé aucun refus |
| Usage | sessions seulement | un cache peut effacer des clés, une session ne doit jamais l'être ; tout autre besoin a sa propre instance |
| Éviction | `maxmemory 64mb`, `noeviction` | plein, Valkey refuse l'écriture (la connexion échoue) plutôt que d'effacer une session ; une session pèse environ 8,6 Ko |
| Persistance | AOF, `appendfsync everysec`, pas d'instantané, petit volume local | un redémarrage ne déconnecte personne ; une panne du nœud perd au plus une seconde d'écritures |
| Mots de passe | un par application, dans le namespace de l'application ; le fichier d'ACL ne contient que leurs **empreintes SHA-256** (`acl.sh`) | un pod ne lit pas un Secret d'un autre namespace ; aucun mot de passe en clair côté Valkey |
| Utilisateur `default` | désactivé | sans mot de passe, aucune commande |
| Contrôle | utilisateur `controle` : `PING`, `INFO`, `DBSIZE`, aucune clé | l'administrateur vérifie mémoire, persistance et nombre de sessions sans pouvoir lire une session |
| Réseau | entrée seulement depuis les pods des applications nommées, sur 6379 ; **aucune sortie** | Valkey ne joint rien, ni DNS ni API |
| Priorité | celle du chat | le chat en dépend à chaque requête, comme de Keycloak |

## Fichiers

| Fichier | Contenu |
|---|---|
| `01-volume.yaml` | PV local et PVC désignés l'un l'autre (aucune autre PVC ne peut le prendre) |
| `02-valkey.yaml` | ServiceAccount sans jeton, Deployment (`Recreate`, image figée par empreinte, ACL lues dans un Secret), Service |
| `03-network.yaml` | entrée limitée aux pods des applications, sortie vide |
| `acl.sh` | construit le Secret du fichier d'ACL à partir des empreintes des mots de passe ; refuse un Secret absent, un mot de passe de moins de 32 caractères, un fichier sans `user default reset off` |

## Côté application (oauth2-proxy)

```
--session-store-type=redis
--redis-connection-url=redis://valkey-sessions.sophia-identity.svc.cluster.local:6379/0
--redis-username=<utilisateur de l'application>
```

Mot de passe par la variable `OAUTH2_PROXY_REDIS_PASSWORD`, en `secretKeyRef` sur le Secret `<application>-sessions` (clé `password`) ; sortie réseau vers les pods `app: valkey-sessions` du namespace d'identité, TCP 6379. Exemple complet : [interface de discussion](../../apps/chat-interface/sophia-interface.yaml).

**Transition** : le passage déconnecte chacun une fois, mais les anciens morceaux de cookie restent dans les navigateurs jusqu'à leur expiration. La limite d'en-tête de chaque serveur derrière oauth2-proxy est donc relevée à **32 Ko** : nginx `large_client_header_buffers 4 32k` ; uvicorn `--h11-max-incomplete-event-size 32768`. **Piège** : h11, le serveur HTTP d'uvicorn, plafonne à 16 Ko par défaut, plus bas que le routeur d'OKD (environ 24 Ko d'en-têtes) ; ce n'est pas nginx seul qu'il faut relever.

## Procédure (administrateur)

**Aucun secret dans une variable du terminal** : chaque mot de passe est généré puis écrit aussitôt par un tube dans son Secret, jamais affiché. Chaque `oc apply` passe d'abord à blanc (`--dry-run=server`).

1. **Sur le nœud** : `sudo mkdir -p /var/lib/sophia/valkey-sessions`, puis `sudo chcon -t container_file_t` sur ce répertoire.
2. **Mots de passe** (contrôle, puis une application) :
   ```bash
   openssl rand -hex 32 | tr -d '\n' | oc -n sophia-identity create secret generic valkey-sessions-controle --from-file=password=/dev/stdin
   openssl rand -hex 32 | tr -d '\n' | oc -n sophia-interface create secret generic sophia-interface-sessions --from-file=password=/dev/stdin
   ```
3. **Fichier d'ACL** : `bash deploy/okd/identity/sessions/acl.sh` (relecture, empreintes seulement), `--a-blanc`, puis `--appliquer`.
4. **Volume, Valkey, réseau** : `01-volume.yaml` (variable `${NODE_NAME}` : nœud qui porte le volume, `oc get nodes`, par exemple `node-0` ; `envsubst '${NODE_NAME}' < 01-volume.yaml | oc apply -f -`), `02-valkey.yaml`, `03-network.yaml`.
5. **Contrôles** : sans mot de passe, `valkey-cli ping` est refusé (`NOAUTH`) ; avec `controle` (mot de passe passé par un tube jusque dans le pod), `aof_enabled:1`, `maxmemory_policy:noeviction`, et `GET` refusé (`NOPERM`).
6. Puis chaque application passe à `--session-store-type=redis`, avec sa sortie réseau ; `DBSIZE` monte à chaque connexion.

## Ajouter une application

1. Créer son Secret `<application>-sessions` dans son namespace (étape 2).
2. Ajouter sa ligne dans `acl.sh` et son entrée dans `03-network.yaml` (modèles en commentaire).
3. `acl.sh --a-blanc` puis `--appliquer` ; `03-network.yaml` à blanc puis réel.
4. **À un moment calme** : `oc -n sophia-identity rollout restart deploy/valkey-sessions`. Valkey ne lit le fichier d'ACL qu'au démarrage : aucun utilisateur n'a le droit `ACL LOAD`, volontairement. Les sessions survivent (AOF) ; les applications déjà branchées répondent en erreur quelques secondes.
5. L'application passe à `--session-store-type=redis`, avec la limite d'en-tête relevée.

## Limites connues

- Pas de TLS entre oauth2-proxy et Valkey, comme pour PostgreSQL : mot de passe et sessions chiffrées circulent en clair sur le réseau des pods, sur un seul nœud.
- Un seul pod : pendant un redémarrage de Valkey, les applications branchées répondent en erreur quelques secondes.
- Pas de sauvegarde : perdre le fichier AOF revient à une reconnexion de chacun.
