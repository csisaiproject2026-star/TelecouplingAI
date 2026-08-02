# CSIS Platform Project Memory

> Durable operational memory for future Codex/Claude sessions. Read this file before repeating repository discovery, deployment, or workflow verification. Update only when facts materially change.

## Repository and branches

- Canonical GitHub remote: `origin = git@github.com:csisaiproject2026-star/TelecouplingAI.git`.
- `production` is the GitHub default and only long-lived branch.
- Create short-lived `feature/<topic>` branches from `production`; deploy the candidate commit to GCP, merge after validation, then promote the same immutable image to MSU.
- GCP is a test environment, not a long-lived Git branch.
- The former `master`, `feature/invest-expansion`, `gcp-head`, and dated `codex/*` branches were deleted on 2026-07-12 after their tips were preserved under `archive/*` annotated tags.
- The worktree contains many historical untracked and deleted files. Never use `git add .`; stage an explicit file list only.
- Historical untracked test data, screenshots, extracted feedback, prototypes, and local distribution packages are intentionally excluded unless the user explicitly names them. Do not treat them as missing work, delete them, or upload them by default. See `DEV_LOG.md` around the 2026-06-17/18 Git push notes for the original decision.
- The established push scope is normally source code and explicitly requested documentation/evidence, not all local test datasets. Always show or audit the explicit staged list before committing.
- User reaffirmed on 2026-07-04: test data and feedback must not be pushed to GitHub. This includes `feedbacks/`, Run test datasets, generated screenshots/results/logs, extracted feedback, and local training-manual image assets. Keep them local unless the user explicitly overrides this rule for a named file.
- Servers are not Git repositories. Never deploy with `git pull` on GCP or MSU.
- Do not recreate parallel environment branches or manually synchronize several long-lived branches; that historical workflow caused source drift.

## Documentation sources of truth

- `DEV_LOG.md` at the repository root is the only canonical append-only development log. Do not create additional project `DEV_LOG*.md` files.
- `PROJECT_MEMORY.md` is the first-read summary for current stable facts; use `DEV_LOG.md` only when detailed chronology is needed.
- `docs/history/development-summary-through-2026-05-16.md` is a frozen digest derived from the root log, not a second log.
- Dated test records under `telecouplingAI-project/Systematic_tests/archive/` are historical evidence and must not receive project-wide development entries.
- Root documentation is indexed by `docs/README.md`: operations in `docs/ops/`, reports in `docs/reports/`, research in `docs/research/`, reusable references in `docs/reference/`, historical demos in `docs/demo/`, and superseded specifications in `docs/archive/`.
- Generated dependencies and runtime state (`node_modules/`, `dump.rdb`, logs, demo command state) are not tracked. Recreate Node dependencies from the lock files in `docs/demo/` and `docs/demo/playwright_demo/`.
- `feedbacks/` remains local evidence governed by the no-new-push rule, and `usecaseLevel_workflow/` remains an active design workspace; neither was relocated during the 2026-07-12 root cleanup.

## Server facts

