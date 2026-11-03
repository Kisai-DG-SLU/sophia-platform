# Service mémoire (`sophia-memoire`)

La mémoire du foyer est un **service**, comme le modèle de langage : appelé par l'interface et par les agents, chacun avec ses droits, et **seul rédacteur** de la connaissance. Il reçoit les documents, en extrait le texte dans un pod isolé, les range en versions, les fait valider par une personne désignée, puis les rend cherchables. Le modèle de la connaissance est décrit dans la fiche [RAG 5D](../../../../docs/concepts/03-rag-5d.md) ; la page du dashboard qui l'utilise, dans le [dashboard](../../apps/chat-interface/README.md#page--mémoire-).

**État dans l'installation de référence** : **en service**. Les étapes de mise en service ci-dessous ont toutes été faites, avec leurs deux épreuves conformes (politique du seau, isolement de l'extraction). La page « Mémoire » du dashboard est déployée ; le premier dépôt réel vient avec son contrôle de bout en bout. Le code du service n'est pas fourni ; ce document en donne le contrat, les règles et la recette.

## Où vit quoi (RAG 5D)

Chaque lieu a un seul rôle. Le registre est écrit **en dernier** : tant qu'il ne référence pas un objet, cet objet n'existe pas pour le service.

| Lieu | Ce qu'il garde | Source de vérité ? |
|---|---|---|
| **Stockage objet S3**, un seau versionné, sans purge (`${MEMOIRE_SEAU}`) | l'**original** de chaque version et son **texte extrait**. Sous `attente/`, la version en attente, effaçable. Sous `valide/`, l'original de chaque version validée (son texte va dans la forge), **protégé contre toute suppression**, même par le service | oui, pour les originaux |
| **PostgreSQL**, un schéma dédié (`${MEMOIRE_SCHEMA}`) | le **registre** : documents, versions, états, empreintes, références vers S3 et vers la forge | oui, pour l'état et les références |
| **Forge Git** (Forgejo), une organisation privée, **un dépôt par niveau** | le **texte validé** de chaque version, en Markdown avec un en-tête ; **un commit par version validée, jamais avant** ; une copie miroir sur un hébergeur externe | oui, pour les textes validés |
| **Base vectorielle** (Qdrant) | les morceaux et leurs vecteurs : la version validée de chaque document, plus la version en attente (marquée, jamais rendue par une recherche) | **non** : un index, reconstructible depuis le registre et les textes |
| **Table d'audit** commune (`audit_log`) | chaque écriture et chaque refus, sans contenu | journal |

Ce que cela donne :
- **Une version refusée n'entre jamais dans la forge** : sa suppression ne demande aucune réécriture de l'historique Git. Tant qu'elle attend, son texte est dans S3, d'où elle s'efface.
- **Un service compromis peut effacer ce qui attend, jamais ce qui est validé** : la politique du seau lui refuse toute suppression sous `valide/`.
- **Le texte extrait est gardé** : un changement de bibliothèque d'extraction ne touche pas les documents déjà déposés, et l'index se reconstruit sans relire les originaux.
- **La forge prépare les dimensions suivantes** : chaque dépôt de niveau pourra être cloné en coffre de notes (dimension structurelle), et le registre nourrira le graphe (dimension 5). Rien de plus n'est à garder aujourd'hui.

### Seau S3 : un seau, deux préfixes

