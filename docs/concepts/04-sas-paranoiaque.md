# Le Sas Paranoïaque

Le **Sas Paranoïaque** est un mécanisme d'isolation destiné à interagir avec Internet tout en protégeant l'infrastructure interne de SophIA.

Son objectif est simple : consommer de l'information externe sans exposer l'infrastructure ni contaminer la base de connaissance.

---

## Problème

L'utilisation d'Internet par des agents IA pose plusieurs risques :

- fuite de données via les requêtes
- traçage des utilisateurs
- récupération de contenus malveillants
- ingestion de contenus générés par IA (AI sludge)
- injection de scripts ou de payloads dans le pipeline de données

Dans un système souverain, l'accès direct au web par les agents n'est pas acceptable.

---

## Principe

Le Sas Paranoïaque agit comme une zone tampon isolée (DMZ) entre Internet et le reste du système.

Les agents n'accèdent jamais directement au web. Le flux est le suivant :

Agent vers Sas Paranoïaque vers Internet, puis nettoyage, validation, et transmission au système.

---

## Fonctionnement

Le Sas Paranoïaque applique plusieurs mécanismes.

### Isolation

Les requêtes web sont exécutées dans des jobs éphémères et isolés. Ces jobs sont détruits après usage.

### Obfuscation

Pour limiter le traçage et l'analyse des requêtes :

- utilisation de proxies
- génération de requêtes leurres (shadow queries)
- rotation d'identité réseau

Exemple : 1 requête utile pour 3 à 4 requêtes leurres.

### Neutralisation du contenu

Les pages récupérées sont détruites puis reconstruites :

- suppression complète du JavaScript
- suppression des traqueurs
- suppression des scripts dynamiques

Le résultat final est converti en Markdown brut.

### Transmission contrôlée

Seul le contenu textuel nettoyé est transmis au système interne.

---

## Position dans l'architecture

Le Sas Paranoïaque est déployé dans un namespace dédié (`sophia-dmz`). Il constitue le seul point d'entrée autorisé pour les données web.

---

## Objectif

Garantir qu'aucune donnée sensible ne fuit vers Internet, qu'aucun code externe ne pénètre dans le système, et que seules des informations textuelles validées sont ingérées.
