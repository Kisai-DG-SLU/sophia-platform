# Module Bureautique — documentation

## Ce que fait le module

- **Ranger et partager** : chaque personne a son espace de fichiers, avec dossiers, aperçus et historique des versions. Tout est **privé par défaut** ; un partage (lecteur ou éditeur) demande un geste explicite, et un lien reste « restreint » tant qu'on ne l'ouvre pas.
- **Éditer** : les documents bureautiques (texte, tableur, présentation, OpenDocument et formats Microsoft) s'ouvrent dans Collabora, dans la page de Fichiers, à plusieurs à la fois.
- **Depuis la discussion** : Sophia retrouve un fichier de la personne par son nom, puis propose de l'ouvrir (dans Collabora pour un document modifiable, dans Fichiers sinon) et de voir le dossier qui le contient. Elle peut aussi lire et résumer le contenu d'un document, avec un modèle local seulement.

## Architecture

```
navigateur (VPN) ──► routeur d'entrée ──► nginx de Fichiers ──► interface, API, Collabora
                                              │
                                              ├──► S3 commun (médias, après autorisation par l'API)
                                              └──► port interne réservé, GET seulement ◄── outil MCP « fichiers »

API de Fichiers ──► PostgreSQL 18 partagé, fournisseur d'identité (OIDC), Valkey (file de tâches, cache)
Collabora ──► API WOPI de Fichiers (TLS interne), DNS ; rien d'autre
```

| Élément | Choix | Raison |
|---|---|---|
| Namespace | dédié (`sophia-workspace`), quota et LimitRange propres | isoler la bureautique du chat et des agents ; le quota couvre les Jobs et le pod de plus d'une mise à jour progressive |
| Priorité | classe `sophia-workspace-low`, sans préemption | sous la discussion, la voix et les agents ; au-dessus des images et du développement ([priorités](../../../deploy/okd/cluster/README.md)) |
| Base | PostgreSQL 18 partagé, un rôle et une base propres, sans superutilisateur | Drive range ses éléments dans des chemins `ltree` dont les étiquettes contiennent des tirets, refusés avant PostgreSQL 16 : la création d'un dossier échouait en 15 |
| Fichiers | S3 commun ([`deploy/okd/storage/`](../../../deploy/okd/storage/README.md)), seau versionné, **corbeille de 30 jours** pour les versions remplacées | une version écrasée ou supprimée se retrouve pendant 30 jours, puis l'espace est rendu |
| Téléversement | URL présignée, du navigateur vers le S3 | le fichier ne transite pas par l'API |
| Médias | servis par nginx après une sous-requête d'autorisation à l'API | les droits restent ceux de Fichiers |
| Identité | client OIDC confidentiel, flux standard avec PKCE | connexion unique ; aucun compte local |
| Isolation | pods en `restricted-v2`, sans capacité ; Collabora isole les documents par **Landlock** | Collabora ne reçoit aucune capacité Linux ; Landlock est vérifié actif dans son journal |
| Collabora | `always_save_on_exit=true`, `idle_timeout_secs=1800`, `max_concurrency=2`, `cleanup.limit_dirty_mem_mb=1024` ; sauvegarde automatique à 30 s et 5 min ; sonde sur `/` | rien ne se perd à la fermeture ; un document oublié libère la mémoire ; deux conversions au plus en parallèle sur un nœud partagé |
| Preuve WOPI | une clé de preuve RSA dans un Secret monté | sans elle, Collabora ne signe pas ses appels et Fichiers ne vérifie pas leur origine |
| Images | figées par empreinte | une mise à jour est une décision |

### nginx de Fichiers : trois correctifs de la mise en service

| Constat | Cause | Correctif |
|---|---|---|
| Aperçu d'image en 403 | nginx relayait vers le S3 les en-têtes `X-Forwarded-*` posés par le routeur ; SeaweedFS vérifiait la signature sur l'hôte public, pas sur l'hôte interne signé par l'API | ces en-têtes sont vidés dans les locations de médias |
| Éditeur : « failed to establish socket connection » | la location `^~ /cool` arrêtait la recherche avant la regex du WebSocket ; Collabora recevait un GET sans `Upgrade` | `location ~ ^/cool` après la regex `/ws`, comme la configuration de référence de Collabora ; les deux formes d'URL du WebSocket passent |
| Jetons WOPI dans le journal d'accès | format de journal par défaut | un format qui masque le chemin de `/cool/`, retire la requête des appels WOPI et masque un Referer qui contient un jeton |

