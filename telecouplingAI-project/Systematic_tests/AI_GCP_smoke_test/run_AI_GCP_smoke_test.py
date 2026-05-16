#!/usr/bin/env python3
"""
AI_GCP_smoke_test — Quick smoke + light load check for the CSIS platform.

Tests the full pipeline: file upload → /api/chat LLM → Celery worker → result.

Phase 1 : 1 user, 4 tools sequentially  (baseline latency)
Phase 2 : N concurrent users, staggered arrival, shuffled tool order  (concurrency)

Tools tested (representative mix):
  07  Carbon Storage     — fast InVEST,  2 files
  09  Annual Water Yield — moderate InVEST, shapefile + rasters
  28  OLS Regression     — TeleBox, 1 CSV
  30  CO2 Emissions      — TeleBox, 1 CSV

Usage (run on GCP host):
    python3 .../Systematic_tests/AI_GCP_smoke_test/run_AI_GCP_smoke_test.py
    python3 ...  --phase 1            # sequential baseline only
    python3 ...  --phase 2            # concurrency only
    python3 ...  --users 5            # override Phase 2 user count (default 3)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL         = "http://localhost"       # nginx → tele-backend
DATA             = Path("/home/csisaiproject2026/csis-platform/telecouplingAI-project/Systematic_tests/Test_data")
MODEL            = "gemini-2.5-flash"
ARRIVAL_WINDOW_S = 8.0                      # Phase 2: user spread window (seconds)
METRICS_INTERVAL = 5                        # seconds between resource samples

# ── Tool definitions ──────────────────────────────────────────────────────────

SMOKE_TOOLS = [
    # (label, [files], prompt, timeout_s)
    (
        "07_CarbonStorage",
        [
            DATA / "07_carbon_storage/lulc_current_willamette.tif",
            DATA / "07_carbon_storage/carbon_pools_willamette.csv",
        ],
        "Run Carbon Storage on the uploaded files.",
        90,
    ),
    (
        "09_AnnualWaterYield",
        [
            DATA / "09_annual_water_yield/watershed_gura.shp",
            DATA / "09_annual_water_yield/watershed_gura.dbf",
            DATA / "09_annual_water_yield/watershed_gura.prj",
            DATA / "09_annual_water_yield/watershed_gura.shx",
            DATA / "09_annual_water_yield/land_use_gura.tif",
            DATA / "09_annual_water_yield/precipitation_gura.tif",
            DATA / "09_annual_water_yield/reference_ET_gura.tif",
            DATA / "09_annual_water_yield/depth_to_root_restricting_layer_gura.tif",
            DATA / "09_annual_water_yield/plant_available_water_fraction_gura.tif",
            DATA / "09_annual_water_yield/biophysical_table_gura.csv",
        ],
        "Run Annual Water Yield on the uploaded files.",
        240,
    ),
    (
        "28_OLS",
        [
            DATA / "28_ols/ols_data.csv",
        ],
        "Run OLS Regression on the uploaded CSV. "
        "dependent_variable=y, independent_variables=x1,x2,x3.",
        60,
    ),
    (
        "30_CO2Emissions",
        [
            DATA / "30_co2_emissions/co2_data.csv",
        ],
        "Run CO2 Emissions analysis on the uploaded CSV. "
        "animal_count_field=animals, length_km_field=distance_km, "
        "capacity_per_trip=50, co2_per_km_per_trip=2.6.",
        60,
    ),
]

# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    label:        str
    success:      bool
    duration:     float
    retried:      bool          = False
    output_files: list          = field(default_factory=list)
    error:        Optional[str] = None


@dataclass
class UserResult:
    user_id:        str
    tool_results:   list  = field(default_factory=list)
    total_duration: float = 0.0
    start_delay_s:  float = 0.0

    @property
    def n_pass(self): return sum(1 for t in self.tool_results if t.success)
    @property
    def n_fail(self): return sum(1 for t in self.tool_results if not t.success)
    @property
    def n_tools(self): return len(self.tool_results)


@dataclass
class MetricSample:
    ts:           float
    cpu_pct:      float
    mem_used_mb:  float
    mem_total_mb: float
    net_rx_mb:    float
    net_tx_mb:    float


# ── System metrics (reads /proc — valid on GCP host) ─────────────────────────

def _proc_stat() -> tuple[int, int]:
    with open("/proc/stat") as f:
        parts = f.readline().split()
    vals = [int(x) for x in parts[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def _proc_mem() -> tuple[float, float]:
    info: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k.strip()] = int(v.split()[0])
    used = info.get("MemTotal", 0) - info.get("MemAvailable", 0)
    return used / 1024, info.get("MemTotal", 0) / 1024   # MB


def _proc_net(iface: str = "eth0") -> tuple[float, float]:
    with open("/proc/net/dev") as f:
        for line in f:
            if iface in line:
                cols = line.split()
                return int(cols[1]) / 1_048_576, int(cols[9]) / 1_048_576
    return 0.0, 0.0


async def metrics_collector(samples: list, stop: asyncio.Event) -> None:
    prev_idle, prev_total = _proc_stat()
    await asyncio.sleep(METRICS_INTERVAL)
    while not stop.is_set():
        try:
            idle, total = _proc_stat()
            d_idle, d_total = idle - prev_idle, total - prev_total
            cpu = 100.0 * (1 - d_idle / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total
            mem_used, mem_total = _proc_mem()
            rx, tx = _proc_net()
            samples.append(MetricSample(time.time(), cpu, mem_used, mem_total, rx, tx))
        except Exception:
            pass
        await asyncio.sleep(METRICS_INTERVAL)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def upload_files(
    client: httpx.AsyncClient, session_id: str, files: list[Path]
) -> tuple[bool, str]:
    """Upload files in batches of 5 to /api/upload."""
    for i in range(0, len(files), 5):
        batch   = [f for f in files[i:i+5] if f.exists()]
        missing = [str(f) for f in files[i:i+5] if not f.exists()]
        if missing:
            return False, f"missing files: {missing}"
        if not batch:
            continue
        handles = []
        try:
            handles = [("files", (f.name, open(f, "rb"))) for f in batch]
            r = await client.post(
                f"{BASE_URL}/api/upload",
                headers={"X-Session-ID": session_id},
                files=handles,
                timeout=120,
            )
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}: {r.text[:200]}"
        finally:
            for _, (_, fh) in handles:
                fh.close()
    return True, ""


async def run_chat(
    client: httpx.AsyncClient, session_id: str, prompt: str, timeout_s: int
) -> tuple[bool, list, Optional[str], bool]:
    """POST /api/chat, stream SSE. Returns (success, out_files, error, tool_invoked)."""
    out_files:    list          = []
    error:        Optional[str] = None
    tool_invoked: bool          = False

    async with client.stream(
        "POST", f"{BASE_URL}/api/chat",
        headers={"X-Session-ID": session_id},
        data={"message": prompt, "model": MODEL},
        timeout=timeout_s,
    ) as resp:
        if resp.status_code != 200:
            return False, [], f"HTTP {resp.status_code}", False
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            try:
                evt = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            t = evt.get("type", "")
            if t == "tool_start":
                tool_invoked = True
            elif t == "tool_result":
                out_files = [f["filename"] for f in evt.get("files", [])]
                if evt.get("success") is False:
                    error = evt.get("message", "tool_result success=False")
                break
            elif t == "error" and "task_id" in evt:
                error = evt.get("message", "error")
                break

    success = tool_invoked and error is None
    return success, out_files, error, tool_invoked


# ── Single user session ───────────────────────────────────────────────────────

async def run_user(user_id: str, tools: list, delay: float = 0.0) -> UserResult:
    result = UserResult(user_id=user_id, start_delay_s=delay)
    if delay > 0:
        print(f"[{user_id}] ⏱  arriving in {delay:.1f}s ...")
        await asyncio.sleep(delay)

    t0_session = time.time()
    print(f"[{user_id}] ▶ started — tools: {[t[0] for t in tools]}")

    async with httpx.AsyncClient() as client:
        for label, files, prompt, timeout_s in tools:
            session_id = f"{user_id}-{label}-{int(time.time())}"
            t0 = time.time()

            # Upload
            ok, err = await upload_files(client, session_id, files)
            if not ok:
                dur = time.time() - t0
                result.tool_results.append(ToolResult(label, False, dur, error=f"upload: {err}"))
                print(f"[{user_id}] {label}: ✗ upload failed — {err}")
                continue

            # Chat (one auto-retry if LLM didn't invoke tool)
            retried = False
            for attempt in range(2):
                try:
                    success, out_files, error, invoked = await run_chat(
                        client, session_id, prompt, timeout_s
                    )
                except Exception as e:
                    success, out_files, error, invoked = False, [], str(e), False

                if success or invoked or attempt == 1:
                    break
                retried = True
                print(f"[{user_id}] {label}: ↩  LLM didn't invoke tool — retrying ...")
                await asyncio.sleep(2)

            dur = time.time() - t0
            icon  = "✓" if success else "✗"
            rtag  = " [retry]" if retried else ""
            extra = f"  → {error[:80]}" if error else f"  → {len(out_files)} output file(s)"
            print(f"[{user_id}] {label}: {icon}{rtag} ({dur:.1f}s){extra}")
            result.tool_results.append(
                ToolResult(label, success, dur, retried, out_files, error)
            )

    result.total_duration = time.time() - t0_session
    print(f"[{user_id}] ■ done  {result.n_pass}/{result.n_tools} PASS  ({result.total_duration:.1f}s total)")
    return result


# ── Reports ───────────────────────────────────────────────────────────────────

def print_phase_report(title: str, results: list[UserResult]) -> None:
    n_tools = sum(r.n_tools for r in results)
    n_pass  = sum(r.n_pass  for r in results)
    n_fail  = sum(r.n_fail  for r in results)
    n_retry = sum(1 for r in results for t in r.tool_results if t.retried)

    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print(f"  Users: {len(results)}   Tests: {n_tools}   "
          f"PASS: {n_pass}   FAIL: {n_fail}   Retried: {n_retry}")
    print()

    for ur in results:
        delay_s = f"  (+{ur.start_delay_s:.1f}s delay)" if ur.start_delay_s > 0 else ""
        print(f"  [{ur.user_id}]{delay_s}  "
              f"{ur.n_pass}/{ur.n_tools} PASS  ({ur.total_duration:.1f}s)")
        for t in ur.tool_results:
            icon  = "✓" if t.success else "✗"
            retry = " ↩" if t.retried else "  "
            err   = f"  → {t.error[:60]}" if t.error else ""
            print(f"    {icon}{retry} {t.label:<30} {t.duration:>8.1f}s{err}")
        print()

    pct     = int(100 * n_pass / n_tools) if n_tools else 0
    verdict = "ALL PASS ✓" if n_fail == 0 else f"{n_fail} FAIL ✗"
    print(f"  ── {verdict}  ({n_pass}/{n_tools} = {pct}%) ──")
    print("=" * 72)


def print_metrics(samples: list[MetricSample], wall_time: float) -> None:
    if not samples:
        print("  (no metrics samples collected)\n")
        return

    cpu_vals  = [s.cpu_pct     for s in samples]
    mem_vals  = [s.mem_used_mb for s in samples]
    mem_total = samples[0].mem_total_mb
    rx_delta  = samples[-1].net_rx_mb - samples[0].net_rx_mb
    tx_delta  = samples[-1].net_tx_mb - samples[0].net_tx_mb
    dur_min   = wall_time / 60

    print("\n" + "=" * 72)
    print("  RESOURCE USAGE  (Phase 2, eth0 network)")
    print("=" * 72)
    print(f"  Duration : {wall_time:.1f}s  |  Samples: {len(samples)} (every {METRICS_INTERVAL}s)")
    print(f"  CPU      : avg {sum(cpu_vals)/len(cpu_vals):.1f}%  "
          f"peak {max(cpu_vals):.1f}%  min {min(cpu_vals):.1f}%")
    print(f"  Memory   : avg {sum(mem_vals)/len(mem_vals):.0f} MB  "
          f"peak {max(mem_vals):.0f} MB  / {mem_total:.0f} MB total")
    print(f"  Network  : RX {rx_delta:.2f} MB  TX {tx_delta:.2f} MB  "
          f"({dur_min:.1f} min window)")
    print()
    print(f"  {'Rel.t':>6}  {'CPU%':>6}  {'MemMB':>8}  {'RX MB':>9}  {'TX MB':>9}")
    print(f"  {'-'*6}  {'-'*6}  {'-'*8}  {'-'*9}  {'-'*9}")
    t0 = samples[0].ts
    for s in samples:
        print(f"  {s.ts-t0:6.0f}s  {s.cpu_pct:6.1f}  {s.mem_used_mb:8.0f}  "
              f"{s.net_rx_mb:9.2f}  {s.net_tx_mb:9.2f}")
    print("=" * 72)


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(phases: list[int], n_users: int) -> int:
    print("\n" + "=" * 72)
    print("  AI_GCP_smoke_test — CSIS Platform Smoke / Load Check")
    print(f"  Target  : {BASE_URL}")
    print(f"  Model   : {MODEL}")
    print(f"  Tools   : {[t[0] for t in SMOKE_TOOLS]}")
    print(f"  Phases  : {phases}  |  Phase 2 users: {n_users}")
    print("=" * 72)

    p1_results: list[UserResult] = []
    p2_results: list[UserResult] = []

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    if 1 in phases:
        print("\n▶ PHASE 1 — Sequential baseline  (1 user, all 4 tools in order)\n")
        r1 = await run_user("u1-seq", SMOKE_TOOLS, delay=0.0)
        p1_results = [r1]
        print_phase_report("PHASE 1 — SEQUENTIAL BASELINE", p1_results)

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    if 2 in phases:
        print(f"\n▶ PHASE 2 — Concurrent  "
              f"({n_users} users, staggered 0–{ARRIVAL_WINDOW_S:.0f}s, shuffled order)\n")

        step    = ARRIVAL_WINDOW_S / max(n_users - 1, 1)
        delays  = sorted([
            i * step + random.uniform(-step * 0.3, step * 0.3)
            for i in range(n_users)
        ])
        delays[0] = max(0.0, delays[0])

        user_tool_lists = []
        for _ in range(n_users):
            shuffled = list(SMOKE_TOOLS)
            random.shuffle(shuffled)
            user_tool_lists.append(shuffled)

        metric_samples: list[MetricSample] = []
        stop_ev  = asyncio.Event()
        m_task   = asyncio.create_task(metrics_collector(metric_samples, stop_ev))

        wall_start = time.time()
        p2_results = list(await asyncio.gather(*[
            run_user(f"u{i+1}-conc", user_tool_lists[i], delays[i])
            for i in range(n_users)
        ]))
        wall_time = time.time() - wall_start

        stop_ev.set()
        await asyncio.sleep(0.1)
        m_task.cancel()

        print(f"\n  Phase 2 wall time: {wall_time:.1f}s")
        print_phase_report("PHASE 2 — CONCURRENT", p2_results)
        print_metrics(metric_samples, wall_time)

    # ── Overall exit code ─────────────────────────────────────────────────────
    all_results = p1_results + p2_results
    n_fail = sum(r.n_fail for r in all_results)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CSIS platform smoke / light load test"
    )
    parser.add_argument(
        "--phase", type=int, choices=[1, 2],
        help="Run only phase 1 (sequential) or phase 2 (concurrent). Default: both."
    )
    parser.add_argument(
        "--users", type=int, default=3,
        help="Number of concurrent users in Phase 2 (default: 3)."
    )
    args = parser.parse_args()
    phases = [args.phase] if args.phase else [1, 2]
    sys.exit(asyncio.run(main(phases, args.users)))
