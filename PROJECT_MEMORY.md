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
  - Sending: cyan upright triangle `(0,184,217)`, QGIS marker size `5.5`.
  - Receiving: magenta inverted triangle `(232,62,140)`, QGIS marker size `5.5`.
  - Spillover: amber circle `(255,176,0)`, QGIS marker size `4.5`.
- Flow rendering:
  - Domestic: yellow.
  - Adjacent countries: cyan.
  - Non-adjacent countries: magenta.
  - Unknown/no-match cases are normalized to Non-adjacent countries; the legend should show only Domestic / Adjacent countries / Non-adjacent countries.
  - Flow map line widths are intentionally slim: categorical relation lines use QGIS width `1.4`; graduated magnitude widths are `0.3`, `0.75`, `1.4`, `2.1`; uniform fallback width is `0.9`.
- Composite Telecoupling scenes include both the Flow country-relation legend and the System-type legend; scene legend font sizes should match `render_spatial_file` (`28px` for graduated numeric values, `24px` for legend titles/categories, using the same DejaVuSans-Bold preference).
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

## Tool guide authoring rule (confirmed 2026-07-11)

- For sample-data/user-guide packaging work, the required order is:
  1. rerun the target tool successfully on the live website,
  2. then write the guide files,
  3. then package `sample data` and the guide outputs for upload.
- Do not draft the final user guide before the target tool has been successfully re-executed on the website in the current session.
- Historical PASS records are useful context, but they do not replace the required live website rerun before guide writing.
- Single-tool webpage/user-guide work now has a local progress file: `telecouplingAI-project/Systematic_tests/UserSystematicTest_Run3_20260702/CSIS_剩余单工具用户指南完成计划.md`.
- For tools needing a follow-up render screenshot after the main green card, use `telecouplingAI-project/Systematic_tests/UserSystematicTest_Run3_20260702/_run3_single_tool_followup.py`.
- As of 2026-07-11, `03_coastal_blue_carbon` is the completed template for remaining tools: live MSU main tool PASS, render follow-up PASS, `sample data.zip`, `user guide.md`, `user guide.pdf`, screenshot folder, manifest, and PDF QA render are present.
- As of 2026-07-11, all 43 active single tools in `UserSystematicTest_Run3_20260702/tools/` have complete `updateforuserguide/` packages with PASS `web_test_manifest.json` files. Final report: `telecouplingAI-project/Systematic_tests/UserSystematicTest_Run3_20260702/CSIS_单工具用户指南完成总报告.md`.
- Special cases resolved during that completion pass: `08_habitat_quality` must upload only its 10 guide-listed current-scenario files; `30_co2_emissions` and `34_commodity_trade` needed direct/function-style prompts to avoid stalled workflow-plan paths; `31_cost_benefit_analysis` must use the direct net-returns prompt without the word "analysis" so it produces a single `run_cost_benefit_analysis` tool card (`via_plan=false`); `40_add_media_flows` render needs `mentions` as the magnitude field.
- User guide format rule updated on 2026-07-11: `updateforuserguide/user guide.md` and `user guide.pdf` are user-facing manuals, not test reports. Do not include `Test status`, `Main live webpage run`, `PASS`, or package-maintenance sections in files meant for users to download. Keep a consistent section order: tool purpose, sample data to upload, website run prompt, output explanation, and optional spatial rendering. Preserve file lists, but add short explanatory text so the guide reads smoothly.
- Final server-upload user guide bundles are staged under `telecouplingAI-project/UserGuide/`, one folder per tool named `<NN_tool_name>_User_Guide`. Keep only upload-needed files there: `sample data.zip`, `user guide.md`, `user guide.pdf`, and screenshots directly referenced by the Markdown. Do not include raw `sample data/`, `qa_render/`, manifests, test scripts, or test reports in `UserGuide/`.
- Workflow user guide bundles were added to `telecouplingAI-project/UserGuide/` on 2026-07-11 after fresh live MSU retesting. The two folders are `Workflow_01_soybean_telecoupling_User_Guide/` and `Workflow_02_tourism_telecoupling_User_Guide/`, each containing only `sample data.zip`, `user guide.md`, `user guide.pdf`, and referenced screenshots. Fresh retest results: Soybean workflow completed with 10 green cards in about 94 seconds; Tourism workflow completed with 8 green cards in about 508 seconds.
- Workflow user guides now use four website checkpoint screenshots in order: `plan_card.png`, `confirmed_steps.png`, `workflow_run_started.png`, and `completed_workflow.png`. The text should explicitly tell users to review the workflow card, click **Confirm & run**, upload all sample files, enter the run prompt, click send, then wait for green result cards.

