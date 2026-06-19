# Scripts — Reference

This directory documents the operational scripts found in the internal agent configuration repository (`sophia-brain/scripts/`). These scripts are specific to the live infrastructure and are not reproduced here.

## Script Inventory

| Script | Purpose |
|---|---|
| `save-brain.sh` | Automated commit and push for both the agent config repository and the memory repository. Supports `--dry-run`, `--engine-only`, `--memory-only` flags. |
| `sophia-vault.sh` | SOPS encryption/decryption wrapper for managing encrypted secrets (`secrets.enc.env`). |
| `backup_db.sh` | Database backup reference script. PostgreSQL was removed in favor of Langfuse Cloud for observability; kept for future RAG with PostgreSQL + pgvector. |
| `rotate-certificates-macos.sh` | OpenShift certificate rotation for macOS environments. Triggered when certificates are exposed. |
| `rotate-certificates-emergency.sh` | Emergency manual certificate rotation guide for OpenShift. Requires manual admin intervention. |
| `rotate-kubeconfig.md` | Step-by-step guide for revoking and rotating exposed `kubeconfig` certificates. |
| `generate_workspaces.py` | Generates `.code-workspace` multi-root files for all projects (Production + Memory directories). |
| `migrate_all_projects.sh` | Bulk migration script for project infrastructure. |
| `create_sophia_links.sh` | Creates symbolic links and directory structure for the Sophia workspace. |
| `check_and_start.sh` | Health check and startup script for agent gateway. |
| `direnv_hook.sh` | Shell hook for environment variable auto-loading with direnv. |

## Deployment Notes

These scripts are **not** included in the public repository as they contain infrastructure-specific logic, paths, and credentials. If you need similar functionality:

- **Backup/rotation**: Adapt from the reference scripts using your cluster's native backup tools (Velero, etcd snapshots)
- **Secret management**: Use SOPS, Helm Secrets, or External Secrets Operator
- **Workspace management**: Use the OpenShift API or a GitOps tool (ArgoCD)
