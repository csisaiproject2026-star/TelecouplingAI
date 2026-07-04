# CSIS Platform Project Memory

> Durable operational memory for future Codex/Claude sessions. Read this file before repeating repository discovery, deployment, or workflow verification. Update only when facts materially change.

## Repository and branches

- Canonical GitHub remote: `origin = git@github.com:csisaiproject2026-star/TelecouplingAI.git`.
- Protected stable branch: `master`.
- Main development branch: `feature/invest-expansion`.
- Deployment/history branch currently used by this workspace: `gcp-head`; it is based on `feature/invest-expansion` and contains the later GCP/Run2 fixes.
- The worktree contains many historical untracked and deleted files. Never use `git add .`; stage an explicit file list only.
- Historical untracked test data, screenshots, extracted feedback, prototypes, and local distribution packages are intentionally excluded unless the user explicitly names them. Do not treat them as missing work, delete them, or upload them by default. See `DEV_LOG.md` around the 2026-06-17/18 Git push notes for the original decision.
- The established push scope is normally source code and explicitly requested documentation/evidence, not all local test datasets. Always show or audit the explicit staged list before committing.
- User reaffirmed on 2026-07-04: test data and feedback must not be pushed to GitHub. This includes `feedbacks/`, Run test datasets, generated screenshots/results/logs, extracted feedback, and local training-manual image assets. Keep them local unless the user explicitly overrides this rule for a named file.
- Servers are not Git repositories. Never deploy with `git pull` on GCP or MSU.
- Alignment rule confirmed 2026-07-04: after validating the MSU-equivalent commit on GCP, point both `gcp-head` and the dated MSU alignment branch at the same commit SHA and push both branches to `origin`.

## Server facts

- GCP: `ssh csis-gcp`, IP `34.42.83.50`, project root `~/csis-platform/`.
- MSU: `ssh csis-msu`, IP `35.9.219.33`, project root `~/csis-platform/telecouplingAI-project/`.
- MSU public URL: `https://ai.telecoupling.msu.edu/` through the MSU WAF.
- Per-server `.env` and `.env.docker` files must never be copied from local or between servers.
- `SERVER_BASE_URL` is the single base URL setting; download URLs are derived by backend configuration.

## Deployment discipline

- Transfer only selected source files or a tar archive that explicitly excludes `.env` and `.env.docker`.
- Build backend images from the server backend directory.
- Before replacing `latest`, create a dated rollback tag.
- After deployment, verify container health, public `/health`, and recent logs for application `ERROR`/`Traceback`.
- A Docker/container/server restart preserves image-based changes. A later full rebuild from stale host source can overwrite them, so source synchronization is still required.

## MSU image checkpoint (2026-07-04)

- Compose services reference `csic_backend:latest` and `csic_frontend:latest` with restart policy `always`.
- Frontend final image: `csic_frontend:ui_map_20260704` (also tagged `latest`).
- Backend/render final image: `csic_backend:workflow_render_legend_20260704` (also tagged `latest`).
- Useful rollback tags:
  - `csic_frontend:pre_ui_map_20260704`
  - `csic_backend:pre_ui_map_20260704`
  - `csic_backend:pre_workflow_render_20260704`
  - `csic_backend:pre_scene_legend_20260704`
- Thin patch Dockerfiles are versioned under `telecouplingAI-project/deploy/`.
- Treat MSU as the current latest production reference. Do not rebuild, recreate, restart, retag, or overwrite MSU during Git/GCP alignment unless the user explicitly asks. Use read-only checks against MSU and deploy the aligned commit to GCP instead.
- Read-only source audit on 2026-07-04:
  - All 80 common Python source files in local backend and the latest `tele-celery-render` container matched byte-for-byte by SHA-256 (`Different=0`).
  - MSU-only `test_cbc_direct.py` and `test_tif.py` are ad-hoc container tests, not runtime source and are intentionally not backported.
  - Local-only files are the three new unit/QGIS smoke tests.
  - Local frontend production build and all four active files in `tele-frontend` matched by SHA-256. MSU additionally contains nginx `50x.html` and one orphaned old hashed JS asset; `index.html` and the active bundle match local.

## UI and map behavior checkpoint (2026-07-04)

