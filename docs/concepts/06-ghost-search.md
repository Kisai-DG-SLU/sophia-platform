# Ghost Search : Obfuscation des Intentions de Recherche

Le **Ghost Search** est un mécanisme d'obfuscation destiné à masquer les intentions réelles du système lorsqu'il effectue des recherches sur Internet.

Son objectif est d'empêcher l'analyse et le profilage des requêtes émises depuis l'infrastructure, afin de ne pas révéler les centres d'intérêt, les projets en cours ou les orientations stratégiques de l'organisation.

---

## Problème

Chaque requête web émise depuis une infrastructure d'entreprise laisse une trace. Les moteurs de recherche, les CDN, les régies publicitaires et les fournisseurs d'accès analysent ces requêtes pour :

- établir un profil de l'entité qui émet les requêtes
- déduire les sujets de recherche, les technologies utilisées, les orientations R&D
- revendre ces données à des concurrents ou à des courtiers en données

Pour une organisation soucieuse de sa souveraineté, exposer ses intentions de recherche revient à exposer sa stratégie.

---

## Principe

Ghost Search repose sur un principe simple : noyer les requêtes légitimes dans un volume de requêtes leurres indiscernables.

Une requête utile est accompagnée de plusieurs requêtes factices, émises simultanément ou en séquence rapprochée, depuis des identités réseau différentes.

Un observateur externe ne peut pas distinguer la requête réelle des leurres.

---

## Fonctionnement

### Génération des leurres

Les requêtes leurres sont générées selon plusieurs stratégies :

- **Thématique.** Des requêtes sur des sujets proches mais non sensibles, pour brouiller le domaine exact de la recherche.
- **Aléatoire.** Des requêtes sur des sujets complètement décorrélés, pour diluer le signal dans le bruit.
- **Historique.** Des requêtes reproduisant des patterns de recherche antérieurs, pour simuler une activité normale et continue.

### Rotation d'identité

Chaque requête (utile ou leurre) est émise depuis une identité réseau différente : proxy différent, en-têtes HTTP variés, fingerprints de navigateur différents.

### Synchronisation temporelle

Les requêtes sont émises de manière à ce qu'un observateur ne puisse pas les différencier par leur rythme ou leur volume. Les leurres respectent les mêmes distributions temporelles que les requêtes réelles.

---

## Relation avec le Sas Paranoïaque

Ghost Search est un module du Sas Paranoïaque. Il opère en amont de la phase de neutralisation du contenu :

1. Ghost Search génère les requêtes (utiles + leurres) et les route via l'infrastructure d'obfuscation.
2. Le Sas Paranoïaque récupère les réponses, les nettoie, et ne transmet au système que le contenu textuel de la requête utile.

---

## Position dans l'architecture

Ghost Search est exécuté dans le namespace `sophia-dmz`, qui constitue la seule zone d'accès au web. Il ne nécessite aucun accès depuis les autres namespaces, préservant ainsi l'isolation du système.

---

## Objectif

Garantir qu'un observateur externe ne peut pas déduire les sujets de recherche, les projets en cours, ou les orientations stratégiques de l'organisation à partir de l'analyse de son trafic web.
