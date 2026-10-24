# Module Courses — documentation

## Ce que fait le module

- **Entrées** : les listes validées du module Cuisine (chacune importée une seule fois, puis marquée « commandée » en retour), une saisie libre, des **courses récurrentes** (tous les N jours ou certains jours de la semaine), des favoris.
- **Analyse puis choix** : le modèle comprend chaque ligne ; des règles choisissent le produit ; un produit nouveau choisi automatiquement porte l'étiquette « auto ».
- **Gestes** sur une liste : choisir, chercher autre chose, ajuster, retirer ou remettre une ligne, **valider** (par l'un ou l'autre adulte), marquer commandée, supprimer.
- **Prix et promotions réels**, lus dans le navigateur distant, recherche automatique en file d'attente.
- **Remplissage du vrai panier** sur demande, et **panier express** depuis la discussion (« ajoute du lait »), une question à la fois.
- **Prix de référence** pour la table des ingrédients du module Cuisine : outil MCP **en lecture** `prix_reference` (voir ci-dessous).

Prévu : plusieurs drives, comparaison entre enseignes, signal quand un site devient illisible.

## Architecture

```
module Cuisine ─MCP─┐
discussion ─────MCP─┼→ service (namespace des applications)   ──→ PostgreSQL partagé (schéma propre)
page de secours ────┘    │ LiteLLM (sophia-local, JSON strict)
                         └←── relevés ── extension du navigateur distant (sas, sortie Internet filtrée)
                                              └──→ site du drive (session ouverte par l'humain)
```

