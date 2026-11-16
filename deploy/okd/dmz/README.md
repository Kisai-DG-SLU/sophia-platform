# Sas web — recherche et météo (`sophia-dmz`)

Première brique du [Sas Paranoïaque](../../../docs/concepts/04-sas-paranoiaque.md) : la plateforme cherche et lit le web **depuis une zone isolée**, qui sort sur Internet mais **ne peut joindre aucune adresse interne**. Un modèle trompé par une page ne peut donc pas faire lire l'intérieur du cluster.

```
interface (API des discussions) ─┐
agents ──────────────────────────┴→ sophia-web :8000 ─→ SearXNG :8080 ─→ moteurs de recherche
                                    │ MCP /mcp + REST     (métamoteur auto-hébergé)
                                    ├→ pages web : réduites en Markdown, sans script
                                    └→ données météo (prévisions jour par jour)
                    sortie : Internet 80/443 et DNS du cluster seulement
```

| Fichier | Contenu |
|---|---|
| `00-searxng.yaml` | métamoteur SearXNG : moteurs choisis, sortie JSON, instance privée (pas de limiteur), SafeSearch modéré, strict pour les utilisateurs protégés (par requête) |
| `01-sophia-web.yaml` | serveur MCP + REST `sophia-web` : ImageStream et BuildConfig dans le namespace des applications, Deployment (conteneurs `sophia-web` et `cook`) et Service dans le sas |
| `02-network.yaml` | NetworkPolicies : tout refusé par défaut ; sortie Internet 80/443 hors plages privées, DNS ; entrée de `sophia-web` depuis l'interface, les agents et le module Cuisine seulement, et de son port 8001 depuis le module Cuisine seul ; SearXNG joignable par `sophia-web` seulement |

## Le service `sophia-web`

Le code du service n'est pas fourni ; son contrat :

| Outil (MCP) | REST | Rôle |
|---|---|---|
| `web_search` | `POST /search` | résultats du métamoteur, **classés par fiabilité** (sources officielles et encyclopédiques d'abord) |
| `fetch_page` | `POST /fetch` | page réduite en Markdown, sans script ni contenu actif ; adresses internes et privées refusées |
| `weather_forecast` | `POST /weather` | prévisions jour par jour (jusqu'à 16 jours) depuis une source de **données** ouverte : les sites météo, rendus en JavaScript, ne sont pas lisibles |

Règles côté interface : la recherche est déclenchée par défaut pour toute demande d'information ; les sources sont citées ; `fetch_page` n'accepte qu'une adresse issue d'une recherche ou d'un message de la personne ; un échec d'outil est dit tel quel, sans cause inventée.

**Météo d'un lieu enregistré** (en service) : `weather_forecast` accepte des coordonnées avec un libellé, et saute alors le géocodage en ligne. L'interface envoie **le centre de la commune** du lieu, jamais l'adresse : la précision d'une prévision ne justifie pas d'envoyer l'emplacement d'un domicile à un service extérieur. En second filet, le service **arrondit lui-même les coordonnées à 0,01°** (environ 1 km) avant de les transmettre. La forme « Commune (code postal) » est aussi acceptée : le code postal est retiré avant le géocodage puis sert à vérifier la réponse, qui dit « introuvable » plutôt que de retenir un homonyme.

**Cache de secours de la météo** (en service ; Secret `sophia-web-cache`, clé `jeton`, même valeur côté interface, facultatif) :

- `PUT /cache/communes` : l'interface envoie la liste anonyme des communes de ses lieux enregistrés (libellé et coordonnées, sans nom de lieu, propriétaire ni adresse), au plus 50, arrondies à 0,01° par le service ; elle remplace la précédente ;
- la route exige un **jeton partagé**, comparé en temps constant : d'autres pods peuvent joindre le service, seule l'interface doit pouvoir remplacer la liste. Le jeton est dans un Secret créé par l'administrateur en un seul tube, sans affichage, et n'est jamais journalisé ;
- toutes les 3 heures, le service précharge J à J+3 pour chaque commune et garde la dernière réponse réussie, **en mémoire seulement** : rien ne relie une commune à une personne, ni sur disque ni dans un journal ;
- si la source en ligne échoue, la prévision en cache est rendue avec l'heure à laquelle elle a été obtenue, pour que la réponse le dise ;
- la base des fuseaux horaires est une dépendance figée, contrôlée au build.

**Téléchargement pour le module Cuisine** (en service) : une seconde application du même service, dans un conteneur à part du pod, sur le **port 8001**. Une NetworkPolicy (`sophia-web-cook-ingress`) n'y laisse entrer que le module Cuisine ; le port 8000, celui du chat et des agents, n'a pas ces routes, et aucun modèle ne les voit.

| REST (port 8001) | Rôle |
|---|---|
| `POST /telecharger` | télécharge un **PDF public** : reconnu à ses premiers octets (`%PDF-`), quel que soit le type annoncé ; 10 Mo au plus, lecture arrêtée au-delà |
| `POST /liens` | rend les liens d'une page HTML : 2 Mo au plus, lue sans rien exécuter, adresses absolues en http(s), 300 au plus |

- **Liste fermée de noms d'hôte exacts**, choisie par l'installation (ConfigMap `sophia-web-cook`, clé `hotes`, séparés par des virgules) ; absente ou vide, tout est refusé. Elle est contrôlée à **chaque saut** de redirection (3 au plus).
- Même garde réseau que `fetch_page` : https seulement, aucune adresse interne, connexion à l'adresse vérifiée.
- Aucun fichier écrit, rien au journal ; un refus porte un motif d'une liste fermée.

## Procédure (l'administrateur)

```bash
oc create secret generic searxng -n sophia-dmz --from-literal=SEARXNG_SECRET="$(openssl rand -hex 32)"
oc policy add-role-to-user system:image-puller system:serviceaccount:sophia-dmz:default -n sophia-apps
oc apply -f 02-network.yaml          # le sas fermé d'abord
oc apply -f 00-searxng.yaml
oc apply -f 01-sophia-web.yaml
oc start-build sophia-web -n sophia-apps --from-dir=<code de sophia-web> --follow
oc rollout status deploy/searxng deploy/sophia-web -n sophia-dmz
```

L'image est construite hors du sas et tirée par lui : **aucun identifiant de la forge dans la zone exposée au web**.

## Remarque

Un pod en `hostNetwork` passe à travers les NetworkPolicies. Tester l'isolement depuis un pod ordinaire, et ne jamais tester la robustesse sur un service en production.
