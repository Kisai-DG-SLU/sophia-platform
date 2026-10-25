# Inférence et matériel

Cette fiche dit **quel modèle sert qui**, **sur quel matériel**, et comment une seule carte graphique se partage entre les usages sans que la discussion en souffre.

---

## Principes

- **100 % local.** La cible a toujours été une inférence entièrement locale. Un modèle distant n'est qu'une dérogation de développement, choisie par routage, jamais une dépendance.
- **Une famille de tâches par carte.** Modèle de langage, embedding, voix et vision : chaque carte porte ses propres modèles, ce qui isole les charges. Aucun modèle n'est réparti sur plusieurs cartes.
- **Un routeur pour tous.** Interface, modules et agents appellent les modèles par des alias du routeur (LiteLLM), jamais un serveur directement. Changer de modèle est un changement de routage.
- **Le modèle choisi par tâche.** Routage, classement et extraction en sortie contrainte n'exigent pas le même modèle que le découpage d'un objectif complexe.

---

## Aujourd'hui

| Usage | Où | État |
|---|---|---|
| Modèle généraliste (texte et vision), 9 milliards de paramètres, quantifié | la seule carte graphique (16 Go) ; 4 discussions en parallèle sur un contexte partagé | en service |
| Embedding | CPU, dans la zone mémoire | en service |
| Voix (reconnaissance, synthèse) et génération d'images | CPU, sans accès réseau | en service |
| Interface, modules, école | modèle local par défaut | en service |
| Agents du panthéon | le modèle local, par l'alias de fond ; une clé du routeur par agent, limitée à cet alias et à l'embedding | en service |

Le serveur de référence accueille trois cartes : la cible est une carte par famille de tâches. Une deuxième ou une troisième carte servira l'embedding, la voix et la vision, **pas un second modèle généraliste**.

---

## Partage de la carte et priorité à la discussion

Un seul modèle généraliste sert l'interface, les modules, les agents et le planificateur. Sans règle, une tâche de fond peut prendre les emplacements d'une discussion. Le serveur garde ses 4 emplacements, fixés à son démarrage ; **la borne est tenue chez les clients** :

| Plage | Discussion (bornée par l'interface) | Alias de fond (tâches des modules, sans flux) | Missions des agents (bornées par le répartiteur) |
|---|---|---|---|
| Jour | 2 | 1 | 1 |
| 3 h à 7 h | 1 | 1 | 2 |

- **Deux alias sur le même serveur** (en service). L'alias principal reste à la discussion, à l'école et aux usages interactifs ; l'école n'attend jamais. L'alias « de fond », limité à une requête à la fois, sert les agents et les tâches de fond des modules (génération de recettes, listes de courses, titres et résumés de discussion), avec repli sur l'alias principal tant qu'il n'est pas ouvert à la clé d'un module. **Limite** : en flux, le verrou du routeur est relâché à la première réponse et ne couvre pas la génération ; il ne vaut que pour les appels sans flux.
- **La discussion bornée par l'interface** (en service) : 2 emplacements le jour, 1 la nuit ; une discussion de plus attend une minute au plus.
- **Les missions bornées par le répartiteur** : une mission à la fois par exécutant, et une ou deux missions sur l'alias de fond selon l'heure. Écrit et testé, en service au prochain build du répartiteur. Rien n'est interrompu au changement de plage : à 7 h, une mission en cours peut faire attendre la discussion jusqu'à sa fin.
- **Fenêtre de contexte des agents** fixée à 64 000 tokens : le serveur local ne publie pas sa fenêtre, et l'agent se repliait sur 256 000, prenant la réserve de la discussion.
- **Petites décisions** : avec un modèle local modeste, les plans sont découpés en décisions à sortie contrainte, encadrées par des règles (voir [Automation Déterministe](09-automation-deterministe.md)).

Un piège du passage au local : un modèle distant acceptait deux messages `system` à la suite, le gabarit de chat du modèle local les refuse (voir [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/README.md)).

---

## Choix du modèle

| Option | Effet | État |
|---|---|---|
| Garder le modèle actuel pour tous les rôles, avec l'alias « de fond » | aucun coût supplémentaire ; recettes par rôle à faire | en service (premier pas) |
| Modèle à experts (35 milliards de paramètres, 3 actifs) en hybride carte + mémoire vive, à la place du modèle actuel | meilleur raisonnement attendu ; 12 à 16 cœurs pendant la génération et 25 à 40 Go de mémoire, en concurrence directe avec la voix, les images et la bureautique | à mesurer, pointe CPU comprise, avant décision |
| Second modèle sur CPU pour les agents | au moins 16 cœurs en permanence | écarté : le CPU n'a pas cette marge |

---

## Budget de ressources

La mémoire vive a de la marge, **le CPU non**. La consommation réelle est faible (quelques cœurs en temps normal, une pointe à 11 cœurs sur une semaine), mais les limites déclarées dépassaient la capacité du nœud, et les charges à venir (bureautique, modèle hybride, réindexation de la mémoire) sont lourdes. **En service** (recette : [`deploy/okd/cluster/`](../../deploy/okd/cluster/)) :

- **Priorités, sans préemption** : un **socle** au-dessus de tout (le pod de lecture du cluster, qui permet de comprendre une panne, et la forge Git, d'où partent tous les déploiements : jamais évincés), puis discussion et modèle de langage > voix > répartiteur et agents > bureautique > images > développement et clusters enfants. Seul le serveur du modèle de langage garde le droit de préempter ;
- **quotas** sur les limites, par namespace, et des demandes et limites explicites pour chaque conteneur ; le quota du namespace des agents est posé, après la classe du pod de lecture ;
- génération d'images limitée à 8 cœurs.

**Leçon** : une classe de priorité ne protège que les pods qui déclarent leurs demandes. Un pod sans demande est le premier évincé sous pression mémoire, quelle que soit sa classe : chaque pod du socle demande au moins son pic mesuré.

Prévu : les travaux lourds la nuit (réindexation, conversions).

---

Voir aussi : [Infrastructure POC](../../deploy/infrastructure.md) · [Inférence locale](../../deploy/okd/inference/README.md) · [Observabilité](10-observabilite.md)