| Préfixe | Contenu | Droits du service |
|---|---|---|
| `attente/originaux/<document>`, `attente/textes/<document>.md` | la version en attente | écrire, lire, supprimer, y compris une version S3 |
| `valide/originaux/<document>` ; `valide/textes/<document>.md` seulement pour un niveau absent de la table de la forge (aucun aujourd'hui) | l'original de chaque version validée, comme version S3 de la même clé ; le texte validé va dans la forge | écrire et lire seulement |

- L'identité S3 du service n'a que la lecture et la liste du seau, et l'écriture sous les deux préfixes ; ni étiquettes, ni administration.
- Une **politique du seau** lui refuse, en plus : toute suppression (objet ou version) sous `valide/`, la suspension du versionnement, le changement de la politique, du cycle de vie, de la CORS ou du verrouillage.
- **Versionnement activé, sans règle de cycle de vie.**
- **Un seul seau suffit** si le stockage évalue la politique **clé par clé**, y compris pour une suppression groupée. C'est le cas de SeaweedFS (vérifié dans son code, puis éprouvé en service). Sinon : deux seaux, l'un pour l'attente, l'autre pour le validé, avec la même logique.

### Forge : un dépôt par niveau

- Une organisation privée, avec un dépôt par niveau de confidentialité (`public`, `famille`, `personnel`, `intime`, `admin`). La correspondance niveau → dépôt est **une seule table du code** : un niveau qui en serait retiré garderait son texte validé dans S3, sous `valide/textes/`.
- Dans chaque dépôt, le fichier est `<personne>/<chemin>.md`, où `<personne>` est l'**identifiant technique** de la personne (jamais un prénom), ou `agent-<nom>`. Une proposition sans chemin (chat, agent) va sous `<personne>/_propositions/<document>.md`. Le préfixe de personne évite toute collision dans un même dépôt.
- **En-tête YAML** : document, version, version remplacée, niveau, genre, chemin, auteur affichable, empreinte, dates de dépôt et de validation, et un lien `source` vers l'original dans S3 avec son identifiant de version.
- **Message du commit** : `document <id>, version <n>`, sans titre ni chemin.
- **Rejeu** : avant d'écrire, le service relit le fichier ; si l'en-tête porte déjà l'empreinte et le numéro de la version, il reprend ce commit au lieu d'en créer un second.
- **Compte du service** : restreint, ni administrateur ni propriétaire, sans droit de créer un dépôt ou une organisation, membre d'une équipe qui n'a que l'écriture du code sur les seuls dépôts de niveau ; un jeton limité à l'écriture des dépôts. Dans Forgejo, utilisateurs et organisations partagent un seul espace de noms : le compte ne peut pas porter le nom de l'organisation.

## Documents et versions (V1)

- **Un document, c'est une personne et son chemin complet** (dossier et nom). Le chemin est comparé en Unicode normalisé et **sans la casse** : un clone de la forge sur un système de fichiers insensible à la casse ne mélangera jamais deux fichiers. Le chemin affiché reste celui du premier dépôt.
- **Un dépôt n'est qu'un lot** : il regroupe les versions d'un même envoi, pour la validation groupée et l'audit, sans faire l'identité du document. Une note et un fichier au même chemin sont le même document.
- **Le niveau, le genre et le format appartiennent au document** : une version à un autre niveau est refusée (`niveau_different`), un autre format ou genre aussi (`type`). Changer le niveau d'un document sera un geste à part, plus tard.
- **Une nouvelle version attend, et la version validée précédente reste cherchable** (V1). Il n'y a jamais deux versions en attente : une nouvelle version **abandonne** celle qui attendait encore (ses morceaux et ses objets sous `attente/` sont supprimés, l'état `abandonnee` est audité). Le valideur ne voit donc que la dernière.
- **États d'une version** : `en_attente`, `valide`, `remplacee` (validée puis dépassée), `rejete` (refusée), `abandonnee`. Au registre, au plus une version en attente et une version validée par document, garanties par deux index uniques partiels.
- **Renommer ou déplacer** un document, c'est un autre chemin, donc un autre document ; l'ancien garde son historique.

### Déroulés

| Geste | Étapes, chacune rejouable sans dommage |
|---|---|
| **Dépôt** (fichier, note, proposition) | relecture du registre (même empreinte que la version en attente ou validée : **reprise**, rendue 200 sans rien écrire) ; contrôles (niveau, garde de version, genre, bornes) ; extraction, avec le contrôle du format ; vecteurs ; audit `tentative` ; S3 sous `attente/` (original, puis texte) ; morceaux dans l'index, marqués en attente ; **registre en dernier**, en une transaction qui ajoute la version `en_attente` et passe à `abandonnee` celle qui attendait ; audit `ecrit` ; puis effacement de la version abandonnée (morceaux et objets sous `attente/`) et son audit. Ce que verse le valideur est validé dans la même requête |
| **Validation** | audit ; copie de l'original vers `valide/` ; texte lu sous `attente/` et commité dans la forge ; dans l'index, les morceaux de la version précédente supprimés et ceux de la nouvelle passés à `valide` ; **registre en dernier** (nouvelle `valide`, précédente `remplacee`) ; suppression sous `attente/` ; audit de la décision |
| **Refus** | audit ; morceaux supprimés ; objets sous `attente/` supprimés ; registre `rejete`, sans empreinte ni référence ; audit. Sans version validée, le document perd aussi son chemin. La version validée précédente reste cherchable |
| **Recherche** | seulement les morceaux `valide`, non expirés, lisibles par l'appelant ; le résultat porte le document et le numéro de version |

