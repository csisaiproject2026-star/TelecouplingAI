# MSU Server Deployment Log — CSIS Platform

**Goal:** Replicate the live GCP deployment 1:1 on the new MSU server so users can use the platform.
**Date:** 2026-05-27/28
**Result:** ✅ Platform fully deployed and verified. 38/38 containers up, backend healthy, Gemini agent + 3 tools end-to-end PASS. Website + file downloads work over **port 80** from a client machine (downloads repointed off the blocked :8001 to nginx `/download/`). Note: the only access gotcha is a **local proxy on the dev machine** (127.0.0.1:29758) that returns 503 — bypass it for `35.9.219.33`. Off-campus/public reachability not tested from a true external vantage (see §5).

---

## 1. Servers & access

| | GCP (source, live) | New MSU server (target) |
|---|---|---|
| SSH alias (in `~/.ssh/config`) | `csis-gcp` | `csis-msu` |
| Address | `34.42.83.50` | `35.9.219.33` |
| User | `csisaiproject2026` | `jianan2` |
| Key | `~/.ssh/id_ed25519_csis` | `~/.ssh/id_ed25519_msu` (new, dedicated) |
| OS | (csis-server) | RHEL 9.7, 32-core Xeon, 62 GB RAM, `/home` 637 GB |
| Hostname | csis-server | csis-telecoupling |

**Autonomous access set up (so Claude can operate/redeploy without prompts):**
- Passwordless SSH: `ssh csis-msu` (key `id_ed25519_msu`). Public key installed in `~jianan2/.ssh/authorized_keys`. Needed `restorecon -Rv ~/.ssh` because RHEL SELinux mislabels a freshly-created `authorized_keys`.
- Passwordless sudo: `/etc/sudoers.d/jianan2` = `jianan2 ALL=(ALL) NOPASSWD:ALL` (mode 440). Revoke later with `sudo rm /etc/sudoers.d/jianan2`.
- MSU→GCP key: `~/.ssh/id_gcp` on MSU, its pubkey added to GCP `authorized_keys`, so MSU can pull directly from GCP. GCP firewall allows inbound SSH from MSU.

---

## 2. Architecture (replicated from GCP, verified)

- Project dir: `~/csis-platform/telecouplingAI-project/` (NOT a git repo — transferred via tar/ssh).
- `datainput_for_demo` → **relative symlink** → `Systematic_tests/Test_data/` (1.7 GB: WaveData 811M, `_shared/Base_Data/global_dem.tif` + `global_polygon.*`, per-tool data, 42 tool dirs).
- Host bind-mount dirs moved to `/home` (637 GB, user-owned, no root needed) — **differs from GCP's `/data/`:**
  - `/home/jianan2/csis-data/outputs`  (runtime tool outputs)
  - `/home/jianan2/csis-data/uploads`  (runtime user uploads)
  - `/home/jianan2/csis-data/model_data` (71 MB crop yield tables, copied from GCP `/data/model_data`)
- Images: `csic_backend:latest` (7.66 GB, conda+QGIS+GDAL+R+natcap.invest 3.14.3) and `csic_frontend:latest` (91.6 MB) — **transferred from GCP** via `docker save | docker load` (not rebuilt) for an exact, proven replica.
- Stack: 1 nginx (:80) + 1 backend + 1 frontend + 1 redis + 1 fileserver (:8001) + 33 celery workers (one queue per tool) = **38 containers**.