- GCP 1 (`csis-server`): `ssh csis-gcp`, IP `34.42.83.50`, project root `~/csis-platform/telecouplingAI-project/`.
- GCP 2 (`csis-server-2`): `ssh csis-gcp-2`, IP `34.136.64.176`, SSH as `csisaiproject2026` with `~/.ssh/id_ed25519_csis`; project root `~/csis-platform/telecouplingAI-project/`.
- GCP 2 was first recorded on 2026-07-31. SSH, HTTP/HTTPS, `/health`, and 40 running containers were reachable; zero unhealthy or restarting containers were observed. Root disk was 97 GB total, 76 GB used, and about 22 GB free. Its source, environment, data, image, and runtime parity with GCP 1 have not yet been audited, so do not promote or deploy by assuming both GCP servers are identical.
- MSU: `ssh csis-msu`, IP `35.9.219.33`, project root `~/csis-platform/telecouplingAI-project/`.
- MSU public URL: `https://ai.telecoupling.msu.edu/` through the MSU WAF.
- Per-server `.env` and `.env.docker` files must never be copied from local or between servers.
- `SERVER_BASE_URL` is the single base URL setting; download URLs are derived by backend configuration.
- On 2026-07-31, GCP 1 and GCP 2 received separate user-provided Gemini API keys. Each prior `.env.docker` is backed up under `~/csis-platform/backups/20260731_gemini_key_rotation/`; no key value is stored in Git or project documentation.
- Both new keys authenticate successfully, list models, and complete the full platform SSE path with `gemini-3.5-flash`. However, the exact official `google-genai` 2.14.0 call to `gemini-2.5-flash` returns Google HTTP 404 on both hosts: `This model models/gemini-2.5-flash is no longer available to new users.` This rules out spelling, an old SDK, a disabled API, and host-region differences for these keys.
- Gemini compatibility migration `ddc7355` was deployed to both GCP hosts on 2026-07-31. The frontend intentionally remains unchanged and still displays/sends `gemini-2.5-flash`; the backend resolves that exact compatibility ID to `gemini-3.5-flash` before calling Google. Backend/config/template/test defaults now use 3.5, and 3.5 thinking summaries are enabled. Do not claim that the UI label is the actual upstream model.
- GCP 1 API image after migration: `sha256:6971bb9fda6b4dd9ce08f6b18803753309d5b7cf92da7da2f76ae9e12594b934`. GCP 2 API image: `sha256:11866d018cda18b5bbd66f48a8d515b92e50a05ada0707e1bed48efd498206cf`. They were independently thin-built from the same prior image and identical `ddc7355` runtime files; `/app/agent.py`, `config.py`, and `main.py` hashes match across hosts. Rollback source, environment, Dockerfile, and image tags are under `~/csis-platform/backups/20260731_gemini35_compat_ddc7355/`.
- Full platform checks passed on both GCP hosts while the request still sent `model=gemini-2.5-flash`: plain SSE chat, visible thinking, OLS tool dispatch, three generated output files, deterministic direct completion, and `done`. The frontend bundle remained `index-xR8BRM1J.js`.
- The GCP 2 clone still had GCP 1's legacy `FILE_SERVER_URL`, causing its successful tool outputs to link to GCP 1 and return 404. Its server-local environment now uses `SERVER_BASE_URL=https://34.136.64.176`, deriving `https://34.136.64.176/download/`; a fresh OLS output download returned 200. GCP 1's existing URL configuration was not changed.

## MSU Gemini capacity checkpoint (2026-07-27)

- User-provided Google AI Studio evidence confirms the active project `CSIS-AI-Platform-Project` is Tier 2.
- Active Gemini 2.5 Flash limits shown on 2026-07-27: 2,000 RPM, 3,000,000 input TPM, and 100,000 RPD.
- Current Google billing rule checked on 2026-07-27: Tier 3 is automatically granted after the linked Cloud Billing account has paid USD 1,000 and 30 days have elapsed since its first successful payment; eligible upgrades usually appear within about 10 minutes after payment/criteria processing.
- This supersedes the historical May 2026 stress-test assumption of 1,000,000 input TPM for current capacity planning.
- At the historical prompt footprint of about 43,000 input tokens per model call, TPM alone permits about 69 model calls per minute in theory; a user workflow may require multiple model calls.
- Current application limits remain more immediate: `MAX_SESSIONS=50`, one Uvicorn process, `_GEMINI_SEMAPHORE=3`, and usually one Celery worker slot per tool queue.
- Do not promise 200 simultaneously active users without raising/fixing session capacity, improving Gemini concurrency/backpressure, and rerunning realistic 200-user tests through the public MSU WAF.

## 200-user capacity checkpoint (2026-07-28)

