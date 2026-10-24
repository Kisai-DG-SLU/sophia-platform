# Modele de Securite SophIA

La securite est un principe fondamental de conception de SophIA.

L'architecture implemente une approche Zero Trust dans laquelle chaque composant est isole et autorise a communiquer uniquement avec les services explicitement autorises.

---

## Principes fondamentaux de securite

Le systeme est concu autour des principes suivants :

- Acces reseau par moindre privilege
- Isolation entre les namespaces
- Connectivite externe controlee
- Infrastructure reproductible
- Tracabilite complete des interactions IA

---

## Segmentation reseau

Chaque namespace appartient a une zone de securite specifique.

| Zone       | Objectif                            |
|------------|-------------------------------------|
| brain      | services d'orchestration            |
| air-gapped | inference locale et memoire         |
| outils     | outils et services MCP              |
| sas        | acquisition web externe             |
| dev        | environnements de developpement     |
| frontend   | interfaces utilisateur              |

Les communications reseau entre zones sont restreintes a l'aide de NetworkPolicies Kubernetes.

### Acces a la plateforme : VPN uniquement

La plateforme ne se joint que par un VPN WireGuard, y compris depuis le reseau local ; le reseau local n'est jamais joignable depuis le VPN. Sur le noeud, une table nftables dediee, independante d'OVN-Kubernetes, distingue deux plages : **administration** (tout le noeud, Forgejo) et **utilisateurs** (HTTP/HTTPS seulement), et ne relaie rien d'autre que Forgejo pour l'administration. Un garde-fou verifie que cette table reste lisible par la version de nft embarquee dans OVN-Kubernetes ; sinon il la retire et alerte, sans jamais couper le VPN, seul chemin d'administration. Voir `deploy/okd/host/wireguard/`.

---

## Composants air-gapped

Certains namespaces sont intentionnellement isoles des reseaux externes, afin d'eliminer tout risque d'exfiltration de donnees : leurs modeles et donnees sont deposes depuis le noeud, a des revisions et empreintes figees.

| Namespace | Etat dans l'installation de reference |
|---|---|
| sophia-inference | **en place** : tout refuse, entree depuis le routeur de modeles et l'outil d'images seulement, aucune sortie |
| sophia-skills | **en place** : aucune sortie hors DNS et modeles d'image |
| sophia-memory | **cible** : isolation a appliquer |

---

## Acquisition de donnees externes

Les informations externes sont recuperees via une couche d'isolation dediee. La couche DMZ est responsable de l'extraction web, du nettoyage du contenu, de la suppression du contenu executable et de la livraison de donnees purifiees au format Markdown au systeme interne.

Ce mecanisme empeche les scripts malveillants ou les mecanismes de tracage de penetrer dans la plateforme.

---

## Protection des donnees

Les donnees sensibles sont protegees par plusieurs mecanismes :

- Controle d'acces strict (SSO, groupes, cles restreintes par client)
- Secrets geres via Kubernetes, jamais dans les depots
- Journalisation d'audit
- Volumes de stockage chiffres : **cible**, pas encore en place dans l'installation de reference (volumes locaux non chiffres)

Les donnees persistantes (bases vectorielles, bases relationnelles, depots de code) sont sur des volumes locaux du serveur ; leur chiffrement au repos est a mettre en place.

---

## Journalisation des interactions

Toutes les interactions IA peuvent etre journalisees pour garantir l'auditabilite. Les journaux incluent les prompts, les reponses, les decisions de routage et les requetes bloquees.

Cela permet une analyse forensique et une tracabilite du comportement de l'IA.

---

## Ameliorations futures de la securite

Les ameliorations prevues incluent :

- Filtrage DLP avance
- Pipelines de verification semantique
- Validation automatisee des sources de connaissance externes
