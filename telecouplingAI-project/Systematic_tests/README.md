# CSIS Platform — Systematic Tests

This directory contains active end-to-end suites, reusable test data, historical
evidence, and retired scripts. Do not treat every `test_*.py` file as an active
pytest test.

## Active test surfaces

| Path | Purpose |
|------|---------|
| `../backend/tests/` | Main backend unit/integration regression suite |
| `AI_local_test/` | Offline per-tool test data and `run_all_local_tests.py` |
| `AI_GCP_test/` | Current four-tier API, LLM, smoke/stress, and browser suite |
| `AI_GCP_direct_test/` | Direct server-side runner and patch-data producer |
| `AI_GCP_llm_test/` | Server-side LLM runner used by documented MSU commands |
| `Manual_ClientToGCP_test/` | Current Playwright/manual client-to-server runner and guide generator |
| `render_demo_data/` | Reusable rendering inputs |

`UserSystematicTest_*` directories are dated execution evidence and user-guide
workspaces. Preserve them unless a separate data-retention decision is made.
Running `pytest` from the repository root defaults to `backend/tests/`; invoke
the other suites explicitly when their required server or test data is ready.

## Historical archive

`archive/` contains retired, non-portable, or superseded scripts. They are kept
for provenance and must not be used as the default validation path:

| Path | Reason archived |
|------|-----------------|
| `archive/root_adhoc/` | One-off root scripts/notebook with hard-coded local paths |
| `archive/AI_GCP_browser_test/` | Superseded by `Manual_ClientToGCP_test/run_browser_test.py` |
| `archive/AI_GCP_smoke_test/` | Superseded by `AI_GCP_test/03_smoke_stress_test/` |
| `archive/Manual_GCP_test/` | March 2026 manual/QGIS/container diagnostics |

Archiving is performed with `git mv`; no historical test evidence is deleted.