- Candidate `capacity-200-v1-165e307` raised GCP to 500 sessions, 8 Gemini calls, a 500-request Gemini queue, and a 2.7M input-TPM safety budget. Session continuity and resource usage remained healthy, but its 50-user fast-pool run reached only 43/50 because seven requests hit the client-side 900-second timeout.
- The seven long tails were not Gemini, CPU, Redis capacity, or Celery compute saturation. All 50 runs reached Celery dispatch, and the affected fast workers finished in milliseconds.
- Root cause: `backend/agent.py` dispatched Celery before subscribing to the task's Redis Pub/Sub channel. Fast workers could publish `tool_result` and `done` before the subscriber existed; Redis Pub/Sub does not replay missed messages. The 1800-second timeout was inside the message-loop body, so it also could not fire when no message arrived.
- The local fix preassigns the Celery task ID, confirms the Pub/Sub subscription before dispatch, and wraps the whole listener in a real asynchronous timeout. Do not resume 100/200-user testing until this candidate is deployed to GCP and passes small fast-pool runs plus repeated 50-user runs at the 99% gate.
- GCP candidate `capacity-200-v1-ea641be` deployed and passed the fast-pool ladder: 10/10, 50/50, 100/100, and final 200/200 with complete session retention. At 200 users, p50 was 294.5 seconds, p95 459.5 seconds, maximum 464.5 seconds, CPU peak 19.8%, and RAM peak 6.6/32 GB. Evidence is under `~/csis-platform/capacity-results/capacity-200-v1-ea641be-20260728/`.
- This validates small inline-CSV fast tools only. It does not validate 200 concurrent large uploads, public WAF upload behavior, disk throughput/capacity, or 200 mixed/heavy InVEST jobs. Keep those as separate capacity gates before claiming unrestricted 200-user capacity.
- Keep `MAX_SESSIONS=500` when the candidate is promoted; this is a low-cost retention/LRU ceiling, not an execution-concurrency setting. A limit of 50 would evict inactive users during a 200-user burst, while exactly 200 leaves no room for New Chat, reloads, or sessions retained for the 24-hour TTL.
- Execution remains intentionally bounded separately: eight concurrent Gemini calls with a 500-request wait queue and a 2.7M-token/minute safety budget. The 200-user fast test succeeded by queueing, but p95 was about 7.7 minutes; capacity therefore means no silent loss, not immediate responses.
- Most heavy InVEST model queues have Celery concurrency 1. If many users choose the same heavy model, those jobs serialize and may approach the 1800/2100-second Celery soft/hard limits. Same-tool bursts, mixed/heavy resources, cancellation, queue ETA/fairness, and the MSU public WAF path remain unvalidated.

## 200-user bottleneck assessment (2026-07-28)

- Current GCP host snapshot: 8 vCPU, 31 GiB RAM, no swap, and 23 GB free on the root/data filesystem. Idle available memory was 27 GiB. The Redis Session index was at its configured 500-session ceiling; new sessions can evict inactive LRU entries, so this is not a 200-user execution limit but does limit 24-hour history retention.
- The validated 200-user fast-tool result is a correctness/capacity pass, not a latency pass: 200/200 succeeded, but p95 was 459.5 seconds. At the configured 2.7M input-TPM budget and conservative 45K tokens per Gemini call, about 60 calls/minute are admitted; roughly two model calls per user make a 200-user burst mathematically about 6-7 minutes before overhead.
- Large uploads are the highest-priority hard blocker. Two upload paths still call `await uf.read()`, duplicating each complete file in Python memory. Two hundred largest guide packages are about 34.70 GB raw; this exceeds current GCP free disk before nginx/Starlette temporary buffering and exceeds the server's practical memory headroom for simultaneous whole-file reads.
- Same-tool heavy bursts are a separate queue bottleneck. Most Celery workers use concurrency 1 (a small set of lightweight queues use 2), so many users choosing one InVEST model serialize even when host CPU/RAM are idle. Do not globally raise all worker concurrency because GDAL/InVEST memory and process safety differ by tool.
- Recommended order: (1) chunked upload writes, partial-file cleanup, explicit per-file/session/global quotas and upload admission control; (2) move upload/temp/output storage to a volume with at least 100 GB free or object storage; (3) add queue depth/ETA/cancellation and per-tool limits; (4) run separate small-workflow, large-upload, same-heavy-tool, mixed, and MSU-WAF capacity ladders. Keep `MAX_SESSIONS=500`, Gemini concurrency 8, and the 500-request wait queue until new evidence justifies changing them.
- Scope clarification: the 23 GB free-space hard limit applies to the GCP validation host, not automatically to MSU. MSU's historical 62 GB RAM and 637 GB home capacity make persistent storage more likely to be adequate for 34.7 GB of raw uploads, provided uploads, nginx temporary bodies, Docker storage, and outputs actually reside on that large filesystem. Whole-file Python buffering remains unsafe by design: about 31.6 GiB of simultaneous file bytes plus the historical roughly 14 GB host/container baseline leaves limited headroom for multipart overhead and active models even on a 62 GB server.

## MSU 200-user public-WAF validation (2026-07-28)

