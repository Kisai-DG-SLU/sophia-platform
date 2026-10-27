# Modèles imposés par rôle, clés virtuelles par usage

Cette fiche dit **qui peut parler à quel modèle**, et comment la règle est tenue par le serveur et par le routeur de modèles (LiteLLM), jamais par le navigateur ni par le modèle. Elle applique le motif de l'[Automation Déterministe](09-automation-deterministe.md) : la décision est une règle, écrite dans une configuration versionnée.

---

## Problème

Dans un foyer ou une équipe, tous les comptes n'ont pas droit aux mêmes modèles : un enfant ou un invité doit rester sur le modèle local, un adulte peut choisir un modèle en ligne. Deux erreurs sont à éviter :

- une règle **dans le navigateur** : le sélecteur cache les modèles, mais une requête forgée passe ;
- **une seule clé pour tout** : chaque appelant (chat, voix, agents, pods de développement) voit alors tous les modèles, distants et payants compris, et la clé maître du routeur finit dans des pods qui n'ont rien à administrer.

---

## 1. Le modèle selon le rôle, côté serveur

Le serveur du chat lit une table **rôle → modèles permis** (`SOPHIA_MODELS_BY_ROLE`, configuration versionnée) :

| Rôle | Modèles permis (par défaut) |
|---|---|
| enfants (groupe protégé) | le modèle local seulement |
| invités | le modèle local seulement |
| compte sans rôle connu | traité comme un invité |
| adultes | sans restriction |

