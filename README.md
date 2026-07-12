# TelecouplingAI

TelecouplingAI is the CSIS web platform for AI-assisted InVEST and
telecoupling analysis. The stack combines a React/Vite interface, FastAPI,
Gemini function calling, Redis/Celery workers, InVEST, R, and QGIS rendering.

- Production: <https://ai.telecoupling.msu.edu/>
- GCP validation environment: <http://34.42.83.50/>
- Canonical branch: `production`

## Repository layout

```text
.
├── telecouplingAI-project/  # Deployable application and active tests
│   ├── backend/
│   ├── frontend/
│   ├── nginx/
│   ├── deploy/
│   ├── Systematic_tests/
│   └── docker-compose.yml
├── docs/                    # Operations, reports, research, demos, and history
├── usecaseLevel_workflow/   # Active workflow design spike
├── AGENTS.md                # Agent operating instructions
├── PROJECT_MEMORY.md        # Current stable project facts
├── DEV_LOG.md               # Canonical append-only development history
└── ROADMAP.md               # Product roadmap
```

See [`docs/README.md`](docs/README.md) for the documentation index and
[`telecouplingAI-project/deploy/README.md`](telecouplingAI-project/deploy/README.md)
for production source controls.

## Development workflow

1. Create a short-lived `feature/<topic>` branch from `production`.
2. Implement and validate locally.
3. Deploy the candidate commit to GCP for integration testing.
4. Merge the validated change into `production`.
5. Build one immutable image and promote that same image to MSU.

GCP is a validation environment, not a long-lived Git branch. MSU is the
production environment.

## Validation

From the repository root:

```bash
python -m pytest
python telecouplingAI-project/deploy/audit_production_drift.py
```

The default pytest configuration discovers the active backend suite only.
Systematic and server-dependent suites must be invoked explicitly.

## Deployment safety

The servers are deployment targets, not Git working copies. Never overwrite
server-specific environment files, TLS keys, outputs, uploads, model data, or
external User Guide assets. Do not restart or recreate production containers
unless the deployment has been separately approved and a rollback is ready.