- MSU originally still had `MAX_SESSIONS=50` and no capacity endpoint. With user approval, exact capacity runtime source from commit `ea641be` was applied as thin image `sha256:e46fad32944c4d5354302aaf40177d3de1bb5dadaf2a39254d124e0a29c6325a`; only `api-server` was recreated. Effective controls are 500 sessions, Gemini concurrency 8, queue 500, and 2.7M input-TPM safety budget.
- Public `https://ai.telecoupling.msu.edu/` fast-pool ladder passed: 10/10, 50/50, corrected 100/100, and final 200/200; every stage retained every test session. The original CBA prompt caused 2 retries at 10 users and 8 at 50 users; corrected 100/200 acceptance runs had zero retries. Final 200-user wall time was 380.0s, p50 269.5s, p95 345.6s, maximum 348.7s, and first-SSE p95 1.9s. All 200 runs used a small CSV and one of OLS/CO2/CBA/Food through the MSU WAF.
- The initial 100-user diagnostic was 98/100 because Gemini interpreted one CBA request as a workflow plan and falsely claimed one existing OLS upload was missing. Both original sessions succeeded immediately with unambiguous single-tool prompts; the acceptance rerun was 100/100 without retries. A prior 3/10 local attempt was invalid because the test process inherited a three-connection localhost proxy; only three requests reached MSU.
- Host CPU peaked at 60%; runnable-process queue peaked briefly at 25; minimum observed free+buffer+reclaimable-cache was 46.6 GiB. Gemini active/waiting peaked at 8/185 and the full 2.7M TPM budget was used, confirming quota pacing as the main latency source.
- Food worker memory peaked at 511.8/512 MiB and remained near the limit without OOM/restart during the test. After confirming both Food queues were empty, it received one maintenance restart and returned to 82.75 MiB. Raise only its memory limit to at least 768 MiB (preferably 1 GiB) before repeated production bursts; do not simultaneously raise concurrency.
- The cumulative ladder grew from 7 to 470/500 sessions, so it did not exercise LRU eviction at or above the 500-session ceiling. Post-test API/Redis were healthy, all relevant restart counts remained zero, OOM flags were false, active leases and tested queues returned to zero, and no backend/worker traceback was found. All 463 generated test sessions and their upload/output directories were removed; MSU returned to 7 pre-existing sessions.
- Scope remains limited: this does not validate 200 large uploads, 200 heavy/same-InVEST jobs, or unrestricted multi-step workflows. Full report and evidence locations: `docs/reports/MSU_CAPACITY_200_20260728.md` and MSU `~/csis-platform/capacity-results/msu-capacity-200-v1-ea641be-20260728/`. Rollback backup: `~/csis-platform/backups/20260728_capacity_200_ea641be_msu/`.

## Direct single-tool completion deployment (2026-07-28)

