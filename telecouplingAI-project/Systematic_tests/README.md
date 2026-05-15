# CSIS Platform — Systematic Tests

Five test categories, each with a clear scope.

```
Systematic_tests/
├── AI_local_test/          ← 42 per-tool local tests (upload CSV → chat → check output)
├── AI_GCP_test/            ← Automated integration tests against GCP via AI path
├── AI_Smoke_GCP_test/      ← Quick AI-driven smoke check: is GCP alive and responding?
├── Manual_GCP_test/        ← Human-executed manual scripts and legacy ad-hoc tests
└── GCP_test/               ← Infrastructure-level tests (stress, load, connectivity)
```

---

## AI_local_test/

One subfolder per tool (42 total). Each contains:
- `testdata/` — sample input files (CSV / HTML). InVEST tools have a README pointing to `datainput_for_demo/`.
- `output/` — outputs land here after a test run.
- `how_to_test.bat` — open in editor: explains which files to upload and what prompt to send.

| Range | Tools |
|-------|-------|
| 01–06 | Network Analysis, CBC Preprocessor, CBC Main, SWY, Crop Percentile, Crop Regression |
| 07–27 | All remaining InVEST tools (Carbon, HQ, AWY, SDR, NDR, Urban, Scenic, HRA, Wave, etc.) |
| 28–42 | New non-InVEST tools (OLS, FAMD, CO2, CBA, Pop Density, Flows, Trade, Agents, Food, Nutrition) |

## AI_GCP_test/

Automated pytest scripts that call the GCP API through the full AI/tool path.

| File | Scope |
|------|-------|
| `test_e2e_tools.py` | End-to-end tool execution on GCP |
| `test_concurrent_tools.py` | Concurrent tool calls, queue isolation |
| `test_integration.py` | API + Redis + Celery integration |

Run: `pytest AI_GCP_test/ -v` (requires GCP at 34.42.83.50)

## AI_Smoke_GCP_test/

| File | Scope |
|------|-------|
| `test_gcp_e2e.py` | Quick smoke: health check + one representative tool call |

Run: `pytest AI_Smoke_GCP_test/ -v` after any deployment to confirm GCP is up.

## Manual_GCP_test/

Legacy and ad-hoc scripts for human-driven testing.

| Subfolder | Contents |
|-----------|----------|
| `manual_20260315/` | Early manual test scripts (SWY, CBC, Crop, Network) |
| `headless_qgis/` | Headless QGIS rendering debug scripts |
| `backend_loose/` | Loose backend scripts (CBC direct, TIF render) |

## GCP_test/

Infrastructure-level tests — run independently of the AI path.

| File | Scope |
|------|-------|
| `test_stress_50.py` | 50-user load test against GCP endpoints |

Run: `python GCP_test/test_stress_50.py` or via Locust.

---

## What is NOT here

`backend/tests/` — the main **pytest unit/integration suite** — lives alongside the source
code and is run via `pytest backend/tests/`. It is not part of this directory.
