# Ghost Search : Obfuscation des Intentions de Recherche

Le **Ghost Search** est un mecanisme d'obfuscation destine a masquer les intentions reelles du systeme lorsqu'il effectue des recherches sur Internet.

Son objectif est d'empecher l'analyse et le profilage des requetes emises depuis l'infrastructure, afin de ne pas reveler les centres d'interet, les projets en cours ou les orientations strategiques de l'organisation.

---

## Probleme

Chaque requete web emise depuis une infrastructure enterprise laisse une trace. Les moteurs de recherche, les CDN, les regies publicitaires et les fournisseurs d'acces analysent ces requetes pour :

- etablir un profil de l'entite qui emet les requetes
- deduire les sujets de recherche, les technologies utilisees, les orientations R&D
- revendre ces donnees a des concurrents ou a des courtiers en donnees

Pour une organisation soucieuse de sa souverainete, exposer ses intentions de recherche revient a exposer sa strategie.

---

## Principe

Ghost Search repose sur un principe simple : noyer les requetes legitimes dans un volume de requetes leurres indiscernables.

Une requete utile est accompagnee de plusieurs requetes factices, emises simultanement ou en sequence rapprochee, depuis des identites reseau differentes.

Un observateur externe ne peut pas distinguer la requete reelle des leurres.

---

## Fonctionnement

### Generation des leurres

Les requetes leurres sont generees selon plusieurs strategies :

- **Thematique.** Des requetes sur des sujets proches mais non sensibles, pour brouiller le domaine exact de la recherche.
- **Aleatoire.** Des requetes sur des sujets completement decorreles, pour diluer le signal dans le bruit.
- **Historique.** Des requetes reproduisant des patterns de recherche anterieurs, pour simuler une activite normale et continue.

### Rotation d'identite

Chaque requete (utile ou leurre) est emise depuis une identite reseau differente : proxy different, en-tetes HTTP varies, fingerprints de navigateur differents.

### Synchronisation temporelle

Les requetes sont emises de maniere a ce qu'un observateur ne puisse pas les differencier par leur rythme ou leur volume. Les leurres respectent les memes distributions temporelles que les requetes reelles.

---

## Relation avec le Sas Paranoiaque

Ghost Search est un module du Sas Paranoiaque. Il opere en amont de la phase de neutralisation du contenu :

1. Ghost Search genere les requetes (utiles + leurres) et les route via l'infrastructure d'obfuscation.
2. Le Sas Paranoiaque recupere les reponses, les nettoie, et ne transmet au systeme que le contenu textuel de la requete utile.

---

## Position dans l'architecture

Ghost Search est execute dans le namespace `sophia-dmz`, qui constitue la seule zone d'acces au web. Il ne necessite aucun acces depuis les autres namespaces, preservant ainsi l'isolation du systeme.

---

## Objectif

Garantir qu'un observateur externe ne peut pas deduire les sujets de recherche, les projets en cours, ou les orientations strategiques de l'organisation a partir de l'analyse de son trafic web.