- GCP runs release `capacity-200-v2-direct-complete` from validated revision `d0a5f95` / tag `capacity-200-v2-direct-complete-r1`. The exact API image is `sha256:706f791afa41762df369f29fb6274825d3e1a4b519562ec08382e51b66ff3780`.
- `DIRECT_TOOL_COMPLETION_ENABLED=true` on the validated GCP and MSU API deployments. Source and templates default the flag to false.
- One explicit normal tool that returns a successful `tool_result` now emits `Analysis completed successfully. N output files were generated.` plus `Please interpret the results.` and ends without the second Gemini summary call. Workflow, multiple/ambiguous tools, render/read tools, missing inputs, failures, and explicit interpretation/summary/render requests keep the original Gemini loop.
- Real GCP OLS smoke generated three files and moved the Gemini reservation from 0 to exactly 45,000. A follow-up `Please interpret the results.` produced a 2,497-character explanation and used read tools as needed.
- Final simultaneous OLS/CO2/CBA/Food smoke passed 4/4 without retries in 2.76-3.77 seconds, retained 4/4 sessions, emitted only iteration 0 for each request, and reserved exactly 180,000 tokens total (4 x 45,000). The earlier 10-user probe passed 10/10 at p95 8.8 seconds and exposed the CBA alias gap that revision `d0a5f95` fixed.
- GCP rollback points: original runtime/image backup `~/csis-platform/backups/20260728_direct_complete_v2_cdd9eac_gcp/` with tag `csic_backend:pre-direct-complete-v2-cdd9eac-running-api`; pre-r1 backup `~/csis-platform/backups/20260728_direct_complete_v2_r1_d0a5f95_gcp/` with tag `csic_backend:pre-direct-complete-v2-r1-d0a5f95-running-api`.
- All generated direct-smoke and fast-pool sessions were deleted. The 10-user probe began at 499/500 sessions, exercised inactive-LRU eviction while adding ten sessions, and cleanup left 490/500; this was on the GCP test environment.
- MSU runs the same release and exact `d0a5f95` agent/config source in API image `sha256:f7feb31c8d26cc8005d4003623a30110de03a1236f960824769ca8963b4c1963`. Only `api-server` was recreated; Redis, nginx, Celery workers, data, environment files, and existing sessions were preserved.
- The same-scope public-WAF 200-user run passed 200/200 with 200/200 session retention and zero retries. Relative to v1, wall time fell from 380.0s to 195.5s (-48.6%), p50 from 269.5s to 64.7s (-76.0%), p95 from 345.6s to 160.6s (-53.5%), maximum from 348.7s to 164.1s (-52.9%), and throughput rose from 31.58 to 61.39 runs/min (+94.4%).
- First model/tool activity p95 changed only from 170.9s to 158.2s (-7.4%), while completion p95 fell by 185.0s. This confirms v2 removes the post-tool second Gemini wait but does not remove first-call TPM pacing. Gemini active/waiting peaked at 8/140 and the 2.7M safety budget was fully used.
- The Food worker again reached its 512 MiB hard limit without OOM. After confirming all fast queues and active leases were zero, a maintenance restart reduced it to 82.52 MiB. Raise only its memory limit to at least 768 MiB, preferably 1 GiB; do not simultaneously raise concurrency.
- All 200 v2 sessions and generated files were removed, restoring the original seven MSU sessions. Evidence: `~/csis-platform/capacity-results/msu-capacity-200-v2-direct-complete-20260728/`. Rollback backup: `~/csis-platform/backups/20260728_direct_complete_v2_r1_d0a5f95_msu/`; v1 image `sha256:e46fad32944c4d5354302aaf40177d3de1bb5dadaf2a39254d124e0a29c6325a`.
- The v2 result remains limited to small-CSV direct fast tools. It does not validate 200 large uploads, same-model heavy InVEST jobs, or unrestricted workflows.
- User-guide impact audit on 2026-07-29 scanned all 45 authoritative Markdown guides (43 single tools and 2 workflows). None claims that Gemini automatically supplies a final explanation/summary, and the standard single-tool instructions still correctly tell users to wait for the completed tool card and download outputs. Full guide rewrites and new screenshots are not required. An optional future batch edit may add one standard sentence to the 43 single-tool guides: after direct completion, type `Please interpret the results.` for an AI explanation. Workflow guides are unaffected.
- The optional guide enhancement was completed on 2026-07-30. All 43 single-tool Markdown guides now say `To get an AI explanation, type: Please interpret the results.` immediately after the completed-card instructions, and all 43 PDFs were regenerated from the same Markdown and existing screenshots. Validation covered 43/43 Markdown prompts, 43/43 extractable PDF prompts, and 76/76 referenced PDF images.
- The worktree `telecouplingAI-project/UserGuide/` copy was restored at the same time. Its Soybean ZIP, Markdown, PDF, and ten directly referenced images now match the expanded 11-system/10-flow release already on GCP/MSU. The three core hashes remain ZIP `7d11507b...`, Markdown `ff6ad52a...`, and PDF `ab171bcc...`.
- The 86 updated single-tool files (43 Markdown/PDF pairs) were deployed from one manifest to GCP and MSU and matched the local SHA-256 values at both sites. Sample-data ZIPs and workflow guides were not modified by this batch. Rollback backups are under each server's `~/csis-platform/backups/20260730_direct_completion_guides/`.
- Learning Center guide PDFs now use global cache version `20260730-direct-completion`; sample-data URLs do not inherit this version, and the Soybean sample ZIP retains its independent `20260729-systems-v2` version. Hot-deployed frontend bundle on both sites: `index-xR8BRM1J.js`. This remains a hot static update, not frontend image solidification.

## Upload-size evidence checkpoint (2026-07-28)