## MSU user-guide entry audit (2026-07-12)

- MSU `tele-fileserver` serves host `/home/jianan2/csis-data/outputs` as public `/download/` through nginx. The main nginx routes `/download/` to `file-server`; all other frontend routes go to `frontend-ui`.
- For User Guide/sample-data publishing, the lowest-risk asset path is `/home/jianan2/csis-data/outputs/user-guides/...` with public links under `/download/user-guides/...`. This avoids changing nginx/compose just to serve downloadable PDFs/zips.
- The MSU host source `frontend/src/App.jsx` previously lagged behind the running frontend image: host source still showed `Hi, CSIS` while the running `tele-frontend` image contained `Hi, Users.`. On 2026-07-12, the MSU host frontend source/config files were synced from the local latest source without rebuilding or restarting containers. Backup: `/home/jianan2/csis-platform/frontend-source-backup-20260712-before-sync.tar.gz`; sync archive: `/home/jianan2/csis-platform/frontend-source-sync-20260712.tar.gz`. Verified `frontend/src/App.jsx` SHA-256 matches local (`e1707715932d65b3f1a0811ed9a0acefd832f3643c82663aeee76b07b3f5234a`) and contains `Hi, Users.`.
- Recommended implementation for the website entry: add a lightweight React `Learning Center` / `User Guides` view in `frontend/src/App.jsx` or a small component, render cards from a generated manifest, and link each PDF/zip to `/download/user-guides/<slug>/user-guide.pdf` and `/download/user-guides/<slug>/sample-data.zip`.
- Local prototype started on 2026-07-12: homepage/header entry opens a `CSIS Learning Center` view; guide metadata lives in `frontend/src/userGuides.js`; each card links to `/download/user-guides/<folder>/user%20guide.pdf` and the per-guide sample zip under the same folder. This is local-only until the user approves deployment.
- Local demo download fix: `frontend/vite.config.js` serves `/download/user-guides/...` from the sibling `UserGuide/` directory through a dev-only middleware. Do not copy the 126MB guide assets into `frontend/public` or `dist`; production should still use nginx `/download/` backed by `/home/jianan2/csis-data/outputs/user-guides/...`.
- Learning Center card descriptions are now per-guide one-sentence summaries in `frontend/src/userGuides.js`; do not use generic text such as "A hands-on guide for running this InVEST model..." on user-facing cards.
- `UserGuide/<folder>/` sample zip files were renamed on 2026-07-12 from generic `sample data.zip` to `<Tool or Workflow Name> sample data.zip` (for example `Add Media Flows sample data.zip`). `frontend/src/userGuides.js` computes and links these filenames via `sampleDataFilename`.
- Deployed hot to MSU and GCP on 2026-07-12 for user-guide entry testing: guide assets were stored outside Docker images under host data directories (`/home/jianan2/csis-data/outputs/user-guides/` on MSU; `/data/outputs/user-guides/` on GCP). Frontend static files were hot-copied into `tele-frontend:/usr/share/nginx/html/`; no Docker image build/commit/retag/force-recreate was performed.
- Deployment validation on 2026-07-12: both MSU public `https://ai.telecoupling.msu.edu/` and GCP `http://34.42.83.50/` returned the new frontend bundle `index-eMc05GKF.js`; `Add Media Flows` guide PDF and `Add Media Flows sample data.zip` returned HTTP 200 on both servers; each server had 135 files under `user-guides` and zero old `sample data.zip` filenames.
- Workflow documentation link fix hot-deployed on 2026-07-12: the public page now labels the entry/buttons as `Documentation`, and the workflow PDF links point to the actual filenames `Soybean_Telecoupling_AI_Driven_User_Guide.pdf` and `Tourism_Telecoupling_User_Guide.pdf`. New frontend bundle: `index-Dd8CHY4p.js`; MSU/GCP public homepages and both workflow PDF URLs returned HTTP 200. This was another hot update only, not Docker image solidification.
- Documentation/frontend changes were solidified on MSU and GCP on 2026-07-12 by saving the verified frontend containers as images, then retagging `csic_frontend:latest`. MSU tag: `csic_frontend:solidified_docs_20260712_081939` (`latest` image ID `sha256:610a7cc8bf6e4e91d56cace74c1d86e046b6afc5828a7e9d82db80b1b87aa083`). GCP tag: `csic_frontend:solidified_docs_20260712_121905` (`latest` image ID `sha256:49391c6602d3892a02707812f2e74d33127660e70e200b19b8cee72335bfde5f`). User-guide PDF/zip assets remain outside Docker images in the host `/download/user-guides/` data directories.

