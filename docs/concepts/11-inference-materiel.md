# Inférence et matériel

Cette fiche dit **quel modèle sert qui**, **sur quel matériel**, et comment une seule carte graphique se partage aujourd'hui entre les usages sans que la discussion en souffre.

---

## Principes

- **100 % local.** La cible a toujours été une inférence entièrement locale. Un modèle distant n'est qu'une dérogation de développement, choisie par routage, jamais une dépendance.
- **Le modèle de langage réparti par couches, la perception à part.** Le modèle de langage peut s'étendre sur plusieurs cartes, **par couches** : à chaque token, seules de petites données passent d'une carte à l'autre, ce que le bus PCIe tient sans peine. Le *tensor parallel* est écarté : il exige un lien direct entre les cartes (NVLink). La perception, l'embedding, le graphe et les petits modèles ont leur propre carte, ce qui isole leurs charges.
- **Un routeur pour tous.** Interface, modules et agents appellent les modèles par des alias du routeur (LiteLLM), jamais un serveur directement. Changer de modèle est un changement de routage.
- **Le modèle choisi par tâche.** Routage, classement et extraction en sortie contrainte n'exigent pas le même modèle que le découpage d'un objectif complexe.

---

## Aujourd'hui

| Usage | Où | État |
|---|---|---|
| Modèle généraliste (texte et vision), à experts : 35 milliards de paramètres dont 3 actifs, quantifié | la seule carte graphique (16 Go, PCIe 3.0 x8) ; les experts de 34 couches restent en mémoire vive, calculés par 20 cœurs réservés ; 8 discussions en parallèle sur un contexte partagé | en service |
| Embedding | CPU, dans la zone mémoire | en service |
| Voix (reconnaissance, synthèse) et génération d'images | CPU, sans accès réseau | en service |
| Interface, modules, école | modèle local par défaut | en service |
| Agents du panthéon | le modèle local, par l'alias de fond ; une clé du routeur par agent, limitée à cet alias et à l'embedding | en service |

Le serveur de référence accueille trois cartes. **Cible, temps 1** : les cartes 1 et 2 portent ensemble le modèle de langage, réparti par couches (discussion, école, agents) ; la carte 3 porte la perception (vision, OCR, voix), l'embedding, le graphe et les petits modèles. Avec une seule carte, le bus est chargé par la copie des experts gardés en mémoire vive (environ 14,7 Go par paquet d'invite), et le premier mot peut attendre 7,8 s quand six demandes arrivent ensemble. Sur deux cartes, presque tout le modèle tient en mémoire graphique, et ce trafic disparaît pour l'essentiel. Les gains sont à prouver par un banc avec le mélange réel (discussions, école, agents).

---

## Temps 2 : une machine d'inférence derrière le routeur

Le temps 1, les trois cartes A2 dans le serveur, reste la cible en cours. Le temps 2, à l'étude et sans décision d'achat, ajoute un **DGX Spark** : puce GB10, 128 Go de mémoire unifiée, partagée entre le processeur et le calcul graphique, débit mémoire d'environ 273 Go/s.

- **Hors du serveur, derrière le routeur.** Le DGX Spark est une machine à part, jointe par le réseau derrière LiteLLM. Seules la requête et la réponse passent par le réseau, comme pour un modèle distant, mais en local : le débit du lien n'est pas un frein.
- **Deux réserves de calcul** :

| Réserve | Matériel | Usages |
|---|---|---|
| DGX Spark | la machine entière | discussion et école avec un modèle plus gros, modèle de code, vision avancée, modèles du monde au besoin (modèles qui prédisent l'évolution d'une scène) |
| Cartes A2 | cartes 1 et 2, le modèle actuel réparti par couches | agents et tâches de fond ; secours de la discussion par les replis du routeur si le DGX Spark ne répond pas |
| Cartes A2 | carte 3 | voix, embedding, lecture de documents |

- **Les alias ne changent pas, seul le routage change.** Interface, modules et agents gardent leurs alias ; le routeur les dirige vers le DGX Spark ou vers les A2.
- **L'embedding ne bouge pas** : changer de modèle d'embedding imposerait de réindexer toute la mémoire.

**Limites** :

- **calcul et débit partagés** : les modèles servis ensemble sur le DGX Spark se partagent son calcul et ses 273 Go/s ; plusieurs modèles chargés ne font pas plusieurs modèles rapides en même temps ;
- **mémoire partagée avec le système** : 110 à 115 Go réellement utiles sur les 128 ;
- **machine ARM, raccordée par le réseau** : les images des serveurs de modèles doivent exister pour cette architecture ; port 10 Gb/s à vérifier côté serveur ;
- **consommation** de 170 à 240 W ;
- **pas de point d'accès Internet** : la machine n'est jointe que par un point d'entrée déclaré dans le namespace d'inférence (`sophia-inference`), comme les autres serveurs de modèles.

---

## Partage de la carte et priorité à la discussion