- nginx currently permits `client_max_body_size 500M` for chat/upload requests, but this is a request-body configuration limit, not a validated safe upload size; multipart overhead also means usable file bytes are slightly lower.
- Largest surviving GCP upload attributable to one task: Coastal Vulnerability, 29 files totaling 171,328,574 bytes (171.33 MB / 163.39 MiB). Largest surviving individual uploaded file: Offshore Wind `claybark_dem.tif`, 169,748,887 bytes (169.75 MB / 161.89 MiB).
- A 355,123,328-byte GCP session directory is cumulative across many sequential tool tests and must not be reported as one task.
- The largest explicitly documented successful upload through the MSU WAF is the roughly 18 MB SDR input set. An attempted roughly 811 MB Wave Energy `WaveData/` upload returned HTTP 413, so that dataset is now server-resident and not user-uploaded.
- Authoritative User Guide inventory on GCP contains 43 single-tool sample ZIPs and two workflow sample ZIPs. Actual upload size means the sum of extracted files, because users upload the extracted contents rather than the compressed ZIP.
- Largest guide upload sets: Coastal Vulnerability is 173,518,490 bytes (173.52 MB / 165.48 MiB, 50 files; 39.80 MB ZIP), and Scenic Quality is 169,764,205 bytes (169.76 MB / 161.90 MiB, 15 files; 24.84 MB ZIP). Of the 43 tool packages, only these two exceed 100 MiB; three are 10-100 MiB, 11 are 1-10 MiB, and 27 are at most 1 MiB.
- Server-resident model data is correctly excluded from the guide upload requirement: the Wave Energy guide uploads only about 0.002 MiB. The Wind Energy guide upload is about 1.594 MiB.
- Workflow upload sets are small: Soybean is 357,242 bytes (0.357 MB / 0.341 MiB, 20 files), and Tourism is 1,882,138 bytes (1.882 MB / 1.795 MiB, 13 files).
- A simultaneous 200-user Coastal Vulnerability upload would introduce about 34.70 GB (32.32 GiB) of request payload before multipart and runtime overhead. The current whole-file `await uf.read()` implementation is not safe evidence for that scenario; large-upload concurrency remains a separate implementation and GCP load-test gate.

## Admin error registry checkpoint (2026-07-28)

