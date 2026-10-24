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
| Surveillance des charges applicatives | métriques des services de SophIA : bus de messages, moteur de workflows, serveur d'inférence | prévu |
| Règles d'alerte | mémoire épuisée, GPU, échecs de workflow, messages en lettres mortes, filtre d'accès VPN retiré par son garde-fou | prévu |

Coût visé : quelques dixièmes de cœur et un à deux gigaoctets de mémoire, sans toucher aux services.

Traçabilité, déjà en place : l'historique de chaque workflow de délégation (30 jours), les événements datés publiés sur le bus par le répartiteur, le journal des requêtes du routeur de modèles.

### 2. Recevoir : l'alarme devient une demande

L'alerte part d'Alertmanager vers un **demandeur « alertes »** du répartiteur, comme n'importe quelle demande : identité prouvée, règles, quotas. Le répartiteur lance un **workflow « incident »**. **Prévu.**

### 3. Réagir : le workflow « incident »

1. **Collecte déterministe** : état des objets concernés, événements, journaux, requêtes de métrologie, par des fonctions de lecture de la supervision. Un filtre de secrets s'applique à tout ce qui est lu.
2. **Diagnostic** par le modèle, en sortie contrainte. S'il manque une information, le modèle demande une autre lecture (un outil typé « lire X ») ; les règles la valident, la supervision la fait. La boucle est bornée par le code.
3. **Plan**, proposé par le modèle : le pourquoi, les actions, les manifestes.
4. **Règles de gravité** : elles fixent le destinataire et les actions automatiques permises. **Aucune au départ.**
5. **Notification de l'administrateur**, puis approbation du plan.
6. **Exécution** par l'agent de maintenance, **chaque commande approuvée**.

Toutes les étapes, de l'alarme à la dernière commande, sont dans l'historique du workflow, avec l'auteur authentifié de chaque approbation.

---

## Ce que la fiche ne fait pas

- Aucun agent ne réagit seul à une alarme : la supervision lit et alerte, elle n'agit jamais.
- Aucune action automatique tant que des règles de gravité ne l'ont pas explicitement permise, action par action.
- Les validations passent aujourd'hui par l'interface du moteur de workflows, réservée au groupe d'administration ; d'autres canaux (interface de discussion, messagerie) viendront par le même principe d'identité vérifiée.

---

## Position dans l'architecture

- métrologie : composants fournis par OKD, et règles versionnées avec les manifestes ;
- réception et décision : le répartiteur (`sophia-core`), voir [Panthéon Agentique](08-pantheon-agentique.md) ;
- diagnostic et plan : le modèle local, par le même routeur que le reste (voir [Inférence et matériel](11-inference-materiel.md)).
