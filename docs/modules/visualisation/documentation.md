# Module Visualisation — documentation

## Ce que fait le module

- **Vue d'ensemble** : en haut les demandeurs (l'interface, le planificateur, le workflow « incident »), au milieu la porte du répartiteur (règles, moteur de workflows, bus d'événements), en bas les exécutants ; les briques d'appui (inférence, mémoire, sas web, outils MCP) sont regroupées et se détaillent au clic. Une jauge montre les places du modèle local : celles du chat et celle des tâches de fond.
- **Relecture** : une exécution en diagramme de séquence, un couloir par acteur, étape par étape avec son journal.
- **Direct** : la même exécution en carte animée (namespaces en zones, étape en cours parcourue par un jeton) ou en colonnes à la manière d'une CI ; deux plateformes, la **cible** ou **aujourd'hui**, où l'exécution s'arrête au premier composant manquant ou en panne.
- **Reste à déployer** : les composants qui ne sont pas verts, rangés selon l'ordre de travail décidé, avec leurs dépendances.
- **Contrôle des miroirs** : toutes les heures, chaque dépôt de la forge doit avoir **un seul** miroir vers l'hébergeur externe, synchronisé depuis moins de 24 h et sans erreur. Un dépôt sans miroir figure dans une liste d'exceptions, avec sa raison ; certaines exceptions sont **interdites** (par exemple les transcripts des sessions d'assistance au code) : un miroir qui y apparaît est une faute.

Prévu : un volet **conformité** (RGPD, AI Act, ISO 27001 visée « certifiable », guide d'hygiène de l'ANSSI), d'abord un tableau d'état des lieux nourri par des sondes en lecture (règles réseau, quotas, Routes, images figées, privilèges, droits, garde-fou du VPN, sauvegardes, rétentions, alertes, veille des failles), puis un plan d'action et son suivi ; le flux d'événements en direct (V2).

## Règles

| Règle | Pourquoi |
|---|---|
| **Rien n'est supposé déployé sans avoir été mesuré** | l'état d'un composant vient de ses sondes : pods prêts, raison d'attente (`CrashLoopBackOff`, `ImagePullBackOff`), réplicas, `EndpointSlice` non vides, alertes en cours ; une source muette ou un refus donne « non mesuré », **jamais** « ok » ; un composant sans sonde reste « théorique » |
| **Lecture seule** | un compte de service qui lit les pods et la métrologie, **pas les Secrets** ; un compte du bus en lecture, qui refuse tout message dont l'émetteur n'est pas le répartiteur ; un jeton de la forge de portée « lecture des dépôts » seulement |
| **Une page ouverte ne coûte rien** | la collecte tourne en fond toutes les 30 secondes ; la page ne lit que le dernier résultat |
| **Une alerte n'est pas un bruit** | l'alerte des miroirs part après **deux** contrôles en échec de suite (deux poussées simultanées se gênent puis se résorbent), et **tout de suite** pour un miroir sur un dépôt interdit ; elle ne va qu'à l'administrateur, par la route Telegram générale de la métrologie (avertissements et alertes critiques, un message à l'ouverture, un autre à la résolution) |
| **Isolé des agents** | un namespace propre, sans aucune liaison de rôle vers un agent : un agent administrateur du namespace des applications aurait pu forger une session ou se servir du compte de lecture ; la dernière liaison de lecture dans ce namespace est supprimée, et la sonde de l'interface de discussion lit son namespace propre |

## Architecture

```
navigateur ─VPN─→ routeur ─→ [ oauth2-proxy │ application + collecteur ]   (namespace dédié)
                                                │  API du cluster (lecture, sans Secrets)
                                                │  métrologie (alertes, places du modèle local)
                                                │  bus d'événements (lecture, file temporaire)
                                                └─ forge (miroirs, jeton en lecture)
```

- Un seul conteneur sert la page et l'API (Starlette et uvicorn), derrière oauth2-proxy et le SSO, groupe d'administration ; la confiance d'oauth2-proxy dans les en-têtes `X-Forwarded-*`, est limitée au routeur.
- Namespace avec quota, valeurs par défaut et entrée fermée, sauf depuis le routeur et, sur le port d'oauth2-proxy, depuis le pod de l'interface ; sortie limitée aux sources lues.
- **Cockpit** ([contrat d'intégration](../README.md#intégrer-un-module-au-cockpit)) : `frame-ancestors` limité à l'interface sur toute réponse ; signal `sophia.pret` (identifiant `workflow`) après la première réponse de l'état ; affichée au centre du cockpit pour l'administrateur seul : en service, vérifiée sur ordinateur, reconnexion au téléphone en recette. L'ouverture depuis la discussion, pour l'administrateur, et la bascule sans clic par Sophia sont en service, en recette.
- **Jeton de la personne** : oauth2-proxy accepte le jeton relayé par le serveur de l'interface (`--skip-jwt-bearer-tokens`, audience de l'application ajoutée par un mappeur sur le client de l'interface, jamais `--extra-jwt-issuers`) ; le groupe d'administration reste exigé ; un jeton refusé reçoit 403, sans redirection (`--bearer-token-login-fallback=false`) : en service, 403 vérifié pour un jeton invalide.
- **Résumé pour « Quoi de neuf ? »** (`GET /api/resume`, déterministe) : commandes en attente de validation, exécutions en échec sur 24 h, alertes, chaîne d'alertes muette, miroirs. **Le texte d'une commande à valider n'est jamais recopié** : c'est une sortie du modèle, qui ne quitte pas l'écran d'approbation ; le motif d'un échec, écrit par le répartiteur, est repris, tronqué à 160 caractères. Les événements sont gardés en mémoire seulement, et oubliés au redémarrage. Appelée par l'interface : en service, vérifiée.
- Build depuis la forge interne par une **clé de déploiement en lecture seule** sur le seul dépôt, jamais par le jeton d'un administrateur de la forge.
- Métriques du contrôle des miroirs exposées pour la métrologie, avec une règle d'alerte du namespace.

## Pièges rencontrés

- **RabbitMQ 4.4** nomme les files créées par le serveur `amq_<32 hexadécimaux>`, et non plus `amq.gen-*` : les droits du compte de lecture doivent suivre, sinon sa file d'écoute est refusée.
- **Forgejo** ne liste les miroirs d'un dépôt qu'à un administrateur, et ne montre que les dépôts visibles du compte : le compte du contrôle est administrateur du site, mais sa puissance est bornée par son jeton (« lecture des dépôts » seulement), sans mot de passe connu ni clé SSH.
- Plusieurs miroirs vers la même adresse (créations répétées) se gênent et poussent chaque commit plusieurs fois : la règle « un seul miroir » en est née.
- **Un miroir en poussée écrase l'hébergeur externe** : une branche modifiée directement chez l'hébergeur a été remplacée par celle de la forge à la synchronisation suivante (tout a été récupéré). Règles retenues : on ne travaille que dans la forge ; chez l'hébergeur, la branche par défaut des dépôts publics est protégée contre la poussée forcée et la suppression (celle des dépôts privés ne peut pas l'être sans offre payante). Un contrôle de divergence entre la forge et l'hébergeur est proposé, pas construit.