Un seul modèle généraliste sert l'interface, les modules, les agents et le planificateur. Sans règle, une tâche de fond peut prendre les emplacements d'une discussion. Le serveur a 8 emplacements, fixés à son démarrage ; **la borne est tenue chez les clients** :

| Plage | Discussion (bornée par l'interface) | Alias de fond (tâches des modules, sans flux) | Missions des agents (bornées par le répartiteur) |
|---|---|---|---|
| Jour | 4 | 1 | 1 |
| 3 h à 7 h | 1 | 1 | 2 |

L'école et les autres usages interactifs prennent le reste des 8 emplacements.

- **Deux alias sur le même serveur** (en service). L'alias principal reste à la discussion, à l'école et aux usages interactifs ; l'école n'attend jamais. L'alias « de fond », limité à une requête à la fois, sert les agents et les tâches de fond des modules (génération de recettes, listes de courses, titres et résumés de discussion), avec repli sur l'alias principal tant qu'il n'est pas ouvert à la clé d'un module. **Limite** : en flux, le verrou du routeur est relâché à la première réponse et ne couvre pas la génération ; il ne vaut que pour les appels sans flux.
- **La discussion bornée par l'interface** (en service) : 4 emplacements le jour, 1 de 3 h à 7 h ; une discussion de plus attend une minute au plus.
- **Les missions bornées par le répartiteur** : une mission à la fois par exécutant, et une ou deux missions sur l'alias de fond selon l'heure. En service. Rien n'est interrompu au changement de plage : à 7 h, une mission en cours peut faire attendre la discussion jusqu'à sa fin.
- **Fenêtre de contexte des agents** fixée à 64 000 tokens : le serveur local ne publie pas sa fenêtre, et l'agent se repliait sur 256 000, prenant la réserve de la discussion.
- **Petites décisions** : avec un modèle local modeste, les plans sont découpés en décisions à sortie contrainte, encadrées par des règles (voir [Automation Déterministe](09-automation-deterministe.md)).

Un piège du passage au local : un modèle distant acceptait deux messages `system` à la suite, le gabarit de chat du modèle local les refuse (voir [`deploy/okd/hermes-system/`](../../deploy/okd/hermes-system/README.md)).

---

## Choix du modèle

| Option | Effet | État |
|---|---|---|
| Un seul modèle pour tous les rôles, avec l'alias « de fond » | aucun coût supplémentaire ; recettes par rôle à faire | en service |
| Modèle à experts (35 milliards de paramètres, 3 actifs) en hybride carte + mémoire vive, à la place du modèle de 9 milliards | qualité 80/85 contre 74/85 aux séries des services ; 20 cœurs réservés et 40 Gi de mémoire ; premier mot jusqu'à 7,8 s quand six demandes arrivent ensemble | en service, après un banc qui a mesuré la pointe CPU ; le modèle de 9 milliards reste disponible pour le retour arrière |
| Second modèle sur CPU pour les agents | au moins 16 cœurs en permanence | écarté : le CPU n'a pas cette marge |
| Modèle de langage réparti par couches sur deux cartes | presque tout le modèle en mémoire graphique : presque plus de copie des experts par le bus, premier mot à plusieurs attendu bien plus court | cible, temps 1 ; à prouver par un banc avec le mélange réel |
| Machine à mémoire unifiée (DGX Spark, 128 Go) hors du serveur, derrière le routeur | modèles plus gros, et plusieurs modèles chargés ensemble ; calcul et débit partagés entre eux ; les A2 passent aux agents, au secours et à la perception | temps 2, à l'étude |

---

## Budget de ressources

La mémoire vive a de la marge, **le CPU non**. La consommation réelle est faible (quelques cœurs en temps normal, une pointe à 11 cœurs sur une semaine), mais les limites déclarées dépassaient la capacité du nœud, et les charges nouvelles (bureautique, modèle hybride, réindexation de la mémoire) sont lourdes. Le modèle hybride réserve à lui seul 20 cœurs, une socket du nœud de référence. **En service** (recette : [`deploy/okd/cluster/`](../../deploy/okd/cluster/)) :

- **Priorités, sans préemption** : un **socle** au-dessus de tout (le pod de lecture du cluster, qui permet de comprendre une panne, et la forge Git, d'où partent tous les déploiements : jamais évincés), puis discussion et modèle de langage > voix > répartiteur et agents > bureautique > images > développement et clusters enfants. Seul le serveur du modèle de langage garde le droit de préempter ;
- **quotas** sur les limites, par namespace, et des demandes et limites explicites pour chaque conteneur ; le quota du namespace des agents est posé, après la classe du pod de lecture ;
- génération d'images limitée à 8 cœurs.

**Leçon** : une classe de priorité ne protège que les pods qui déclarent leurs demandes. Un pod sans demande est le premier évincé sous pression mémoire, quelle que soit sa classe : chaque pod du socle demande au moins son pic mesuré.

Prévu : les travaux lourds la nuit (réindexation, conversions).

---

Voir aussi : [Infrastructure POC](../../deploy/infrastructure.md) · [Inférence locale](../../deploy/okd/inference/README.md) · [Observabilité](10-observabilite.md)
