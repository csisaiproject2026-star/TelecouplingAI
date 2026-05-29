# Deploy CSIS Platform → New Server (MSU)  — Working Plan & Memory

> **GOAL:** Replicate the GCP deployment 1:1 on the new server so the platform runs at `http://35.9.219.33/`, same as `http://34.42.83.50/`.
> This file is the durable memory for the deployment. Update the checkboxes as steps complete.

## Servers

| | GCP (source, live) | New MSU server (target) |
|---|---|---|
| SSH alias | `csis-gcp` | `csis-msu` |
| Address | `34.42.83.50` | `35.9.219.33` |
| User | `csisaiproject2026` | `jianan2` |
| Key | `~/.ssh/id_ed25519_csis` | `~/.ssh/id_ed25519_msu` (new, dedicated) |
| OS | (csis-server) | RHEL 9.7, 32-core, 62G RAM, /home 637G |
| Docker | installed, 38 containers up | **NOT installed yet** |
| Auth for Claude | key ✅ | key install in progress |

`~/.ssh/config` already has `csis-gcp` and `csis-msu` host blocks.

## GCP deployment structure (verified 2026-05-27 — authoritative, DEV_LOG older paths are stale)

- Project dir: `~/csis-platform/telecouplingAI-project/` (server is NOT a git repo)
- **`datainput_for_demo` is a SYMLINK → `Systematic_tests/Test_data/`** (1.7 GB: WaveData 811M, _shared/Base_Data/global_dem.tif + global_polygon.*, per-tool model_data, 42 tool dirs). compose mounts `./datainput_for_demo:/data/datainput:ro` through it.
- Host `/data/` bind-mount sources (OUTSIDE project dir):
  - `/data/model_data` (71M) → mounted `/data/model_data:ro`  — **must copy**
  - `/data/outputs` (8.5G) → runtime output — **do NOT copy** (regenerated)
  - `/data/uploads` (1.9G) → runtime uploads — **do NOT copy** (regenerated)
- `.env` (compose vars): HOST_SHARED_DIR, HOST_UPLOADS_DIR, HOST_MODEL_DATA_PATH, HOST_DATAINPUT_PATH
- `.env.docker` (container env): real GOOGLE_API_KEY + `FILE_SERVER_URL=http://34.42.83.50:8001/download/`  ← **only value that MUST change per server**
- Images: `csic_backend:latest` 7.71G (FROM condaforge/miniforge3 + mamba gdal/geos/proj/geopandas/qgis/r-* + pip natcap.invest==3.14.3, pygeoprocessing==2.4.10, google-genai, celery), `csic_frontend:latest` 93M (vite). Build is heavy.
- Runtime: 38 containers (1 backend + 1 nginx + 1 frontend + 1 redis + 1 fileserver + 33 celery workers).

## Key differences on new server (decisions)

1. **Host data dirs moved off `/data/` → under `/home/jianan2/csis-data/`** (user owns /home, 637G, avoids root for data). Set `HOST_SHARED_DIR`/`HOST_UPLOADS_DIR`/`HOST_MODEL_DATA_PATH` in `.env` accordingly.
2. **`.env.docker` `FILE_SERVER_URL` → `http://35.9.219.33:8001/download/`** (keep same GOOGLE_API_KEY).
3. **Backend/frontend images: REBUILD on new server** (`docker compose build`) — fast university internet + 32 cores; avoids 3G image transfer. Fallback: stream image GCP→local→MSU if build fails.
4. **Data (1.8G): pull directly MSU ← GCP** via rsync over SSH (set up MSU→GCP key), not relayed through local uplink.

## Plan / Checklist

- [x] **P0. SSH key access to MSU** — DONE 2026-05-27. `ssh csis-msu` works passwordless (key `id_ed25519_msu`). Fix that worked: key comment kept wrapping to a 2nd line on paste → dropped the comment, used `head -1` to keep just `ssh-ed25519 <base64>` (valid entry), then `restorecon -Rv ~/.ssh` for SELinux. authorized_keys is 1 line. (Harmless warning: server OpenSSH lacks post-quantum KEX.)
- [x] **P0b. sudo for autonomy** — DONE 2026-05-27. Chose A: `/etc/sudoers.d/jianan2` = `jianan2 ALL=(ALL) NOPASSWD:ALL` (perms set 440). `ssh csis-msu 'sudo -n ...'` works. Claude now fully autonomous on MSU (key + NOPASSWD sudo). To revoke later: `sudo rm /etc/sudoers.d/jianan2`.
- [x] **P1. Install Docker CE** — DONE 2026-05-27. Docker 29.5.2 + Compose v5.1.4 + containerd 2.2.4 installed from docker-ce-stable (CentOS repo) on RHEL 9. `systemctl enable --now docker` ok. `usermod -aG docker jianan2` done (effective on next login).
- [x] **P2. Code** — DONE. tar-over-ssh MSU←GCP (rsync absent on GCP). Relative `datainput_for_demo` symlink. Gotcha: inner ssh needs `-n` or it eats the heredoc stdin.
- [x] **P3. Data** — DONE. Test_data 1.7G + model_data 71M pulled from GCP via MSU→GCP key.
- [x] **P4. Host dirs** — DONE. `/home/jianan2/csis-data/{outputs,uploads,model_data}`.
- [x] **P5. Config** — DONE. `.env` (/home paths) + `.env.docker` (Gemini key + FILE_SERVER_URL=35.9.219.33). compose config validates.
- [x] **P6. Images + up** — DONE. Transferred images from GCP (`docker save|load`), not rebuilt. 38/38 containers up, backend healthy.
- [x] **P7. Firewall** — DONE (host). firewalld http + 8001/tcp open. ⚠️ Off-campus inbound 80 blocked by MSU network boundary (503, never reaches nginx); SSH/22 allowed. Needs MSU IT to open 80/8001, or use campus/VPN.
- [x] **P8. Verify** — DONE. Internal/server-public GET / & /health = 200. Agent `list all tools` ✅ (Gemini). Tools #28 OLS ✓, #30 CO2 ✓, #5 Crop Percentile (InVEST+model_data) ✓.

**→ Full deployment log: `msu_dev.md` (repo root).**

## Status log
- 2026-05-27: GCP structure inspected & verified. Key `id_ed25519_msu` generated, config added.
- 2026-05-27: **P0 DONE — `ssh csis-msu` passwordless works.** NOPASSWD sudo granted.
- 2026-05-28: **ALL PHASES DONE (P0–P8). Platform deployed & verified on MSU.** 38/38 containers, Gemini agent + 3 tools PASS. Only open item: MSU border firewall blocks off-campus port 80. Full log → `msu_dev.md`.