### Config files (created on server, gitignored / not in repo)
`.env` (compose var substitution):
```
HOST_SHARED_DIR=/home/jianan2/csis-data/outputs
HOST_UPLOADS_DIR=/home/jianan2/csis-data/uploads
HOST_MODEL_DATA_PATH=/home/jianan2/csis-data/model_data
HOST_DATAINPUT_PATH=/home/jianan2/csis-platform/telecouplingAI-project/datainput_for_demo
```
`.env.docker` (container env) — identical to GCP except `FILE_SERVER_URL`:
```
GOOGLE_API_KEY=<Gemini key, same as GCP>
FILE_SERVER_URL=http://35.9.219.33/download/        # ← port 80 (NOT :8001) — see §5
DEFAULT_MODEL=gemini-2.5-flash
... (SHARED_DIR, UPLOADS_DIR, QGIS_*, REDIS_URL, MODEL_DATA_PATH, SESSION_TTL_HOURS=24, MAX_SESSIONS=50, AUTH_REQUIRED=false)
```
> **Downloads route through port 80**, not 8001. nginx has `location /download/ { proxy_pass http://fileserver/download/; }`, so the file-server is reachable via `http://IP/download/...` without exposing 8001. Verified: a file in `~/csis-data/outputs/` downloads with HTTP 200 over port 80 from a client machine. (GCP used :8001 because that port was open there; on MSU only 80 is reachable.)

---

## 3. Step-by-step log (P0–P8)

**P0 — Access.** Generated `id_ed25519_msu`; added `csis-msu`/`csis-gcp` blocks to `~/.ssh/config`. Installed pubkey (one line; dropped the comment that kept wrapping on paste). `restorecon -Rv ~/.ssh` fixed SELinux. `ssh csis-msu` → passwordless ✅. Granted NOPASSWD sudo ✅.

**P1 — Docker.** RHEL 9: added docker-ce CentOS repo, `dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin --allowerasing`. Result: **Docker 29.5.2 + Compose v5.1.4 + containerd 2.2.4**. `systemctl enable --now docker`; `usermod -aG docker jianan2` (docker now runs without sudo). data-root `/var/lib/docker` on `/` (70G, 61G free — sufficient), driver overlayfs.

**P2 — Code.** `tar`-over-ssh pull MSU←GCP (rsync not installed on GCP). Excluded `outputs/ uploads/ *.log .pytest_cache __pycache__ datainput_for_demo`. Recreated `datainput_for_demo` as a **relative** symlink (GCP's was an absolute path that wouldn't resolve on MSU).
- **Gotcha:** nested `ssh ... 'tar cf -' | tar xf` inside a `ssh 'bash -s' <<heredoc` — the inner ssh ate the heredoc as its stdin and truncated the script. **Fix: `ssh -n`** (stdin from /dev/null) on the inner ssh.

**P3 — Data.** `Systematic_tests/Test_data` 1.7 GB + `/data/model_data` 71 MB pulled from GCP. WaveData 811M reachable through the symlink ✅.

**P4–P5 — Config.** Wrote `.env` (host dirs → `/home`) and `.env.docker` (Gemini key + `FILE_SERVER_URL` → `35.9.219.33`). `docker compose config` validates; `datainput` source resolves correctly.

**P6 — Images + launch.** `docker save csic_backend:latest csic_frontend:latest` on GCP → streamed → `docker load` on MSU (exit 0, both loaded). `docker compose up -d` → all 38 containers Started; redis/nginx pulled from Docker Hub.

**P7 — Firewall.** `firewall-cmd --add-service=http --permanent` + `--add-port=8001/tcp --permanent` + reload. firewalld active zone now lists `http` + `8001/tcp`.

**P8 — Verification.** See §4.

---

## 4. Verification results

