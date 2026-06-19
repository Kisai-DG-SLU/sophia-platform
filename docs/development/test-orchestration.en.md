# Project Test Orchestration Workflow

This document defines the standard method for managing artificial intelligence project tests through a notebook environment within the SophIA ecosystem.

## 1. System Architecture

The model relies on a single sovereign orchestrator accessing a set of versioned projects.

- **Compute (Kubernetes):** A dedicated notebook pod with a custom base image.
- **Storage:** Persistent volume mounted on `$WORKSPACE_DIR`.
- **Git:**
  - Global repository containing specifications and procedures.
  - One dedicated repository per project.
- **Environment isolation:** Reproducible environments per project via a dedicated environment manager.

---

## 2. Workspace Structure

The organization ensures persistence of environments and code:

```text
$WORKSPACE_DIR/
├── .local/                # IDE configuration
├── specs/                 # Brain repository clone (the doctrine)
├── project-a/             # Project A repository
│   ├── .env/              # Isolated environment
│   ├── env.toml           # Dependency manifest
│   └── data/              # Local data
└── project-b/             # Project B repository
```

---

## 3. Operational Workflow

### A. Initialization or Retrieval

1.  Clone with access token:

    ```bash
    cd $WORKSPACE_DIR
    git clone https://$GIT_SERVER/$USER/$PROJECT.git
    ```

2.  Environment configuration:

    ```bash
    cd $PROJECT
    env install   # install dependencies from manifest
    ```

### B. IDE Kernel Configuration

Each project has its own kernel to avoid library conflicts.

```bash
env run python -m ipykernel install --user \
    --name $PROJECT \
    --display-name "Python ($PROJECT)"
```

### C. Interface Usage

1.  Open the IDE interface via the Kubernetes route.
2.  Navigate to the project folder.
3.  Select the corresponding kernel for the active project.

---

## 4. Data Management and Backup

- Data is stored on the persistent volume.
- Code is synchronized to the internal Git repository using standard commands.
- Multiple projects can be open simultaneously, each using its own environment.

---

## 5. Maintenance

- Access tokens can be retrieved from pod logs.
- Kernel paths are verifiable in the IDE configuration.
- Global secrets are injected into the pod; specific secrets can be managed via a local environment file.
