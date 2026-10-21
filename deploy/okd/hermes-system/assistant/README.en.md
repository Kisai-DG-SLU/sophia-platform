# Per-project sessions for the coding assistant (`ws`)

Dionysos' coding assistant sees the whole cluster and every repository. To avoid mixing everything in one context (and burning tokens for nothing), each project gets **its own directory, session, memory and tab** in a zellij session, re-created at every container start.

## Installation

These files go into the assistant's private repository (`${CLAUDE_REPO}`), under `ws/`, added to its `.gitignore` allow-list: they are then restored by `init-claude` like the rest of the configuration.

| File | Role |
|---|---|
| `ws` | the tool (see below) |
| `projets.example.tsv` | example registry, to copy as `projets.tsv` |
| `zellij/config.kdl` | zellij configuration of the session (no resurrection: `ws` re-creates it) |

Environment variables read by `ws`: `FORGEJO_URL` (required), `WS_NOTES_REPO` (private notes repository `org/repo`, required), `WS_SESSION` (zellij session name), `WS_GIT_NAME`, `WS_GIT_EMAIL`. The write token is read from `/var/run/secrets/forgejo-push/` (Secret `${PUSH_SECRET}` mounted as a file by `02-observer-dionysos.yaml`).

In the assistant's `settings.json`, a `SessionStart` hook running `ws check --here` tells every session about its project's unpushed work.

## Usage

```bash
oc -n ${AGENT_NAMESPACE} exec -it agent-dionysos-0 -c dionysos -- ws attach
```

In a tab, **Enter** runs `claude --continue` (resumes the project's last conversation); on exit, a shell stays in the project directory.

| Command | Effect |
|---|---|
| `ws list` | projects, status, links, git state |
| `ws new <name> <org/repo[,…]> [--suivi <folder>] [--lies a,b] [--desc "…"]` | new project: clones, partial copy of the notes repository (follow-up folder created if missing), context, memory, tab added without restart |
| `ws close <name> [reason]` | close without destroying: **refuses** while uncommitted or unpushed work remains; removes tab and clone; keeps repository, follow-up, memory and transcripts |
| `ws open <name>` | reopen: the session resumes where it stopped |
| `ws check [--here\|--log]` | unpushed work (start hook, `claude-sync` sidecar) |
| `ws up` | re-create everything (container start command) |

## How it works

- **One directory per project** (`/opt/data/workspaces/<project>/`): the assistant stores transcripts, resumption (`--continue`) and automatic memory per working directory; one session per project is therefore just one directory per project.
- **Two-level context**: a shared `CLAUDE.md` (cross-cutting rules, project map generated from the registry) and, per project, a generated `.claude/CLAUDE.md` (role, repositories, follow-up, linked projects) plus the project memory, reloaded after every `/clear`.
- **Global view kept**: a session reads every directory and the cluster but writes only to its own project; for another project it leaves a note in that project's `notes-entrantes.md`.
- **Private notes**: each project has a partial copy of the notes repository limited to its follow-up folder (separate copies: two sessions never share one git working tree).
- **Persistence**: registry, memories and transcripts live in the assistant repository; working clones are re-created at every pod re-creation (`emptyDir`) — hence the unpushed-work safeguard.

## Known pitfalls

- A zellij command run from inside a zellij session acts on **that** session: `ws` always unsets `ZELLIJ`, `ZELLIJ_SESSION_NAME` and `ZELLIJ_PANE_ID`.
- With no client attached, `zellij action close-tab` closes nothing: `ws` uses `close-tab-by-id`.
- A partial clone (`--filter=blob:none --sparse`) downloads files on `sparse-checkout set`: it needs credentials, like the clone.
- The token mounted as a file is readable by every process in the container, agent included: keep it for a phase where that trust is accepted.
