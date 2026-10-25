# Observabilité et réaction aux incidents

Cette fiche dit **qui voit quoi**, **qui reçoit une alarme** et **qui transforme une alarme en plan d'action**. Elle applique le motif de l'[Automation Déterministe](09-automation-deterministe.md) : collecte déterministe, diagnostic par le modèle, décision par des règles, exécution sous validation humaine.

---

## Problème

Une plateforme qui sert un foyer ou une organisation doit savoir quand elle va mal avant ses utilisateurs : un modèle qui sature, un pod tué faute de mémoire, une file de messages en échec, un workflow bloqué. Une métrique sans destinataire ne protège rien, et un agent libre qui « répare » sans contrôle est un risque de plus.

---

## Trois temps

### 1. Voir : l'observabilité minimale

| Élément | Ce qu'il apporte | État |
|---|---|---|
| Métrologie de la plateforme (Prometheus, Alertmanager fournis par OKD) | état du nœud et des composants du cluster | en service |
| Accès en lecture à la métrologie pour la supervision | requêtes, pointes sur plusieurs jours | en service |
| Surveillance des charges applicatives | métriques des services de SophIA : bus de messages, moteur de workflows, serveur d'inférence ; 15 jours de rétention | en service |
| Règles d'alerte | 27 règles : mémoire épuisée et redémarrages en boucle (répétées dans chaque namespace, une règle ne voyant que le sien), répartiteur indisponible, lettres mortes et alarmes du bus, workflows en échec, modèle local indisponible ou saturé | en service : chargées, aucune en erreur |
| Exporteur du nœud | la carte graphique (mémoire, utilisation, température, puissance) et les fichiers de métriques que déposent les scripts du nœud | en service |
| Garde-fou du filtre VPN en métrique | son code à chaque passage ; alertes : filtre retiré, vérification impossible, garde-fou muet | en service |

Coût mesuré : environ 0,2 cœur et un à deux gigaoctets de mémoire, sans toucher aux services. Recette : [`deploy/okd/monitoring/`](../../deploy/okd/monitoring/).

Traçabilité, déjà en place : l'historique de chaque workflow de délégation (30 jours), les événements datés publiés sur le bus par le répartiteur, le journal des requêtes du routeur de modèles.

### 2. Recevoir : l'alarme devient une demande

L'alerte part d'Alertmanager vers un **demandeur « alertes »** du répartiteur, comme n'importe quelle demande : identité prouvée, règles, quotas. Le répartiteur lance un **workflow « incident »**, un par groupe d'alertes. Les alertes de la plateforme OKD passent par le même circuit, par une route ajoutée en tête de son Alertmanager, qui laisse chaque alerte suivre ensuite son chemin d'avant. **Prévu** : la route est prête et non activée, le récepteur du répartiteur écrit et désactivé ; il ne fera d'abord que valider et journaliser.

### 3. Réagir : le workflow « incident »

1. **Collecte déterministe**, par une recette propre à chaque alerte : état des objets concernés, événements, journaux, requêtes de métrologie, par les fonctions de lecture de la supervision. Un filtre de secrets s'applique à tout ce qui est lu.
2. **Diagnostic** par le modèle local, en sortie contrainte. S'il manque une information, le modèle demande une autre lecture (un outil typé « lire X ») ; les règles la valident, la supervision la fait. **Deux tours au plus**, bornés par le code ; un plafond à revoir à l'usage.
3. **Plan**, proposé par le modèle : le pourquoi, les actions, les manifestes.
4. **Règles de gravité**, tirées de l'étiquette de l'alerte, jamais du modèle : elles fixent le destinataire et les actions automatiques permises. **Aucune au départ.**
5. **Notification de l'administrateur**, puis approbation du plan.
6. **Exécution** par l'agent de maintenance, **chaque commande approuvée**.

Toutes les étapes, de l'alarme à la dernière commande, sont dans l'historique du workflow, avec l'auteur authentifié de chaque approbation.

**Les fonctions de lecture de la supervision** tournent dans un pod à part, sans accès au réseau du nœud, sans session d'assistant ni jeton de la forge, joignable par le seul répartiteur, avec son propre compte en lecture seule sur le cluster et la métrologie. Cinq fonctions typées : lister, décrire, journaux, métrique, alertes. Ni Secrets ni ConfigMaps ; valeurs d'environnement masquées ; tailles bornées. **Prévu** : conçu et testé, non déployé.

---

## Ce que la fiche ne fait pas

- Aucun agent ne réagit seul à une alarme : la supervision lit et alerte, elle n'agit jamais.
- Aucune action automatique tant que des règles de gravité ne l'ont pas explicitement permise, action par action.
- Les validations passeront par l'interface de discussion, avec le jeton de la personne relayé et vérifié ; l'interface du moteur de workflows, réservée au groupe d'administration, reste le chemin de secours, et le seul aujourd'hui.

---

## Position dans l'architecture

- métrologie : composants fournis par OKD, et règles versionnées avec les manifestes ;
- réception et décision : le répartiteur (`sophia-core`), voir [Panthéon Agentique](08-pantheon-agentique.md) ;
- diagnostic et plan : le modèle local, par le même routeur que le reste (voir [Inférence et matériel](11-inference-materiel.md)).