| Check | Result |
|---|---|
| Containers running | **38 / 38** (none exited/restarting) |
| `tele-backend` health | **healthy** — log: `CSIS backend started ✅`, uvicorn on :8000 |
| Internal `GET /health` | **200** |
| Internal `GET /` (frontend) | **200** |
| Server→own public IP `GET /health` | **200** (nginx logs it: `35.9.219.33 ... 200`) |
| **Agent end-to-end** `POST /api/chat "list all tools"` | **✅** full correct tool catalog via Gemini (Recreation #26 correctly excluded) — **Gemini key works** |
| Tool #28 OLS Regression (LLM→celery→worker) | **✓ PASS** 35.8s |
| Tool #30 CO2 Emissions | **✓ PASS** 28.5s |
| Tool #5 Crop Production Percentile (InVEST + model_data mount) | **✓ PASS** 26.9s |

Conclusion: web UI serves, Gemini agent works, TeleBox + InVEST tools execute end-to-end with the transferred data. The platform is operational on the server.

---

## 5. Access / ports — CORRECTED findings

Earlier guess ("MSU blocks port 80") was **WRONG**. Re-tested from the dev Windows machine:
- The **503** seen via `curl http://35.9.219.33/` was caused by a **local forward proxy on the dev machine** (`HTTP_PROXY=http://127.0.0.1:29758`, system `ProxyEnable=1 ProxyServer=localhost:29758` — a VPN/proxy client). That proxy refused the destination and returned 503. With `curl --noproxy '*'` → **200**.
- Raw TCP from the dev machine (no proxy): **port 80 OPEN ✅, port 22 OPEN ✅, port 8001 CLOSED ❌**.
- **Port 80 (website + API + downloads): reachable.** Verified end-to-end from the dev machine: `GET /` 200, `GET /health` 200, and a real file download via `http://35.9.219.33/download/...` → **HTTP 200** with correct content.
- **Port 8001 is blocked** between the dev machine and the server → that's why `FILE_SERVER_URL` was repointed to port 80 (§2). Downloads no longer need 8001.

**Practical guidance:**
- To open the site in the **browser on the dev machine**: if it shows 503, the browser is going through the `127.0.0.1:29758` proxy — turn that proxy off, or add `35.9.219.33` to its direct/bypass list. Then `http://35.9.219.33/` loads.
- The dev machine reaches the server via the campus network (server's last login was from a `172.21.x` private IP). **Public/off-campus reachability was NOT tested from a truly external vantage point** (Claude runs on the dev machine). If off-campus public access is required, test from a non-campus network or ask MSU IT to confirm inbound 80 is open to the internet.
- Host firewall (firewalld) has 80 + 8001 open; 8001 is now unused.

---

## 6. Operations runbook (MSU)

All commands run from anywhere with `ssh csis-msu` (passwordless). Project dir `~/csis-platform/telecouplingAI-project/`.

```bash
# status
ssh csis-msu 'docker ps --format "{{.Names}}\t{{.Status}}" | sort'
ssh csis-msu 'cd ~/csis-platform/telecouplingAI-project && docker compose ps'

# restart everything / one service
ssh csis-msu 'cd ~/csis-platform/telecouplingAI-project && docker compose restart'
ssh csis-msu 'cd ~/csis-platform/telecouplingAI-project && docker compose restart tele-nginx'

# logs
ssh csis-msu 'docker logs --tail 50 tele-backend'

# health / quick test (on server)
ssh csis-msu 'curl -s -o /dev/null -w "%{http_code}\n" http://localhost/health'

# redeploy backend code after editing (no sudo needed):
#   1) copy changed files into ~/csis-platform/telecouplingAI-project/backend/ (scp or tar)
#   2) rebuild image OR re-pull from GCP, then:
ssh csis-msu 'cd ~/csis-platform/telecouplingAI-project && docker compose up -d --force-recreate'

# run a tool end-to-end (inside backend container, full LLM path):
ssh csis-msu 'docker exec tele-backend bash -lc "cd /home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/AI_GCP_llm_test && python run_AI_GCP_llm_test.py --ids 28"'
```

Note: the backend container's internal path keeps the GCP username (`/home/csisaiproject2026/...`) because that string is the container mount target in docker-compose.yml — harmless, it's inside the container.

---

## 7. Differences from GCP (summary)
1. Host data dirs under `/home/jianan2/csis-data/` instead of `/data/` (avoids root; `/home` is the 637 GB volume).
2. `FILE_SERVER_URL` IP = `35.9.219.33`.
3. `datainput_for_demo` symlink is **relative** (`Systematic_tests/Test_data`) so it survives the different home path.
4. RHEL 9 + SELinux (vs GCP). Docker CE default has SELinux confinement off, so bind mounts work without `:z`. `authorized_keys` needed `restorecon`.
5. Images transferred (not rebuilt).
```
```