**Analyse synchrone** : extraction, découpage (2 000 caractères, recouvrement de 200) et vecteurs se font pendant la requête, qui rend l'état final. Au pire environ quatre minutes hors lenteur du stockage (extraction 90 s, vecteurs 120 s, base vectorielle 30 s) ; s'y ajoutent, en cas de lenteur, S3 (deux écritures, 30 s chacune), le registre (10 s) et l'audit (5 s par ligne), et à la validation la forge (lecture et écriture, 30 s chacune). Le relais du chat doit attendre davantage. Les vecteurs sont calculés **dans le cluster**, par l'alias d'embedding du routeur de modèles.

**Pannes** : une panne de l'audit, de S3, de l'index, du registre ou de la forge est un refus fermé (503), audité sauf pour l'audit lui-même. Le même envoi refait après une coupure retrouve sa version par l'empreinte et rend 200, sans rien recompter.

## Contrat (aperçu)

Toutes les routes exigent un jeton. Une personne présente son jeton d'accès OIDC, vérifié par le service (signature RS256 par les clés du realm, émetteur, expiration, **audience du service**, type, client d'origine dans une liste fermée, groupes en liste). Un agent présentera un jeton de compte de service projeté, vérifié par `TokenReview`.

| Route | Qui | Rôle |
|---|---|---|
| `rechercher` | tous | morceaux validés lisibles par l'appelant |
| `proposer` | personnes, agents | un texte court, identifié par une clé stable : même clé et même contenu, reprise ; autre contenu, nouvelle version |
| `moi` | personnes | niveaux où la personne peut verser, si elle valide, bornes |
| `depots`, `depots/{lot}/fichiers`, `depots/{lot}/notes` | personnes qui versent | un lot, puis **un document par requête** (fichier en corps brut, chemin dans un en-tête encodé, version vue en paramètre) |
| `existants` | personnes | avant l'envoi : quels chemins existent déjà, avec leur dernière version, état, niveau et format (POST : les chemins ne passent ni dans une URL ni dans un journal) |
| `connaissances`, `connaissances/historique` | personnes | ses documents en dossiers, recherche par nom, filtre par état ; l'historique des versions d'un document |
| `a_valider`, `a_valider/compte`, `valider` | le valideur seul | une ligne par version en attente ; le compte pour « Quoi de neuf ? » ; la décision sur une version, ou sur **la liste vue** (contrôlée en entier avant d'écrire) |

**Ordre des contrôles au dépôt** : reprise (même contenu, quelle que soit la version annoncée), puis niveau (`niveau_different`), puis garde de version (`existe_deja` si un chemin existant arrive sans version vue, `version_changee` si la version vue n'est plus la dernière : un autre appareil est passé entre-temps), puis genre, puis bornes, puis format, **après l'extraction** : le format vient des octets.

**Motifs fermés** : `type`, `taille`, `illisible`, `vide`, `trop_long`, `nom`, `niveau`, `niveau_different`, `existe_deja`, `version_changee`, `deja_decide`, `depot`, `depot_plein`, `trop_en_attente`, `occupe`. L'interface ne traduit que ces mots, jamais un texte libre du service. Un seul mot par état dans le contrat : `en_attente`, `valide`, `refuse`.

## Validation

- **Une seule personne valide** : l'administrateur du foyer, désigné par son **identifiant technique** dans un réglage, **et** membre du groupe d'administration. Un autre membre de ce groupe ne valide rien. Un réglage vide ou mal formé arrête le service au démarrage.
- **Statut fixé par règle, jamais par le modèle** : ce que verse le valideur est validé d'office ; le reste attend, y compris ce que versent les autres administrateurs et les agents ; ce qui vient du web attendra toujours le [Tribunal Sémantique](../../../../docs/concepts/05-tribunal-semantique.md), même versé par le valideur. Seul l'état de validation décide de l'usage ; la confiance (0, puis 1 une fois validé) n'est qu'une trace.
- **Confidentialité devant le valideur** : pour les niveaux `personnel` et `intime` des autres, la liste à valider ne montre que l'auteur (nom affichable relevé dans son jeton au dépôt), le niveau, la date et le poids : ni nom de fichier, ni chemin, ni extrait. Le valideur peut valider ou refuser, sans pouvoir lire ensuite.
- **Décision rejouée** : sur un document déjà décidé, la même décision comme la décision contraire rendent `deja_decide`, avec le `statut` ; la page le compare à la décision envoyée (même valeur : succès ; valeur contraire : échec). `version_changee` couvre une version abandonnée ou dépassée. Sur une liste, une ligne déjà décidée avec la même décision est sautée, et une ligne décidée autrement rend `version_changee` pour toute la liste, sans rien écrire.

## Droits par niveau

Le filtre de droits est **ajouté par le service** à toute recherche dans l'index, puis chaque résultat est recontrôlé (état, droits, expiration). Le modèle ne peut pas l'élargir.

| Appelant | `public` | `famille` | `personnel` | `intime` | `admin` |
|---|---|---|---|---|---|
| administration | oui | oui | les siens | les siens | oui |
| responsables | oui | oui | les siens | les siens | — |
| protégés | oui | oui | les siens | les siens | — |
| invités | oui | — | — | — | — |
| agent | oui | — | — | — | — |

- On ne verse qu'à un niveau qu'on lit soi-même ; **les invités ne versent rien**.
- **Agents limités à `public`** tant que le répartiteur ne transmet pas la personne servie : sinon, un invité passant par un agent lirait `famille`. Ils n'ont pas non plus les routes de dépôt.

### Limites, à connaître

Les droits ci-dessus sont ceux **du service**, seule porte de lecture prévue. Ils ne protègent pas de qui administre les lieux eux-mêmes :
- **Administrateurs de la forge** : ils lisent tous les dépôts de niveau, `intime` compris. Dans l'installation de référence, c'est un choix assumé du responsable du foyer, qui sait qu'un agent d'administration de la forge en fait partie. Le service reste seul à détenir un jeton sur ces dépôts.
- **Miroir externe** : chaque dépôt de niveau a une copie privée chez un hébergeur Git externe (règle générale de l'installation : tout dépôt a son miroir). Tous les niveaux y sont, `intime` compris, lisibles par quiconque accède à ce compte, même les textes que la page présente comme lisibles par leur seul auteur. C'est aussi une copie hors de la maison, mais **des textes validés seulement** : les originaux (S3) et le registre (PostgreSQL) n'y sont pas, et la sauvegarde de l'installation reste à faire. Pour une installation qui ne veut pas de cette exposition : pas de miroir sur les dépôts `personnel` et `intime`, ou un miroir chiffré.
- **Administrateurs de la base et du stockage** : ils lisent le registre (chemins compris) et les originaux.
- **La confidentialité devant le valideur est une garantie de l'interface**, pas de l'administration technique : l'audit et le journal du pod portent l'identifiant de l'appelant, le poids et le nombre de morceaux de chaque dépôt, quel que soit son niveau. Qui lit ces journaux relie un document intime à son auteur, sans son contenu ni son nom.

## Audit en base

- Chaque écriture et chaque refus vont dans la table d'audit commune, en **deux lignes pour une écriture** : `tentative`, puis `ecrit` ou `echec_stockage` ; une décision de validation de même. Ils portent les identifiants, la version, l'issue, le poids et le nombre de morceaux, **jamais de contenu, de chemin ni de nom d'auteur**.
- **Un rôle PostgreSQL dédié, qui n'a que `INSERT`** sur cette table : ni lecture, ni modification, ni suppression, aucune autre table. Le service **vérifie ces droits à son démarrage** et refuse de démarrer avec un rôle plus large. Un service compromis peut donc ajouter des lignes, jamais effacer sa trace.
- Le registre a **son propre rôle**, propriétaire de son seul schéma, sans droit sur le reste de la base. Les tables du registre sont créées par le service au démarrage, par un script SQL versionné et rejouable.
- Les deux mots de passe sont générés sur place, rangés dans leur Secret **avant** le rôle, et seul un **vérificateur SCRAM**, calculé hors du serveur, part dans `CREATE ROLE` : même un ordre en erreur, que PostgreSQL journalise, n'y laisse aucun mot de passe.
- La table d'audit est rattachée au tenant de l'installation : son identifiant est un réglage du service (une seule ligne exigée). Supprimer le tenant effacerait tout l'audit, par cascade.
- Le journal applicatif ne porte que des identifiants et des nombres ; le client HTTP n'y écrit que ses avertissements.

## Extraction isolée (D2)

Lire un PDF ou un document bureautique, c'est exécuter un analyseur sur un fichier inconnu. Une première version le faisait dans un sous-processus du service : la relecture a montré que l'enfant, de même UID, lisait l'environnement de son parent (`/proc/<parent>/environ`), donc ses clés, le jeton du pod, et avait son réseau.

**L'extraction tourne donc dans un pod à part** (`sophia-extraction`), de la même image avec une autre commande :
- **ni Secret, ni variable sensible, ni jeton de compte de service, ni sortie réseau**, ni espace de processus partagé : une exécution de code dans l'analyseur n'y trouve rien à voler ni personne à joindre ;
- le service mémoire lui envoie les octets en HTTP ; c'est la seule entrée admise ;
- chaque fichier y est lu par un sous-processus `python -I` sans environnement, limité en mémoire (512 Mio) et en temps de calcul (60 s), sans fichier écrit ni processus ou fil créé, tué après 90 s ou si le client coupe ; deux à la fois au plus ;
- le **type vient des octets** (signature), jamais du nom, et se décide dans l'enfant, y compris la lecture du répertoire d'une archive (10 000 entrées au plus) ;
- la sortie est bornée dans l'enfant (200 000 caractères) et lue avec une borne par le parent ; un texte brut trop gros est refusé sans lancer d'enfant ;
- le parent ne relaie qu'un **motif fermé**, jamais un texte de l'enfant ;
- formats : texte et Markdown (UTF-8 strict), PDF avec du texte (500 pages au plus ; chiffré ou sans texte : refusé), documents bureautiques lus sans DTD ni entités. Les images viendront plus tard, par un modèle de vision ; leur transcription attendra toujours la validation.

**Épreuve en service**, lancée depuis le pod d'extraction : noms des variables présentes (aucune sensible, pour aucun processus visible), aucun jeton monté, puis des essais de connexion **par adresse, sans DNS** vers chaque service de l'installation (base vectorielle, service mémoire, fournisseur d'identité, routeur, PostgreSQL, S3, forge, API du cluster sur le nœud et par son Service, DNS) et vers Internet. Tout doit être injoignable ; les essais par nom ne prouvent rien seuls, le DNS échouant d'abord. Chaque résolution est bornée (5 s), pour que l'épreuve dure environ une minute.

## Bornes

50 Mio par fichier ; 200 documents et 500 Mio par lot ; une note de 50 000 caractères ; 200 000 caractères de texte par document ; 1 000 documents en attente par personne (sauf le valideur) ; 5 000 documents gardés par personne. Une nouvelle version ne compte pas comme un document de plus ; les versions remplacées, abandonnées et refusées ne comptent pas. Les bornes sont vérifiées sous un verrou par personne ; au plus deux envois traités à la fois, les autres attendent 15 s puis reçoivent `occupe`. Le chemin est assaini : relatif, normalisé, 240 caractères au plus, ni `..`, ni segment vide ou commençant par un point, ni caractère de contrôle, de direction ou de séparation de ligne.

## Réseau de la zone

Avec le service, la zone mémoire se ferme :
- **base vectorielle** : clé d'API, télémétrie coupée ; joignable par le seul service mémoire ;
- **refus par défaut en entrée et en sortie** dans le namespace, puis une règle par flux : embedding depuis le seul routeur de modèles ; service mémoire depuis le seul chat ; extraction depuis le seul service mémoire ; sorties du service vers le DNS, la base vectorielle, l'extraction, le routeur, le fournisseur d'identité (clés du realm), PostgreSQL, S3 et la forge ;
- en face, chaque destination admet **le seul pod du service** (règles d'entrée de PostgreSQL, du stockage, de la forge et du fournisseur d'identité) ;
- un **EgressFirewall** en seconde barrière : réseaux des pods et des Services du cluster seulement, puis refus. Aucune sortie vers un nœud ni vers Internet ; la vérification des jetons d'agents (`TokenReview`) ajoutera plus tard la seule API du cluster.

Avant de fermer, faire l'inventaire de ce qui joint la zone : dans l'installation de référence, les agents recevaient l'adresse de la base vectorielle et de l'embedding sans s'en servir, et une ingestion suspendue écrivait en direct dans la base vectorielle ; elle passera par le service.

## Mise en service (générique)

L'administrateur applique, une étape à la fois ; chaque contrôle est relu avant l'étape suivante. Règles constantes : **aucun secret à l'écran ni dans une variable du terminal** (générés et rangés par un tube), **une sauvegarde de chaque objet modifié** avant `oc diff`, puis `--dry-run=server`, puis `apply`.

| Étape | Geste | Contrôle attendu |
|---|---|---|
| 0 | Relevé de la table d'audit commune et des tenants | colonnes connues, un seul tenant |
| 1 | Image : ImageStreams, base Python **figée par empreinte**, build binaire du code commité seul, dépendances installées par empreintes | `Push successful` ; empreinte de l'image reportée dans les manifestes |
| 2 | Secrets : clé de la base vectorielle, clé du routeur limitée à l'alias d'embedding (avec un plafond de requêtes), réglage du valideur (identifiant technique lu dans le fournisseur d'identité) | longueurs attendues ; empreinte de la clé du routeur égale des deux côtés |
| 2 bis | PostgreSQL : réglage du tenant, Secrets puis rôles par vérificateur SCRAM (audit : `INSERT` seul ; registre : propriétaire de son schéma), schéma créé à son nom ; entrée réseau du service | **par le Service, donc avec mot de passe** : l'ajout d'audit passe (transaction annulée), lecture, modification, suppression et autres tables refusées ; le registre crée dans son schéma et rien ailleurs ; un mauvais mot de passe est refusé |
| 2 ter | S3 : **copie de sauvegarde de la configuration des identités, dans le cluster** ; Secret du service, puis identité tirée de lui, sans affichage ; entrée réseau ; relance du stockage (**coupe le service de fichiers environ une minute**) ; Job de création du seau (versionnement, politique, aucun cycle de vie) | concordance des empreintes des clés ; versionnement activé ; aucun cycle de vie ; politique posée |
| 2 quater | Forge : compte du service restreint, organisation privée, un dépôt par niveau, équipe d'écriture, jeton du service versé directement dans son Secret, jeton d'installation temporaire supprimé à la fin ; miroirs si l'installation en veut ; entrée réseau resserrée au pod du service | codes de l'API ; longueur du jeton ; dernier envoi des miroirs sans erreur |
| 3 | Clé d'API sur la base vectorielle (un redémarrage), puis index du registre dans la collection (document, lot, rang, version) | 401 sans clé ; index présents |
| 4 | Fournisseur d'identité : **audience du service** ajoutée aux jetons d'accès du client du chat ; entrée réseau du service | mappeur présent ; relance à blanc « non modifié » |
| 5 | Comptes, service, extraction, règles réseau, EgressFirewall | pods prêts sans redémarrage ; au démarrage, le service ouvre ses deux connexions à PostgreSQL, vérifie le rôle d'audit et crée le registre |
| 5 bis | **Épreuve de la politique du seau**, avec l'identité du service, depuis son pod, **avant tout dépôt** | sous `valide/` : suppression de version refusée, simple et groupée, marqueur de suppression refusé, témoin toujours là ; versionnement, cycle de vie et politique : refusés ; sous `attente/` : écrire et supprimer permis. Sinon : deux seaux |
| 5 ter | L'embedding reste joignable par le routeur | 200 |
| 6 | **Épreuve de l'isolement de l'extraction** (voir plus haut) | toutes les adresses injoignables ; « conforme » |

Ensuite : la copie de sauvegarde de la configuration S3 est supprimée ; le chat reçoit l'adresse du service et sa sortie vers lui (voir le [dashboard](../../apps/chat-interface/README.md#page--mémoire-)).

**Au premier dépôt réel**, l'administrateur relit, sans contenu, chemin ni identifiant de personne : les dernières lignes d'audit (`tentative`, puis `ecrit`), le registre (`en_attente`, original et texte présents, pas de commit) ; après validation, l'audit de la décision, le registre (`valide`, original présent, texte dans la forge, un identifiant de commit), le commit `document <id>, version 1` dans le dépôt du niveau, et le dernier envoi des miroirs.

**Retour arrière**, étape par étape, depuis les sauvegardes : règles réseau par `oc diff` puis `apply` de la sauvegarde ; identités S3 depuis la copie gardée dans le cluster (relance du stockage) ; rôles PostgreSQL par `DROP OWNED BY` puis `DROP ROLE` (**supprime tout le registre** ; l'audit déjà écrit reste) ; mappeur d'audience dans la console. À savoir : une copie miroir supprimée chez l'hébergeur externe ne se retrouve pas, et, hors du miroir, le texte validé n'existe que dans la forge ; l'original reste dans S3, d'où le texte se ré-extrait.

## Variables

| Variable | Rôle |
|---|---|
| `${SOPHIA_MEMORY_NAMESPACE}` | namespace de la zone mémoire (`sophia-memory`) |
| `${OIDC_ISSUER}`, `${JWKS_URL}` | émetteur public comparé au jeton ; clés du realm, par l'adresse interne |
| `${AZP_PERMIS}` | clients dont un jeton est accepté (le chat) |
| `${AGENTS}` | comptes de service reconnus, pour la façade des agents |
| `${VALIDEUR}` | identifiant technique du valideur (UUID) ; vide ou mal formé : refus de démarrer |
| `${QDRANT_URL}`, `${QDRANT_CLE}` | base vectorielle et sa clé (Secret) |
| `${EXTRACTION_URL}` | service d'extraction |
| `${LITELLM_URL}`, `${LITELLM_CLE}` | routeur de modèles et clé du service (Secret) |
| `${PG_HOST}`, `${PG_BASE}` | PostgreSQL et la base de la mémoire |
| `${PG_AUDIT_ROLE}`, `${PG_AUDIT_MOT_DE_PASSE}` | rôle d'audit (`INSERT` seul) |
| `${PG_REGISTRE_ROLE}`, `${PG_REGISTRE_MOT_DE_PASSE}` | rôle du registre |
| `${AUDIT_TENANT}` | tenant de l'installation (UUID) |
| `${S3_URL}`, `${S3_CLE}`, `${S3_SECRET}`, `${S3_CA}` | stockage objet, identité du service, autorité de certification des Services |
| `${MEMOIRE_SEAU}` | seau de la mémoire |
| `${FORGEJO_URL}`, `${FORGEJO_JETON}` | forge et jeton du compte du service |
| `${MEMOIRE_FORGEJO_ORG}` | organisation des dépôts de niveau |

## Banc

Tout le service est éprouvé en mémoire contre des faux (base vectorielle avec filtres, routeur, fournisseur d'identité avec clé RSA, `TokenReview`, audit, registre aux mêmes contraintes que le schéma, seau versionné à politique imitée, forge), avec les vrais clients S3 et forge, le vrai service d'extraction et son vrai sous-processus, et le SQL analysé par l'analyseur de PostgreSQL : 172 tests. **Les contrôles principaux sont éprouvés chacun par au moins une mutation** qui le fait échouer (une quarantaine), manifestes compris (Secret ou jeton dans l'extraction, sortie de l'extraction, refus par défaut, base vectorielle ouverte à un autre namespace). Le banc a trouvé, entre autres, que la table d'audit réelle refusait deux champs que l'application lui passait. PostgreSQL, S3 et la forge s'éprouvent à la mise en service.

## Ensuite

- Outil d'administration : **reconstruction de l'index** depuis le registre et les textes, et liste de ce qui reste sous `attente/` sans version en attente au registre.
- **Façade MCP** pour les agents, et outil mémoire du chat, sous le jeton de la personne.
- Agents au-delà de `public` quand le répartiteur transmettra la personne servie.
- Changement de niveau d'un document, par un geste dédié ; vrai renommage.
- Images, par le modèle de vision ; ingestion reconstruite, écrite par `proposer`.
- Graphe (dimension 5) nourri par le registre ; coffres de notes clonés depuis la forge.