| Élément | Choix |
|---|---|
| Service | application Python et **oauth2-proxy** (SSO, groupe dédié aux adultes) ; serveur MCP interne ; un port réservé aux relevés, ouvert au seul pod du navigateur ; un schéma de 13 tables (produits, correspondances, listes, lignes, relevés de prix…) |
| Navigateur distant | dans le **sas** (`sophia-dmz`) : Chromium + Xvfb + noVNC, non root, sans jeton de compte de service, derrière le SSO et le VPN |
| Politiques du navigateur | liste blanche de domaines (le drive, son service anti-robot, le service) ; gestionnaire de mots de passe, de cartes et d'adresses **désactivés** |
| Extension | Manifest V3, **sans furtivité** : elle lit les données que la page a déjà reçues en ne gardant qu'une liste fermée de champs, et remplit le panier par l'appel normal du site |
| Session marchande | **les identifiants ne sont jamais connus** du service, du dépôt ni des journaux : l'humain se connecte lui-même dans le navigateur distant (code par e-mail, captcha) ; seul le cookie de session persiste, sur un volume local du nœud (compromis assumé) |
| Droit d'écrire | l'identité est **injectée par l'interface** (`sophia/injecte`) et comparée à la liste des adultes du foyer ; sur la page, elle vient de l'en-tête du proxy, et un formulaire venu d'un autre site est refusé (`Sec-Fetch-Site`) |
| Outils MCP | ≈ 25 : lecture (rechercher un produit, voir le panier, favoris, état d'un achat, courses récurrentes, prix de référence) et écriture (ajouter, importer les listes du module Cuisine, analyser, choisir, politique de marque, ajuster / retirer / remettre une ligne, valider, remplir le panier, acheter en express…) ; les outils express déclarent un délai de 60 s |
| Build | BuildConfigs Git ; un CronJob ne reconstruit une image que si ses fichiers ont changé |

## Règles : le modèle comprend, il ne choisit pas

Le modèle reçoit les lignes par lots de 20 et rend, en **JSON strict**, pour chacune : le produit générique, la quantité, l'unité, la marque demandée, les mots de recherche, 0 à 3 synonymes. Sa sortie est contrôlée : identifiants exacts, bornes, unité connue, **marque acceptée seulement si elle est écrite dans la ligne** ; un rejet motivé repart une fois au modèle, 3 réponses invalides au plus par ligne.

Le choix est **déterministe** :

1. candidats : un libellé est retenu s'il contient tous les mots d'une formulation ; la famille de produits retenue est d'abord celle des libellés qui commencent par un mot de la recherche, puis la plus nombreuse ;
2. politique de marque du foyer, par produit : exigée, préférée, marque de distributeur par défaut, premier prix ;
3. puis le moins de gaspillage, puis le **prix au kilo ou au litre**, puis le prix ; jamais de comparaison entre poids, volume et pièces ;
4. au plus 12 articles par ligne, alerte au-delà de 25 % d'arrondi.

## Prix de référence (`prix_reference`)

Outil MCP en lecture, appelé une fois par jour par le module Cuisine, 300 noms au plus. Pour chaque nom, **une seule** des trois clés `prix_kg`, `prix_litre` ou `prix_piece` (selon l'unité de vente), avec le prix de l'article, son libellé, son code-barres, la source et la date du relevé ; un nom sans prix connu ne rend pas de ligne.

- **Aucun appel au drive** : lecture en base des relevés déjà faits par le navigateur ;
- **prix normal**, sans promotion : une promotion passagère fausserait une référence ;
- **seulement les produits déjà retenus par le foyer** (choix mémorisé, sinon produit de la dernière liste validée) : pas de choix fait à la place du foyer pour un produit jamais acheté — le prix au kilo dépend de la marque prise ;
- noms rapprochés **sans modèle**, par les mêmes mots de recherche que les listes ; entre deux produits génériques, le choix le plus récent l'emporte ;
- poids, volume et pièces jamais convertis entre eux (1 l n'est pas 1 kg) ; le libellé rendu permet au module Cuisine de voir de quel produit vient un prix.

## Avant toute action sur le panier

- le panier du drive est **lu d'abord** ; illisible, rien n'est touché ;
- **jamais de baisse de quantité**, rien n'est envoyé pour un produit déjà présent en quantité suffisante ;
- chaque ajout est **vérifié** par la quantité constatée sur le site ; 3 à 6 s par article, 60 articles au plus, arrêt au premier refus ;
- jamais de créneau, de paiement ni de vidage du panier ;
- en express, « ajouté » n'est dit qu'après confirmation du site ;
- **aucun contournement anti-robot** : au premier défi, arrêt et signal ; seul un humain dans un vrai navigateur passe ;
- volume humain (quelques dizaines de recherches par semaine), usage personnel ; la page n'affiche ni lien profond ni image du site marchand ;
- champs personnels masqués dans les journaux de diagnostic.

## Mesures

- 134 tests (vrai PostgreSQL, vrai transport MCP, faux routeur de modèles, faux module Cuisine).
- ≈ 200 produits relevés pour une recherche courante (« lait ») ; ≈ 320 produits habituels du foyer.
- Exemple de choix : le pack de 20 à 1,69 €/l plutôt que le pack de 12 à 1,73 €/l.
- Achat express servi en ≈ 30 s ; navigateur limité à 1 CPU et 2 Gi.

## Leçons

- Un appel du site marchand « même quantité » a agi comme un **interrupteur** et retiré des produits du panier : d'où les règles « lire avant », « ne jamais baisser ».
- Laisser le modèle filtrer les candidats lui faisait rater le pack le moins cher : filtre déterministe.
- « La famille la plus nombreuse » seule a pris de la purée pour des tomates : d'abord les libellés qui commencent par le mot cherché.
- Le script de fond de l'extension restait en cache dans le profil conservé : changer la version de l'extension à chaque modification.
- Après un défi au démarrage, l'extension restait muette tant qu'aucune page n'était rouverte : une page est relancée toutes les 5 min.
- Une clé `ingress:` répétée dans un YAML efface la première, sans erreur.
- Un site qui change peut casser la lecture ou le remplissage : c'est assumé, la panne est **visible**, jamais un achat erroné silencieux.
- Une référence de prix hérite des choix passés : un produit retenu par erreur avant un correctif (une conserve pour un légume frais) donne un prix au kilo faux jusqu'au prochain bon choix. D'où le libellé rendu avec chaque prix.