- **Refus explicite** : un modèle hors liste envoyé par le navigateur reçoit un **403** (« Modèle non autorisé pour ce compte : … seulement »), et rien ne part vers le routeur. Jamais de remplacement silencieux : la personne saurait mal quel modèle a répondu.
- **Modèle par défaut** ramené au premier modèle permis : un parent a pu choisir un modèle en ligne pour le profil d'un enfant avant la règle. Enregistrer un modèle hors liste dans un profil répond 400.
- **Appels internes** (analyse d'intention, reformulation, résumé, titre) : ils prennent le modèle déjà contrôlé. Les tâches de fond vont sur l'alias de fond du modèle local ; photos et questions sur une sélection restent toujours sur le modèle local.
- **Interface** : le profil expose les modèles permis ; le sélecteur et la fenêtre de profil ne proposent qu'eux. C'est un confort, pas la garde.
- **Même famille de règle** pour le contenu des documents lu par un outil : il ne va qu'aux modèles d'une liste fermée de modèles locaux (`SOPHIA_MODELES_CONTENU`), et il est retiré de tout appel à un autre modèle (voir [Relais de l'identité](12-relais-identite.md)).

---

## 2. Une clé virtuelle par usage

Le routeur de modèles délivre des **clés virtuelles** : chacune a une **liste de modèles fermée** et ses propres limites (requêtes par minute, budget). La règle est alors tenue par le routeur, quelle que soit la requête.

| Usage | Modèles | Limites |
|---|---|---|
| chat | les modèles du chat | débit et budget du chat |
| voix du chat | reconnaissance et synthèse vocales seulement | débit propre (300 requêtes par minute), sans budget : modèles locaux |
| chaque agent (`agent-<nom>`) | l'alias de fond du modèle local et l'embedding | 120 requêtes par minute, sans budget : la liste fermée empêche tout appel payant |
| chaque projet de développement (prévu) | le modèle local seul : l'alias de fond et l'embedding, comme les agents | débit borné, sans budget : la liste fermée empêche tout appel payant |
| chaque application (cuisine, courses…) | ses seuls modèles | les siennes |

### La voix : la clé posée par nginx

Les routes audio vont de nginx au routeur **sans passer par l'API du chat** : ce sont des formulaires multipart, que l'API n'a pas à analyser. nginx pose la clé de la voix (`LITELLM_AUDIO_API_KEY`) **sur ces deux routes seulement**, et écrase toute clé envoyée par le navigateur. Une requête vers un autre modèle avec cette clé est refusée par le routeur lui-même : la règle tient **sans lire le formulaire**.

Pourquoi une clé à part : une transcription plus une synthèse par phrase, pour plusieurs personnes à la fois, dépassent vite le débit d'une clé de chat. Sans clé de voix, le chat reprend celle du pod et l'annonce au démarrage.

---

## 3. La clé maître ne sort plus de la passerelle

La clé maître du routeur sert à l'administrer : créer des clés, changer des budgets. Elle ne doit être lue que par le routeur lui-même.

1. **Une clé virtuelle pour chaque appelant** qui lisait la clé maître (agents, pods de développement), rangée dans son propre Secret. Le contrôle `/key/info` le prouve : il répond un alias pour une clé virtuelle, et 404 pour la clé maître.
2. **Le sel fixé avant le renouvellement** : le routeur chiffre ce qu'il garde en base avec `LITELLM_SALT_KEY`, qui vaut par défaut la clé maître. On le pose donc à la **valeur actuelle** de la clé maître, sans l'afficher ; **il ne change plus jamais**. Sinon, changer la clé maître rendrait illisible ce qui est déjà chiffré.
3. **Retrait** de la clé maître des Secrets des appelants.
4. **Nouvelle clé maître**, tirée au hasard et jamais affichée, posée par un patch lu sur l'entrée standard, après sauvegarde de l'ancienne hors de tout dépôt. Sel, retrait et renouvellement passent en **un seul redémarrage** du routeur.
5. **Contrôles** : la liste des clés répond avec la nouvelle clé maître ; chaque agent répond ; chaque pod de développement montre son propre alias.

Pour que ce redémarrage ne coupe rien, le routeur a des **sondes** (readiness sur `/health/readiness`, liveness sur `/health/liveliness`, délai de 3 secondes, car la readiness interroge la base) et une stratégie **RollingUpdate** (`maxSurge: 1`, `maxUnavailable: 0`) : l'ancien pod sert jusqu'à ce que le nouveau soit prêt. Le quota du namespace admet ce second pod. Sans sonde, le pod était déclaré prêt une trentaine de secondes avant d'écouter, d'où une coupure.

---

## 4. L'outil : `create-virtual-key.py`

Un script lancé dans le pod du routeur, qui n'affiche jamais une clé ([`deploy/okd/core/litellm/create-virtual-key.py`](../../deploy/okd/core/litellm/create-virtual-key.py)) ; il ne modifie ni ne supprime jamais une clé existante :

- `--modeles a,b --rpm N` : liste explicite et débit, sans budget ; chaque modèle doit exister dans le routeur ; `*` est refusé ;
- `--comme <alias>` : reprend les modèles et les limites (débit, budget) d'une clé existante, `--sans x,y` en retire, jamais n'en ajoute ; une référence en « tout modèle » est refusée ;
- `--dry-run` : montre la clé à créer, sans rien créer ; un alias déjà pris arrête le script ;
- `--eval VAR` : rend la clé dans une variable du shell, qui part ensuite dans un Secret par un tube (`printf … | oc set data … --from-file=…=/dev/stdin`), jamais en argument ;
- `--info <alias>` : modèles, limites, dépense, et une **empreinte** de la clé (début de son SHA-256), à comparer à l'empreinte de la valeur du Secret pour vérifier sans rien afficher.

Essayé contre un faux routeur : à blanc, modèle inconnu, limite absente, options incompatibles, création, alias déjà pris, `--info`.

---

## État

| Élément | État |
|---|---|
| Modèles par rôle dans le serveur du chat, sélecteur réduit | en service |
| Clé de la voix posée par nginx | en service |
| Une clé par agent ; clé maître retirée des appelants et renouvelée | en service |
| Sondes et RollingUpdate du routeur ([`deployment.yaml`](../../deploy/okd/core/litellm/deployment.yaml)) | en service |
| Clé d'un projet de développement, limitée au modèle local : créée une fois par le workflow qui crée le cluster du projet, au moyen d'un compte de gestion qui ne peut appeler aucun modèle, dans une équipe du routeur limitée au modèle local ; aucun script lancé à la main | prévu (éprouvé avec le premier cluster de projet) |

---

## Ce que la fiche ne fait pas

- Le navigateur ne décide d'aucun modèle : il propose, le serveur refuse ou laisse passer.
- Aucune clé ne voit « tous les modèles ».
- La clé maître n'est lue par aucun pod hors du routeur.

---

## Position dans l'architecture

- routeur de modèles : `sophia-core` ([`deploy/okd/core/`](../../deploy/okd/core/)) ;
- interface de discussion : `sophia-interface` ([`deploy/okd/apps/chat-interface/`](../../deploy/okd/apps/chat-interface/)) ;
- agents : [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/) ;
- partage du modèle local : [Inférence et matériel](11-inference-materiel.md) ;
- protections d'ensemble : [Modèle de sécurité](../security.md).