## Hot-patch discipline checkpoint (2026-07-12)

- User rule clarified: after function changes, first hot-patch and let the user test. Only solidify Docker images when the user explicitly says to solidify; do not eagerly rebuild, commit, retag, or force-recreate images while more hot changes may be coming.
- MSU and GCP `tele-celery-render` containers were hot-patched for flow/system rendering changes by syncing host source files, copying them into `/app/renderers/`, and restarting only `tele-celery-render`.
- Current live flow/system behavior on MSU and GCP: system markers are half-sized; flow relation has only Domestic / Adjacent countries / Non-adjacent countries; flow line widths are half of the previous values.
- Latest verified hot-patched `telecoupling_style.py` SHA-256 in both running render containers: `b16b79910b413f820faf289e8ed448fc630e5d66d3186cdae3bd29d67f9a671e`.
- Latest verified hot-patched `_qgis_scene_render_worker.py` SHA-256 in both running render containers after scene legend font alignment: `d8feb9be686da133ef5d251feb06a1179c82bc97e7b64499252ffe734a1087c5`.
- Backups for the latest flow-width hot patch: MSU `/home/jianan2/csis-platform/backups/20260712_flow_width_half/`; GCP `/home/csisaiproject2026/csis-platform/backups/20260712_flow_width_half/`.
- These updates are live hot patches, not image solidification. A normal `docker restart` preserves the container writable layer, but `docker compose up --force-recreate`, rebuilding from old images, or replacing the container can lose the hot patch until the user asks to solidify.
- Backend/render/thinking patches were solidified on MSU and GCP on 2026-07-12. Avoid `docker commit` against the running MSU backend: it paused the container and the commit hung, so it was killed and the backend was unpaused; health recovered. The successful backend solidification method was a thin local Docker build with `FROM csic_backend:latest`, `--pull=false`, and only `COPY` of the patched files (`agent.py`, `telecoupling_style.py`, `telecoupling_classification.py`, `_qgis_scene_render_worker.py`, `file_reference_resolver.py`). This did not download dependencies.
- Solidified backend image tags: MSU `csic_backend:solidified_thinking_render_20260712_083322` (`latest` image ID `sha256:2f25a2a38cd49a01d65f502dcd5b88486b94329f044474721dc8d6feab227338`); GCP `csic_backend:solidified_thinking_render_20260712_123245` (`latest` image ID `sha256:3bf4f155586dafd2ac14f892145690ea7d8acf3ae2283036011c4d05ddcf8bca`). Rollback tags were created before replacing `latest` (`pre_solidify_20260712_*` and running-container pre-solidify tags).

## Communication rule checkpoint (2026-07-12)

- Strong user requirement for the CSIS website: avoid Chinese in the public `Thought process` / thinking-process panel shown to website users. Those website thinking summaries should be English-only.
- Codex conversation/UI with the user should remain Chinese by default unless the user asks otherwise. Do not confuse Codex progress messages with the CSIS website `Thought process` behavior.
- Implementation status: `backend/agent.py` sanitizes streamed SSE `thinking` events by filtering CJK characters and emitting one English fallback when needed; `frontend/src/App.jsx` also filters CJK text before appending/rendering thinking blocks as a UI safety net.
- Runtime prompt status: the system instruction explicitly says visible thought summaries in the website Thought process UI must always be English-only.
- Hot-patched live on MSU and GCP without image solidification: `tele-backend:/app/agent.py` SHA-256 `1912162ec8b1ac6205daf0d0f6db53b3ebf3af41151553a36981e67200b8063c`; `tele-frontend:/usr/share/nginx/html/index.html` SHA-256 `70ed439da7b5ffa0bd9645afc4fcca6cb08451f7a0651e1df14bb741643e2215`; active JS bundle includes the CJK guard regex. This is now also covered by the 2026-07-12 solidified frontend/backend `latest` images described above.
- Backups for this hot patch: MSU `/home/jianan2/csis-platform/backups/20260712_thinking_english_guard/`; GCP `/home/csisaiproject2026/csis-platform/backups/20260712_thinking_english_guard/`.