- The implemented design is Celery/API structured events -> Redis Stream -> one API-hosted collector -> PostgreSQL. Workers do not open independent PostgreSQL pools. JSON container logs remain the fallback for database/Redis failures and hard process termination.
- PostgreSQL stores fingerprint groups, individual occurrences, Admin users/sessions, and Admin audit records. Default retention is 90 days. Inputs are represented only by bounded filename/extension/size metadata; prompts, file contents, API keys, and internal source paths are not exposed through the Admin API.
- `/admin/errors` uses independent Argon2id credentials, opaque server-side sessions, HttpOnly/SameSite cookies, CSRF checks, login throttling, status/assignment/notes, grouped search, and manual evidence preservation/download.
- Evidence preservation validates the recorded session ID, rejects symlinks and paths outside configured upload/output roots, enforces a 2 GiB limit, and atomically publishes a completed evidence directory. Evidence is not copied permanently unless an Admin explicitly preserves it.
- `ERROR_REGISTRY_ENABLED` and `ADMIN_ENABLED` are intentionally separate. GCP collection may run while Admin login remains disabled because the current GCP public endpoint is HTTP. Never enable GCP Admin login over public HTTP; add trusted HTTPS first. MSU may enable Admin because its public endpoint is HTTPS through the WAF.
- Each server currently has its own PostgreSQL registry. The environment filter is useful within exported/centralized data, but a single page cannot query both servers until a central database or cross-site collector is added.
- Local validation covered Python compilation, 26 focused backend tests, frontend production build, Compose rendering, and two read-only code reviews. PostgreSQL/Redis/container integration and public-path behavior remain GCP deployment gates.
- GCP candidate `error-registry-v1-dd62107` was deployed on 2026-07-28. Backend image ID: `sha256:0aeff852cd217fa1871a1fbe87bcfb5f7de058b35136102d18b9e8b80c67868d`; frontend image ID: `sha256:fb5aaec367272d1331876b6b521aa705f07eb083bccf6aae1d52c92f7686afb6`.
- GCP rollback tags are `csic_backend:pre_error_registry_dd62107` (`sha256:b3c81a...`) and `csic_frontend:pre_error_registry_dd62107` (`sha256:f92245...`). Source/env backup: `~/csis-platform/backups/20260728_error_registry_v1_dd62107/`.
- GCP validation passed with 40/40 Compose services running, zero unhealthy/restarting services, healthy PostgreSQL, Redis pending count zero, and public `/health` success. A real unknown-tool Celery probe persisted one occurrence and one fingerprint group through Redis/PostgreSQL; the probe rows were deleted afterward.
- GCP `/admin/errors` SPA routing returns 200. Its Admin backend is enabled only for the established SSH-tunnel path; nginx blocks direct public `/api/admin/*` access with 403 because GCP still lacks trusted public HTTPS. Do not remove that restriction until trusted HTTPS exists.
- On 2026-08-02, the Admin password was reset to the same new operator-provided credential on GCP 1 and GCP 2 only; MSU was intentionally unchanged because it was unreachable. Each host's `.env.docker` retains the Compose-safe doubled-dollar Argon2id hash, only `api-server` was recreated, and old Admin sessions were deleted. Full local SSH-tunnel checks passed on both hosts: SPA, login, session, and logout all returned 200. Direct public-IP Admin API access remains intentionally blocked and will make the otherwise visible SPA show `Request failed`. Rollback copies are under `~/csis-platform/backups/20260802_gcp_admin_password_reset/`; no plaintext password or hash is stored in Git.
- MSU Error Registry was fully deployed on 2026-07-31. Public entry: `https://ai.telecoupling.msu.edu/admin/errors`; the SPA returns 200 and an unauthenticated `/api/admin/session` returns the expected 401. MSU uses `ERROR_REGISTRY_ENABLED=true`, `ADMIN_ENABLED=true`, `ERROR_ENVIRONMENT=msu`, Secure cookies, and the existing GCP Admin username/password credential hash. The PostgreSQL password was generated locally on MSU and was not returned or committed.
- MSU registry runtime identities: backend `sha256:6971bb9fda6b4dd9ce08f6b18803753309d5b7cf92da7da2f76ae9e12594b934`, frontend `sha256:4a9c5213d9a4758b06926a98a414e94ffaa4688836f475909a1ea63886bd47eb`, PostgreSQL `sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777`, and named volume `telecouplingai-project_error_db_data`. All 35 API/Celery services use the same backend image; all 40 Compose services run with zero unhealthy/restarting containers.
- MSU validation passed Redis Stream -> collector -> PostgreSQL with one marked deployment event; the event, fingerprint group, and Redis stream entry were removed afterward, leaving zero groups, occurrences, and pending events. Public chat still succeeds while the frontend sends the 2.5 compatibility ID and the backend logs actual `gemini-3.5-flash`.
- MSU rollback source/env/Compose/container records are under `~/csis-platform/backups/20260731_msu_error_registry/`; image rollback tags are `csic_backend:pre-msu-error-registry-20260731` and `csic_frontend:pre-msu-error-registry-20260731`.

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
  - Domestic systems: yellow.
  - Adjacent systems: cyan.
  - Distant systems: magenta.
  - Unknown/no-match cases are normalized to Distant systems; the legend should show only Domestic systems / Adjacent systems / Distant systems.
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
- Soybean guide systems/flow data was expanded on 2026-07-29 without changing workflow code or the other 18 sample files. `DrawRadialFlows.csv` contains 10 illustrative lines: 4 Distant systems (the original China/Spain/Netherlands/Thailand endpoints), 3 Domestic systems (Cuiaba, Sao Paulo, Rio de Janeiro), and 3 Adjacent systems (Montevideo/Uruguay, Buenos Aires/Argentina, Asuncion/Paraguay). `Brazil_Systems_pfm.csv` contains the matching 11 points: one Brazil sending point and all 10 receiving endpoints. The explicit `Flow_Relation` column makes flow classification deterministic; all `Quantity` values remain demonstration values of 1.
- The updated Soybean ZIP, Markdown guide, fully regenerated 16-page PDF, and 10 directly referenced guide images are external User Guide assets, not Git-tracked test data. Identical copies are live on GCP and MSU under `outputs/user-guides/Workflow_01_soybean_telecoupling_User_Guide/`. Public ZIP SHA-256: `7d11507b3f636a574c95fea0c92f2fe1255b57272934d255c9c08121abd1f3d6`; PDF SHA-256: `ab171bccc70b9e02a363e8202d9b1a9597740de9166c794022efb6217ee86aad`. Server backups: `~/csis-platform/backups/20260729_soybean_flow_categories/` and `~/csis-platform/backups/20260729_soybean_system_points/`.
- Targeted GCP validation ran the real systems, radial-flow, single-map, and composite-scene paths: 11/11 system rows and 10/10 flow rows produced geometry; roles were 1 sending / 10 receiving; relation counts were 3 domestic / 3 adjacent / 4 distant; and all new maps/legends matched. The unchanged crop and habitat inputs were not rerun.
- The Learning Center adds `?v=20260729-systems-v2` to the Soybean PDF and ZIP URLs so browsers and the MSU WAF cannot reuse the old same-filename assets. Hot-deployed frontend bundle on GCP/MSU: `index-D2cqdaUX.js`. This is a hot static update, not frontend image solidification.

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
- GitHub backup for the 2026-07-12 documentation/render/thinking solidification source changes was pushed to `origin/codex/msu-latest-20260704` on 2026-07-12. The first backup commit was `4bb2ad3` (`feat: solidify documentation and map rendering updates`). Public UserGuide PDF/zip asset directories were intentionally not added to Git because they contain sample data/assets and are served from the server host data directories.

