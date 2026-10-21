# Sessions par projet pour l'assistant de code (`ws`)

L'assistant de code de Dionysos voit tout le cluster et tous les dépôts. Pour ne pas tout mélanger dans un seul contexte (et ne pas consommer de jetons pour rien), chaque projet a **son répertoire, sa session, sa mémoire et son onglet** dans une session zellij, recréés à chaque démarrage du conteneur.

## Installation

Ces fichiers vont dans le dépôt privé de l'assistant (`${CLAUDE_REPO}`), sous `ws/`, ajouté à la liste blanche de son `.gitignore` : ils sont alors restaurés par `init-claude` comme le reste de la configuration.

| Fichier | Rôle |
|---|---|
| `ws` | l'outil (voir ci-dessous) |
| `projets.example.tsv` | registre d'exemple, à copier en `projets.tsv` |
| `zellij/config.kdl` | configuration zellij de la session (sans résurrection : `ws` la recrée) |

Variables d'environnement lues par `ws` : `FORGEJO_URL` (requis), `WS_NOTES_REPO` (dépôt de notes privées `org/dépôt`, requis), `WS_SESSION` (nom de la session zellij), `WS_GIT_NAME`, `WS_GIT_EMAIL`. Le jeton d'écriture est lu dans `/var/run/secrets/forgejo-push/` (Secret `${PUSH_SECRET}` monté en fichier par `02-observer-dionysos.yaml`).

Dans le `settings.json` de l'assistant, un hook `SessionStart` qui lance `ws check --here` signale à chaque session le travail non poussé de son projet.

## Utilisation

```bash
oc -n ${AGENT_NAMESPACE} exec -it agent-dionysos-0 -c dionysos -- ws attach
```

Dans un onglet, **Entrée** lance `claude --continue` (reprise de la dernière conversation du projet) ; en quittant, un shell reste dans le répertoire du projet.

| Commande | Effet |
|---|---|
| `ws list` | projets, statut, liens, état git |
| `ws new <nom> <org/dépôt[,…]> [--suivi <dossier>] [--lies a,b] [--desc "…"]` | nouveau projet : clones, copie partielle du dépôt de notes (dossier de suivi créé s'il manque), contexte, mémoire, onglet ajouté sans redémarrage |
| `ws close <nom> [raison]` | fermer sans détruire : **refuse** s'il reste du travail non commité ou non poussé ; retire onglet et clone ; conserve dépôt, suivi, mémoire et transcripts |
| `ws open <nom>` | rouvrir : la session reprend où elle en était |
| `ws check [--here\|--log]` | travail non poussé (hook de démarrage, sidecar `claude-sync`) |
| `ws up` | tout recréer (commande de démarrage du conteneur) |

## Fonctionnement

- **Un répertoire par projet** (`/opt/data/workspaces/<projet>/`) : l'assistant range transcripts, reprise (`--continue`) et mémoire automatique par répertoire de travail ; une session par projet n'est donc qu'un répertoire par projet.
- **Contexte à deux niveaux** : un `CLAUDE.md` commun (règles transverses, carte des projets générée depuis le registre) et, par projet, `.claude/CLAUDE.md` généré (rôle, dépôts, suivi, projets liés) plus la mémoire du projet, rechargés après chaque `/clear`.
- **Vue globale conservée** : une session lit tous les répertoires et le cluster, mais n'écrit que dans son projet ; pour un autre projet, elle laisse une note dans son `notes-entrantes.md`.
- **Notes privées** : chaque projet a une copie partielle du dépôt de notes limitée à son dossier de suivi (copies séparées : deux sessions ne se partagent jamais un même répertoire git).
- **Persistance** : registre, mémoires et transcripts vivent dans le dépôt de l'assistant ; les clones de travail sont refaits à chaque recréation du pod (`emptyDir`) — d'où le garde-fou sur le travail non poussé.

## Pièges connus

- Une commande zellij lancée depuis l'intérieur d'une session zellij agit sur **cette** session : `ws` retire toujours `ZELLIJ`, `ZELLIJ_SESSION_NAME` et `ZELLIJ_PANE_ID`.
- Sans client attaché, `zellij action close-tab` ne ferme rien : `ws` utilise `close-tab-by-id`.
- Un clone partiel (`--filter=blob:none --sparse`) télécharge des fichiers au `sparse-checkout set` : il lui faut les identifiants, comme au clone.
- Le jeton monté en fichier est lisible par tout processus du conteneur, agent compris : à réserver à une phase où cette confiance est acceptée.
