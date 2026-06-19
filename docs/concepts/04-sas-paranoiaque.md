# Le Sas Paranoiaque

Le **Sas Paranoiaque** est un mecanisme d'isolation destine a interagir avec Internet tout en protegeant l'infrastructure interne de SophIA.

Son objectif est simple : consommer de l'information externe sans exposer l'infrastructure ni contaminer la base de connaissance.

---

## Probleme

L'utilisation d'Internet par des agents IA pose plusieurs risques :

- fuite de donnees via les requetes
- tracage des utilisateurs
- recuperation de contenus malveillants
- ingestion de contenus generes par IA (AI sludge)
- injection de scripts ou de payloads dans le pipeline de donnees

Dans un systeme souverain, l'acces direct au web par les agents n'est pas acceptable.

---

## Principe

Le Sas Paranoiaque agit comme une zone tampon isolee (DMZ) entre Internet et le reste du systeme.

Les agents n'accedent jamais directement au web. Le flux est le suivant :

Agent vers Sas Paranoiaque vers Internet, puis nettoyage, validation, et transmission au systeme.

---

## Fonctionnement

Le Sas Paranoiaque applique plusieurs mecanismes.

### Isolation

Les requetes web sont executees dans des jobs ephemeres et isoles. Ces jobs sont detruits apres usage.

### Obfuscation

Pour limiter le tracage et l'analyse des requetes :

- utilisation de proxies
- generation de requetes leurres (shadow queries)
- rotation d'identite reseau

Exemple : 1 requete utile pour 3 a 4 requetes leurres.

### Neutralisation du contenu

Les pages recuperees sont detruites puis reconstruites :

- suppression complete du JavaScript
- suppression des traqueurs
- suppression des scripts dynamiques

Le resultat final est converti en Markdown brut.

### Transmission controlee

Seul le contenu textuel nettoye est transmis au systeme interne.

---

## Position dans l'architecture

Le Sas Paranoiaque est deploye dans un namespace dedie (`sophia-dmz`). Il constitue le seul point d'entree autorise pour les donnees web.

---

## Objectif

Garantir qu'aucune donnee sensible ne fuit vers Internet, qu'aucun code externe ne penetre dans le systeme, et que seules des informations textuelles validees sont ingerees.
