# Filtre Anti-Fuite (DLP) : Protection des Données Critiques

Le **DLP Filter** (Data Leak Prevention) est un mécanisme de sécurité qui détecte, anonymise ou bloque les données critiques avant qu'elles ne quittent le périmètre de confiance du système.

Son rôle est de prévenir la fuite d'informations sensibles vers des modèles distants, des services externes, ou des logs non sécurisés.

---

## Problème

Les systèmes d'IA modernes peuvent être amenés à transmettre des données à des services externes pour plusieurs raisons : inférence via un modèle distant, enrichissement de contexte par une API externe, utilisation d'un service de routage de modèles.

Dans ces échanges, le risque de fuite de données sensibles est permanent :

- identifiants techniques (clés API, tokens, certificats)
- données personnelles (noms, emails, numéros)
- propriété intellectuelle (brevets, algorithmes, données financières)
- secrets industriels (sources, architectures, spécifications)

Un système qui ne contrôle pas ce qui sort de son périmètre expose l'organisation à des risques juridiques, concurrentiels et réglementaires.

---

## Principe

Le DLP Filter agit comme une barrière de contrôle au point de sortie du système. Tout contenu destiné à être transmis à un service extérieur est intercepté, analysé, et traité selon des règles configurables.

Trois actions sont possibles :

- **Autoriser.** Le contenu ne contient aucune donnée sensible et peut être transmis.
- **Anonymiser.** Le contenu contient des données sensibles identifiées. Celles-ci sont remplacées par des placeholders avant transmission. Une alerte est enregistrée.
- **Bloquer.** Le contenu contient des données critiques qui ne doivent en aucun cas quitter le périmètre. La transmission est interrompue et une alerte est remontée.

---

## Fonctionnement

### Détection

Le filtre analyse le contenu selon plusieurs méthodes :

- **Pattern matching.** Détection de formats connus (clés API, adresses email, numéros de carte, IBAN) par expressions régulières.
- **Contextuelle.** Analyse sémantique pour identifier des données qui, sans correspondre à un format connu, sont sensibles par leur contexte.
- **Statistique.** Détection d'anomalies dans les flux de sortie : volume inhabituel, type de données inattendu.

### Décision

Chaque règle de détection est associée à un niveau de criticité qui détermine l'action :

- Critique : blocage et alerte immédiate.
- Élevé : anonymisation et alerte.
- Standard : anonymisation silencieuse.
- Information : passage et journalisation.

### Journalisation

Toute interaction avec le DLP Filter est journalisée : contenu intercepté (ou sa signature), règle déclenchée, action appliquée, horodatage. Ces journaux sont accessibles pour audit sans révéler les données elles-mêmes (pseudonymisation).

---

## Position dans l'architecture

Le DLP Filter opère au niveau de la couche de routage (`sophia-core`), au point d'entrée et de sortie des communications avec les modèles distants et les services externes. Il peut être activé ou désactivé par namespace, permettant une granularité fine.

Il fonctionne en complément du Sas Paranoïaque : là où le Sas protège des entrées web, le DLP Filter protège des sorties de données.

---

## Objectif

Garantir qu'aucune donnée sensible ne quitte le périmètre de confiance sans avoir été détectée, anonymisée ou bloquée, et que chaque incident potentiel est tracé et remontable.
