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
| Agents du panthéon | encore configurés sur des modèles distants, pour les essais | à passer en local (prévu) |

Le serveur de référence accueille trois cartes : la cible est une carte par famille de tâches. Une deuxième ou une troisième carte servira l'embedding, la voix et la vision, **pas un second modèle généraliste**.

---

## Partage de la carte et priorité à la discussion

Un seul modèle généraliste sert l'interface, les modules, les agents et le planificateur. Sans règle, une tâche de fond peut prendre les emplacements d'une discussion. **Prévu :**

- **Deux alias sur le même serveur.** L'alias principal reste à la discussion, à l'école et aux usages interactifs. Un alias « de fond », limité à une requête à la fois, sert les agents, le planificateur et les tâches de fond des modules : la discussion garde trois emplacements de fait.
- **Concurrence bornée par le répartiteur** : une mission à la fois au départ.
- **Petites décisions** : avec un modèle local modeste, les plans sont découpés en décisions à sortie contrainte, encadrées par des règles (voir [Automation Déterministe](09-automation-deterministe.md)).

---

## Choix du modèle

| Option | Effet | État |
|---|---|---|
| Garder le modèle actuel pour tous les rôles, avec l'alias « de fond » | aucun coût supplémentaire ; recettes par rôle à faire | prévu (premier pas) |
| Modèle à experts (35 milliards de paramètres, 3 actifs) en hybride carte + mémoire vive, à la place du modèle actuel | meilleur raisonnement attendu ; 12 à 16 cœurs pendant la génération et 25 à 40 Go de mémoire, en concurrence directe avec la voix, les images et la bureautique | à mesurer, pointe CPU comprise, avant décision |
| Second modèle sur CPU pour les agents | au moins 16 cœurs en permanence | écarté : le CPU n'a pas cette marge |

---

## Budget de ressources

La mémoire vive a de la marge, **le CPU non**. La consommation réelle est faible (quelques cœurs en temps normal), mais les limites déclarées dépassent la capacité du nœud, et les charges à venir (bureautique, modèle hybride, réindexation de la mémoire) sont lourdes. **Prévu :**

- **Priorités** : discussion et modèle de langage > voix > répartiteur et agents > bureautique > images > développement et clusters enfants ;
- **quotas** par namespace, et demandes et limites pour chaque agent ;
- génération d'images limitée à 8 cœurs ;
- travaux lourds la nuit (réindexation, conversions).

---

Voir aussi : [Infrastructure POC](../../deploy/infrastructure.md) · [Inférence locale](../../deploy/okd/inference/README.md) · [Observabilité](10-observabilite.md)