Leçon : un relais se teste par de vraies requêtes contre de faux services, en-têtes compris, pas seulement par `nginx -t`.

## Confidentialité

- **Chacun ses fichiers** : un élément créé par une personne est invisible des autres, y compris par son adresse directe, tant qu'il n'est pas partagé.
- **Pas de chiffrement par personne** : les fichiers sont dans le S3 et la base de l'installation. L'administrateur du système peut donc lire les données brutes ; la confidentialité tient aux droits de l'application, pas à une clé propre à chaque personne.
- **Comptes protégés** (enfants) : ils ont un espace comme les autres ; depuis la discussion, le contenu de leurs documents ne part que vers le modèle local, comme toutes leurs données.

## Depuis la discussion : l'outil MCP « fichiers »

Un serveur MCP en lecture seule ([`deploy/okd/skills/`](../../../deploy/okd/skills/README.md)), sous l'identité de la personne : le chat relaie son jeton, l'outil le vérifie puis l'échange contre un jeton émis pour lui, et Fichiers applique ses propres droits. La chaîne complète est décrite dans [Relais de l'identité](../../concepts/12-relais-identite.md).

| Outil | Ce qu'il rend | État |
|---|---|---|
| `chercher_fichiers` | jusqu'à 10 éléments trouvés **par le nom** (sans accents ni casse), avec chemin, date, type, « modifiable » ; sans URL | en service |
| `details_fichier` | un élément et son chemin lisible | en service |
| `lire_fichier` | le texte d'un document (odt, docx, ods, xlsx, pdf, txt, md, csv), borné, marqué « contenu sensible » | déployé, recette à faire |

- **API dédiée** : Fichiers sert son API pour jeton relayé sur un **port interne réservé**, sans Route, **en GET seulement** ; le port public répond 404 sur ce chemin. Les actions permises sont une liste blanche de lecture. La lecture du contenu passe par la même autorisation que les médias, sur ce port.
- **Liens construits par le chat** : l'outil ne rend aucune adresse ; le chat compose « Ouvrir dans Collabora » pour un élément modifiable **et** de type bureautique (par l'extension **ou** le type MIME), « Ouvrir dans Fichiers » (l'aperçu) pour les autres, et « Voir dans Fichiers » vers le dossier qui contient l'élément quand il est lisible par la personne.
- **Contenu local seulement** : le chat n'appelle `lire_fichier` qu'avec un modèle de la liste des modèles locaux, retire ce contenu de tout appel à un autre modèle, et ne propose aucun outil après une lecture (voir [Modèles par rôle](../../concepts/13-modeles-par-role.md)).
- **Pas de recherche dans le contenu** : Drive n'indexe pas le texte des fichiers sans son moteur de recherche, non installé.

## Navigateurs

Drive et Collabora utilisent des blocs `static {}` d'ES2022 : il faut au moins **Safari 16.4** (ou un navigateur équivalent). Sur un appareil plus ancien, Fichiers ne démarre pas, et aucun correctif côté serveur n'est raisonnable. Le chat détecte le moteur par un petit script ES2022 (pas par le User-Agent) : sur un moteur trop ancien, les boutons vers Fichiers deviennent un texte inactif qui le dit, et la liste des résultats reste affichée.

## Prévu

- **Courrier unifié** (décidé) : un agrégateur local qui rassemble les boîtes existantes d'une personne par IMAP (synchronisation bidirectionnelle), avec tri, anti-spam et webmail derrière le SSO ; aucun serveur exposé à Internet. Un **outil MCP** permettra au modèle ou à un workflow de chercher, lire, classer et préparer un brouillon, jamais d'envoyer ni de supprimer définitivement : l'envoi reste validé par la personne.
- **Discussion permanente et visio** : installées, en recette, dans un module à part ([Communication](../communication/README.md)) ; Jitsi Meet a remplacé la Visio de La Suite. Lancer une visio depuis la discussion reste prévu.

## Leçons

- Une base « déjà testée » par les migrations ne l'est pas pour l'écriture : la première création de dossier a révélé l'exigence de PostgreSQL 16.
- Avant de basculer un service vers une nouvelle base, contrôler sa **sortie** réseau autant que l'entrée de la base.
- Un jeton peut finir dans un journal par une voie inattendue (journal d'accès, journal d'erreurs, client HTTP d'un outil) : chaque voie se vérifie.