## Hot-patch discipline checkpoint (2026-07-12)

- User rule clarified: after function changes, first hot-patch and let the user test. Only solidify Docker images when the user explicitly says to solidify; do not eagerly rebuild, commit, retag, or force-recreate images while more hot changes may be coming.
- MSU and GCP `tele-celery-render` containers were hot-patched for flow/system rendering changes by syncing host source files, copying them into `/app/renderers/`, and restarting only `tele-celery-render`.
- Current source flow/system behavior uses Domestic systems / Adjacent systems / Distant systems; flow line widths remain half of the previous values. Commit `8aeba48` and frontend bundle `index-VMleCgSm.js` were hot-deployed to GCP and MSU on 2026-07-28. Both real QGIS runtime checks and public frontend/health checks passed. These changes are not yet solidified into Docker images. Backups: GCP `/home/csisaiproject2026/csis-platform/backups/20260728_system_labels_footer_8aeba48/`; MSU `/home/jianan2/csis-platform/backups/20260728_system_labels_footer_8aeba48/`.
- The chat footer `Contact us` target is `https://v.wjx.cn/vm/eRrSxQS.aspx#` as of commit `a6b2ba1`. Frontend bundle `index-Ce83RVT0.js` was hot-deployed to GCP 1, GCP 2, and MSU on 2026-07-31; no container was rebuilt or restarted. Public bundle checks and the contact target returned HTTP 200. Per-host rollback backups: `~/csis-platform/backups/20260731_contact_link_a6b2ba1/`.
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

## Production source reconciliation checkpoint (2026-07-12)

- The verified production source baseline is Git commit `b3d1ebb` on the historical branch `codex/msu-latest-20260704`; that branch name is dated, but the commit includes the 2026-07-12 documentation, thinking guard, and map-rendering solidification work.
- Use the long-lived `production` branch as the canonical deployment source going forward. Create feature branches from `production`; do not develop from the old POC `master`.
- The 36 older/missing MSU host files and the GCP deployment-helper gaps were reconciled from an explicit tracked-file archive. Both host-source trees now match the canonical deployment source after normalized line-ending comparison.
- The read-only drift audit is `telecouplingAI-project/deploy/audit_production_drift.py`. Server metadata and observed image identities are in `telecouplingAI-project/deploy/production_inventory.json`.
- Never synchronize active `.env` files, `.env.docker`, backend environment files, TLS certificates/private keys, outputs, uploads, model data, demo inputs, Systematic test data, or external User Guide assets as part of source reconciliation.
- MSU and GCP external User Guide trees matched byte-for-byte (232 files). Runtime Skill trees matched byte-for-byte (44 files).
- MSU nginx received the same cache policy already active on GCP: `index.html`/SPA responses use `Cache-Control: no-cache`, while hashed `/assets/*` files use one-year immutable caching. Backup: `~/csis-platform/backups/20260712_nginx_no_cache/nginx.conf.before`.
- Source reconciliation does not imply a container deployment. Do not restart, recreate, or retag containers merely to make host source match Git.
- The post-sync full audit at deployment-source commit `024615e` passed all scopes: 165 host files per server, 75 API/render runtime files per container, 44 Skills, 3 active frontend files, and 232 external User Guide files. Public health checks passed and no business container was restarted or recreated.
- Reconciliation backups are under MSU `/home/jianan2/csis-platform/backups/20260712_source_reconciliation_a484d7a/` and GCP `/home/csisaiproject2026/csis-platform/backups/20260712_source_reconciliation_a484d7a/`.
- GitHub branch consolidation completed on 2026-07-12: default branch `production`; all five former long-lived/history branch tips retained as annotated `archive/*` tags; no other remote heads remain.
- Repository-root cleanup completed without changing the controlled deployment tree: the stale README was replaced, historical documents/demos moved under `docs/`, and committed Node/Redis/runtime artifacts removed. Post-cleanup MSU/GCP host-source audit still passed all 165 controlled files.
