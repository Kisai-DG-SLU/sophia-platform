# Filtre Anti-Fuite (DLP) : Protection des Donnees Critiques

Le **DLP Filter** (Data Leak Prevention) est un mecanisme de securite qui detecte, anonymise ou bloque les donnees critiques avant qu'elles ne quittent le perimetre de confiance du systeme.

Son role est de prevenir la fuite d'informations sensibles vers des modeles distants, des services externes, ou des logs non securises.

---

## Probleme

Les systemes d'IA modernes peuvent etre amenes a transmettre des donnees a des services externes pour plusieurs raisons : inference via un modele distant, enrichissement de contexte par une API externe, utilisation d'un service de routage de modeles.

Dans ces echanges, le risque de fuite de donnees sensibles est permanent :

- identifiants techniques (cles API, tokens, certificats)
- donnees personnelles (noms, emails, numeros)
- propriete intellectuelle (brevets, algorithmes, donnees financieres)
- secrets industriels (sources, architectures, specifications)

Un systeme qui ne controle pas ce qui sort de son perimetre expose l'organisation a des risques juridiques, concurrentiels et reglementaires.

---

## Principe

Le DLP Filter agit comme une barriere de controle au point de sortie du systeme. Tout contenu destine a etre transmis a un service exterieur est intercepte, analyse, et traite selon des regles configurables.

Trois actions sont possibles :

- **Autoriser.** Le contenu ne contient aucune donnee sensible et peut etre transmis.
- **Anonymiser.** Le contenu contient des donnees sensibles identifiees. Celles-ci sont remplacees par des placeholders avant transmission. Une alerte est enregistree.
- **Bloquer.** Le contenu contient des donnees critiques qui ne doivent en aucun cas quitter le perimetre. La transmission est interrompue et une alerte est remontee.

---

## Fonctionnement

### Detection

Le filtre analyse le contenu selon plusieurs methodes :

- **Pattern matching.** Detection de formats connus (cles API, adresses email, numeros de carte, IBAN) par expressions regulieres.
- **Contextuelle.** Analyse semantique pour identifier des donnees qui, sans correspondre a un format connu, sont sensibles par leur contexte.
- **Statistique.** Detection d'anomalies dans les flux de sortie : volume inhabituel, type de donnees inattendu.

### Decision

Chaque regle de detection est associee a un niveau de criticite qui determine l'action :

- Critique : blocage et alerte immediate.
- Eleve : anonymisation et alerte.
- Standard : anonymisation silencieuse.
- Information : passage et journalisation.

### Journalisation

Toute interaction avec le DLP Filter est journalisee : contenu intercepte (ou sa signature), regle declenchee, action appliquee, horodatage. Ces journaux sont accessibles pour audit sans reveler les donnees elles-memes (pseudonymisation).

---

## Position dans l'architecture

Le DLP Filter opere au niveau de la couche de routage (`sophia-core`), au point d'entree et de sortie des communications avec les modeles distants et les services externes. Il peut etre active ou desactive par namespace, permettant une granularite fine.

Il fonctionne en complement du Sas Paranoiaque : la ou le Sas protege des entrees web, le DLP Filter protege des sorties de donnees.

---

## Objectif

Garantir qu'aucune donnee sensible ne quitte le perimetre de confiance sans avoir ete detectee, anonymisee ou bloquee, et que chaque incident potentiel est trace et remontable.
