# Le Tribunal Semantique

Le **Tribunal Semantique** est un mecanisme de validation des connaissances destine a limiter l'ingestion d'informations erronees ou generees artificiellement.

Son role est de juger la credibilite d'une information avant son integration dans la memoire du systeme.

---

## Probleme

Internet contient aujourd'hui une proportion croissante de contenus generes par IA. Cela entraine plusieurs risques :

- propagation d'informations fausses
- amplification d'erreurs
- boucles d'auto-apprentissage (model collapse)
- ingestion de contenu manipule

Un systeme RAG naif peut facilement integrer ces donnees sans distinction.

---

## Principe

Le Tribunal Semantique agit comme un mecanisme de validation multi-sources. Une information n'est integree dans la memoire du systeme que si elle respecte certaines regles.

---

## Processus

### 1. Extraction

Le contenu est recupere via le Sas Paranoiaque.

### 2. Analyse

Le texte est analyse pour detecter :

- indices de generation IA
- incoherences factuelles
- absence de sources

### 3. Croisement

Le systeme recherche plusieurs sources independantes. Une regle simple peut etre appliquee : une information doit etre confirmee par au moins trois sources.

### 4. Decision

Trois cas sont possibles :

**Valide.** L'information est jugee fiable et peut etre indexee.

**Conteste.** Les sources divergent. Le contenu est place en quarantaine.

**Rejete.** Le contenu est juge non fiable. Il est ignore.

---

## Resultat

Seules les informations validees sont integrees dans la memoire persistante (`sophia-memory`).

---

## Objectif

Limiter l'auto-contamination des bases de connaissance, l'amplification des erreurs et les effets de model collapse.