- Welcome text is `Hi, Users.`.
- System rendering:
  - Sending: cyan upright triangle `(0,184,217)`.
  - Receiving: magenta inverted triangle `(232,62,140)`.
  - Spillover: amber circle `(255,176,0)`.
- Flow rendering:
  - Domestic: yellow.
  - Adjacent countries: cyan.
  - Non-adjacent countries: magenta.
  - Unknown: gray when endpoints cannot be matched to the world boundary layer.
- Composite Telecoupling scenes include both the Flow country-relation legend and the System-type legend.
- Render calls resolve output basenames such as `radial_flows.shp` against session output paths before dispatch.

## Rendering design decisions

- TIF/SHP outputs remain download-only by default.
- Only render when the user explicitly requests visualization.
- Use `render_spatial_file` for one spatial output.
- Use `render_telecoupling_scene` to overlay Systems/Flows/Agents/Causes in one map.
- Do not claim an image is shown unless the corresponding render tool actually produced an image.

## Workflow verification checkpoint (2026-07-04)

- Soybean workflow: PASS, 4 planned steps, 10 green result cards; final measured run about 86 seconds.
- Tourism workflow: PASS, 5 planned steps, 8 green result cards; final measured run about 98 seconds.
- Post-workflow visualization: 5/5 PASS.
  - Soybean Systems + Flows composite.
  - Soybean crop yield raster.
  - Soybean habitat quality raster.
  - Soybean habitat degradation raster.
  - Tourism Systems + Flows composite.
- Reusable runner and evidence: `feedbacks/MSU_Workflow_Verification_20260704/`.
- Training manual: `telecouplingAI-project/Systematic_tests/UserSystematicTest_Run3_20260702/CSIS_两个Workflow学习测试手册.md`.
- Manual images are local to the manual tree in `workflow_manual_images/`; 9/9 links were verified.

## Fast validation commands

- Focused backend tests:
  - `python -m pytest backend/tests/test_telecoupling_classification.py backend/tests/test_file_reference_resolver.py -q -p no:cacheprovider`
- Frontend build:
  - `npm run build` from `telecouplingAI-project/frontend/`.
- QGIS runtime smoke test:
  - `backend/tests/qgis_telecoupling_style_smoke.py` inside a backend/QGIS-capable container.
- Do not rerun both full web workflows unless workflow execution, rendering, file-path resolution, or deployment behavior changed.

## 2026-07-04 change set

- Core source:
  - `frontend/src/App.jsx`
  - `backend/agent.py`
  - `backend/renderers/telecoupling_style.py`
  - `backend/renderers/telecoupling_classification.py`
  - `backend/renderers/_qgis_scene_render_worker.py`
  - `backend/shared/file_reference_resolver.py`
- Tests:
  - `backend/tests/test_telecoupling_classification.py`
  - `backend/tests/test_file_reference_resolver.py`
  - `backend/tests/qgis_telecoupling_style_smoke.py`
- Local commit containing the main change set: `24c0210` (`feat: persist telecoupling map styles and workflow rendering`).

## GCP/MSU alignment checkpoint (2026-07-04)

- The authoritative clean alignment branch is `codex/msu-aligned-20260704`, created directly from remote `gcp-head` and containing only audited source, tests, deployment Dockerfiles, and project memory/docs.
- Clean alignment commit before final deployment notes: `23d2b77`. No test datasets, feedback, screenshots, generated results/logs, or workflow-manual image assets are present in this branch.
- The actual GCP compose root is `~/csis-platform/telecouplingAI-project/`.
- GCP rollback tags created before deployment: `csic_backend:pre_msu_align_20260704` and `csic_frontend:pre_msu_align_20260704`.
- GCP candidate tags: `csic_backend:msu_aligned_20260704` and `csic_frontend:msu_aligned_20260704`; both were promoted to `latest` after validation.
- GCP post-deployment checks: all compose services running, backend and Redis healthy, public `/health` returned `{"status":"ok"}`, deployed bundle contained `Hi, Users`, QGIS classification smoke passed, and the first five minutes of logs contained no `Traceback`, `ERROR`, or unhandled exception matches.
- MSU was not restarted, rebuilt, recreated, retagged, or written to during this alignment.
