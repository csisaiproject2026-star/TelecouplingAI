#!/usr/bin/env python3
"""
CSIS Platform GCP E2E Test  v2
Phase 1: 1 user, all 6 tools sequentially
Phase 2: 5 concurrent users — staggered start + randomised tool order

Realistic simulation:
  - Users arrive with random delay (0-8s window, like real people opening the site)
  - Each user runs tools in a random order (independent tools only — all 6 are independent)
  - Tool not invoked by agent → auto-retry once (handles LLM non-determinism)
  - Background goroutine samples CPU / RAM / network every 5 s during Phase 2
  - Full metrics summary appended to report
"""

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL  = "http://localhost"
DATA_ROOT = Path("/home/csisaiproject2026/csis-platform/datainput_for_demo")
MODEL     = "gemini-2.5-flash"

# Phase 2 settings
NUM_USERS        = 5
ARRIVAL_WINDOW_S = 8     # users spread over this window (seconds)
METRICS_INTERVAL = 5     # seconds between resource samples

# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    tool_name:    str
    success:      bool
    duration:     float
    retried:      bool = False
    output_files: list = field(default_factory=list)
    error:        Optional[str] = None


@dataclass
class UserSessionResult:
    user_id:        str
    tool_results:   list  = field(default_factory=list)
    total_duration: float = 0.0
    start_delay_s:  float = 0.0

    @property
    def passed(self):
        return sum(1 for r in self.tool_results if r.success)

    @property
    def failed(self):
        return sum(1 for r in self.tool_results if not r.success)


@dataclass
class MetricSample:
    ts:       float   # wall-clock time (seconds since epoch)
    cpu_pct:  float   # host-level CPU usage %
    mem_used_mb: float
    mem_total_mb: float
    net_rx_mb: float  # cumulative RX since boot
    net_tx_mb: float  # cumulative TX since boot


# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOL1_FILES = [
    DATA_ROOT / "NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv",
    DATA_ROOT / "NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv",
    DATA_ROOT / "NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shp",
    DATA_ROOT / "NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.dbf",
    DATA_ROOT / "NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shx",
]
TOOL1_PROMPT = (
    'Run Network Analysis Grouping with the uploaded files. '
    'nodes_join_attri="id", layer_join_attri="NAME", clustering_algorithm="walktrap"'
)

TOOL2_FILES = [
    DATA_ROOT / "CoastalBLueCarbonPreprocessor_input/snapshots.csv",
    DATA_ROOT / "CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv",
    DATA_ROOT / "CoastalBLueCarbonPreprocessor_input/GBJC_2010_mean_Resample.tif",
    DATA_ROOT / "CoastalBLueCarbonPreprocessor_input/GBJC_2030_mean_Resample.tif",
    DATA_ROOT / "CoastalBLueCarbonPreprocessor_input/GBJC_2050_mean_Resample.tif",
]
TOOL2_PROMPT = (
    'Run Coastal Blue Carbon Preprocessor with the uploaded snapshots.csv, '
    'lulc_lookup.csv, and the three LULC rasters (2010, 2030, 2050). '
    'Use empty results_suffix="".'
)

TOOL3_FILES = [
    DATA_ROOT / "CoastalBlueCarbon_input/snapshots.csv",
    DATA_ROOT / "CoastalBlueCarbon_input/outputs_preprocessor/transitions_sample.csv",
    DATA_ROOT / "CoastalBlueCarbon_input/outputs_preprocessor/biophysical_table_sample.csv",
    DATA_ROOT / "CoastalBlueCarbon_input/GBJC_2010_mean_Resample.tif",
    DATA_ROOT / "CoastalBlueCarbon_input/GBJC_2030_mean_Resample.tif",
    DATA_ROOT / "CoastalBlueCarbon_input/GBJC_2050_mean_Resample.tif",
]
TOOL3_PROMPT = (
    'Run Coastal Blue Carbon main model now. All required files have been uploaded: '
    'snapshots.csv (landcover snapshots), transitions_sample.csv (transitions table — '
    'already manually edited and ready to use, do NOT ask for confirmation), '
    'biophysical_table_sample.csv (biophysical table), and the three LULC rasters '
    'GBJC_2010_mean_Resample.tif, GBJC_2030_mean_Resample.tif, GBJC_2050_mean_Resample.tif. '
    'No economic analysis. results_suffix="". All parameters are complete — invoke the tool immediately.'
)

TOOL4_FILES = [
    DATA_ROOT / "SeasonalWaterYield_input/watershed_gura.shp",
    DATA_ROOT / "SeasonalWaterYield_input/watershed_gura.dbf",
    DATA_ROOT / "SeasonalWaterYield_input/watershed_gura.prj",
    DATA_ROOT / "SeasonalWaterYield_input/watershed_gura.shx",
    DATA_ROOT / "SeasonalWaterYield_input/land_use_gura.tif",
    DATA_ROOT / "SeasonalWaterYield_input/DEM_gura.tif",
    DATA_ROOT / "SeasonalWaterYield_input/soil_group_gura.tif",
    DATA_ROOT / "SeasonalWaterYield_input/biophysical_table_gura_SWY.csv",
    DATA_ROOT / "SeasonalWaterYield_input/rain_events_gura.csv",
]
TOOL4_PROMPT = (
    'Run Seasonal Water Yield now. All parameters are complete — invoke the tool immediately. '
    'Uploaded files: watershed_gura.shp (aoi_path), land_use_gura.tif (lulc_raster_path), '
    'DEM_gura.tif (dem_raster_path), soil_group_gura.tif (soil_group_path), '
    'biophysical_table_gura_SWY.csv (biophysical_table_path), '
    'rain_events_gura.csv (rain_events_table_path). '
    'Directory paths: precip_dir=/data/datainput/SeasonalWaterYield_input/Precipitation_monthly, '
    'et0_dir=/data/datainput/SeasonalWaterYield_input/ET0_monthly. '
    'threshold_flow_accumulation=1000, results_suffix="". Do not ask any questions, run immediately.'
)

TOOL5_FILES = [
    DATA_ROOT / "CropProductionPercentile_input/sample_user_data/landcover.tif",
    DATA_ROOT / "CropProductionPercentile_input/sample_user_data/landcover_to_crop_table.csv",
]
TOOL5_PROMPT = (
    'Run Crop Production Percentile with the uploaded landcover.tif and '
    'landcover_to_crop_table.csv. Use empty results_suffix="".'
)

TOOL6_FILES = [
    DATA_ROOT / "CropProductionRegression_input/sample_user_data/landcover.tif",
    DATA_ROOT / "CropProductionRegression_input/sample_user_data/landcover_to_crop_table.csv",
    DATA_ROOT / "CropProductionRegression_input/sample_user_data/crop_fertilization_rates.csv",
]
TOOL6_PROMPT = (
    'Run Crop Production Regression with the uploaded landcover.tif, '
    'landcover_to_crop_table.csv, and crop_fertilization_rates.csv. '
    'Use empty results_suffix="".'
)

# Base tool list — Phase 2 shuffles a copy per user
TOOLS_BASE = [
    ("Tool1_NetworkAnalysis",    TOOL1_FILES, TOOL1_PROMPT, 180),
    ("Tool2_CBCPreprocessor",    TOOL2_FILES, TOOL2_PROMPT, 360),
    ("Tool3_CBCMain",            TOOL3_FILES, TOOL3_PROMPT, 360),
    ("Tool4_SeasonalWaterYield", TOOL4_FILES, TOOL4_PROMPT, 600),
    ("Tool5_CropPercentile",     TOOL5_FILES, TOOL5_PROMPT, 360),
    ("Tool6_CropRegression",     TOOL6_FILES, TOOL6_PROMPT, 360),
]

# ─── System metrics (reads /proc — valid for host-level inside Docker) ────────

def _read_proc_stat() -> tuple[int, int]:
    """Return (idle_ticks, total_ticks) from /proc/stat cpu line."""
    with open("/proc/stat") as f:
        line = f.readline()
    parts = line.split()
    # user nice system idle iowait irq softirq ...
    values = [int(x) for x in parts[1:]]
    total = sum(values)
    idle  = values[3] + (values[4] if len(values) > 4 else 0)
    return idle, total


def _read_meminfo_mb() -> tuple[float, float]:
    """Return (used_mb, total_mb) from /proc/meminfo."""
    info: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k.strip()] = int(v.split()[0])   # kB
    total     = info.get("MemTotal",     0)
    available = info.get("MemAvailable", 0)
    used      = total - available
    return used / 1024, total / 1024   # → MB


def _read_net_mb(iface: str = "eth0") -> tuple[float, float]:
    """Return (rx_mb, tx_mb) cumulative from /proc/net/dev."""
    with open("/proc/net/dev") as f:
        for line in f:
            if iface in line:
                cols = line.split()
                rx = int(cols[1])
                tx = int(cols[9])
                return rx / 1024 / 1024, tx / 1024 / 1024
    return 0.0, 0.0


async def metrics_collector(
    samples: list,
    stop_event: asyncio.Event,
    interval: float = METRICS_INTERVAL,
):
    """Background coroutine: appends a MetricSample every `interval` seconds."""
    prev_idle, prev_total = _read_proc_stat()
    await asyncio.sleep(interval)

    while not stop_event.is_set():
        try:
            idle, total = _read_proc_stat()
            d_idle  = idle  - prev_idle
            d_total = total - prev_total
            cpu_pct = 100.0 * (1.0 - d_idle / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total

            mem_used, mem_total = _read_meminfo_mb()
            rx_mb, tx_mb = _read_net_mb()

            samples.append(MetricSample(
                ts=time.time(),
                cpu_pct=cpu_pct,
                mem_used_mb=mem_used,
                mem_total_mb=mem_total,
                net_rx_mb=rx_mb,
                net_tx_mb=tx_mb,
            ))
        except Exception:
            pass   # don't let metric errors break the test

        await asyncio.sleep(interval)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

async def upload_files(
    client: httpx.AsyncClient, session_id: str, files: list
) -> tuple[bool, str]:
    """Upload files in batches of 3."""
    batch_size = 3
    for i in range(0, len(files), batch_size):
        batch   = [Path(f) for f in files[i:i + batch_size] if Path(f).exists()]
        missing = [str(f) for f in files[i:i + batch_size] if not Path(f).exists()]
        if missing:
            return False, f"Missing files: {missing}"
        if not batch:
            continue
        file_handles = []
        try:
            file_handles = [("files", (f.name, open(f, "rb"))) for f in batch]
            resp = await client.post(
                f"{BASE_URL}/api/upload",
                headers={"X-Session-ID": session_id},
                files=file_handles,
                timeout=120,
            )
            if resp.status_code != 200:
                return False, f"Upload HTTP {resp.status_code}: {resp.text[:200]}"
        finally:
            for _, (_, fh) in file_handles:
                fh.close()
    return True, ""


async def run_tool_chat(
    client: httpx.AsyncClient, session_id: str, prompt: str, timeout: int
) -> tuple[bool, list, Optional[str], bool]:
    """
    Send chat, stream SSE.
    Returns (success, output_files, error, tool_was_invoked).
    """
    output_files:  list = []
    error:         Optional[str] = None
    tool_started:  bool = False

    async with client.stream(
        "POST",
        f"{BASE_URL}/api/chat",
        headers={"X-Session-ID": session_id},
        data={"message": prompt, "model": MODEL},
        timeout=timeout,
    ) as resp:
        if resp.status_code != 200:
            return False, [], f"HTTP {resp.status_code}", False

        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue

            etype = event.get("type", "")
            if etype == "tool_start":
                tool_started = True
            elif etype == "tool_result":
                output_files = [f["filename"] for f in event.get("files", [])]
            elif etype == "error" and "task_id" in event:
                error = event.get("message", "unknown error")

    success = bool(output_files) and not error
    return success, output_files, error, tool_started


# ─── Single user session ──────────────────────────────────────────────────────

async def run_user_session(
    user_id: str,
    tools: list,
    start_delay: float = 0.0,
) -> UserSessionResult:
    """Run one user session; tools list may be in any order."""
    result = UserSessionResult(user_id=user_id, start_delay_s=start_delay)

    if start_delay > 0:
        print(f"[{user_id}] ⏱  arriving in {start_delay:.1f}s ...")
        await asyncio.sleep(start_delay)

    session_start = time.time()
    print(f"[{user_id}] ▶ Session started  (tool order: {[t[0] for t in tools]})")

    async with httpx.AsyncClient() as client:
        for tool_name, files, prompt, timeout in tools:
            session_id = f"{user_id}-{tool_name}"
            t_start = time.time()

            # ── Upload ──────────────────────────────────────────────────────
            print(f"[{user_id}] {tool_name}: uploading {len(files)} files ...")
            ok, err = await upload_files(client, session_id, files)
            if not ok:
                result.tool_results.append(ToolResult(
                    tool_name=tool_name, success=False,
                    duration=time.time() - t_start,
                    error=f"Upload failed: {err}",
                ))
                print(f"[{user_id}] {tool_name}: ✗ upload — {err}")
                continue

            # ── Chat (with one auto-retry if agent didn't invoke tool) ──────
            print(f"[{user_id}] {tool_name}: running (timeout={timeout}s) ...")
            retried = False
            for attempt in range(2):   # attempt 0 = first try, attempt 1 = retry
                try:
                    success, out_files, error, tool_invoked = await run_tool_chat(
                        client, session_id, prompt, timeout
                    )
                except Exception as e:
                    success, out_files, error, tool_invoked = False, [], str(e), False

                if success:
                    break

                # Only retry when the agent asked for clarification (tool not run)
                # Don't retry hard compute errors — they'll fail again
                if not tool_invoked and attempt == 0:
                    retried = True
                    print(f"[{user_id}] {tool_name}: ↩  agent didn't invoke tool — retrying once ...")
                    await asyncio.sleep(2)   # brief pause before retry
                else:
                    break

            duration = time.time() - t_start
            result.tool_results.append(ToolResult(
                tool_name=tool_name, success=success,
                duration=duration, retried=retried,
                output_files=out_files, error=error,
            ))

            icon  = "✓" if success else "✗"
            retry = " [retried]" if retried else ""
            extra = f"  → {error[:100]}" if error else f"  → {len(out_files)} output files"
            print(f"[{user_id}] {tool_name}: {icon}{retry} ({duration:.1f}s){extra}")

    result.total_duration = time.time() - session_start
    print(f"[{user_id}] ■ done  {result.passed}/6 passed  ({result.total_duration:.1f}s)")
    return result


# ─── Reports ──────────────────────────────────────────────────────────────────

def print_report(phase_name: str, results: list):
    total_tests = sum(len(r.tool_results) for r in results)
    total_pass  = sum(r.passed  for r in results)
    total_fail  = sum(r.failed  for r in results)
    retried     = sum(1 for r in results
                      for tr in r.tool_results if getattr(tr, "retried", False))

    print("\n" + "=" * 76)
    print(f"  {phase_name}")
    print("=" * 76)
    print(f"  Users: {len(results)}   Tests: {total_tests}   "
          f"Passed: {total_pass}   Failed: {total_fail}   "
          f"Auto-retried: {retried}")
    print()

    for ur in results:
        delay_str = f"  (arrived +{ur.start_delay_s:.1f}s)" if ur.start_delay_s else ""
        print(f"  User: {ur.user_id:<14}  {ur.passed}/6 passed  "
              f"({ur.total_duration:.1f}s total){delay_str}")
        for tr in ur.tool_results:
            icon      = "✓" if tr.success else "✗"
            retry_str = " ↩" if getattr(tr, "retried", False) else "  "
            err_str   = f"  → {tr.error[:60]}" if tr.error else ""
            print(f"    {icon}{retry_str} {tr.tool_name:<30}  {tr.duration:>7.1f}s{err_str}")
        print()

    pct = int(100 * total_pass / total_tests) if total_tests else 0
    print(f"  ── Overall: {total_pass}/{total_tests} passed ({pct}%) ──")
    print("=" * 76 + "\n")


def print_metrics_report(samples: list, phase_wall_time: float):
    if not samples:
        print("  (no metrics samples collected)\n")
        return

    cpu_vals  = [s.cpu_pct     for s in samples]
    mem_vals  = [s.mem_used_mb for s in samples]
    mem_total = samples[0].mem_total_mb if samples else 1

    # Net deltas (first vs last sample for throughput)
    net_rx_delta = samples[-1].net_rx_mb - samples[0].net_rx_mb
    net_tx_delta = samples[-1].net_tx_mb - samples[0].net_tx_mb
    duration_min = phase_wall_time / 60

    print("=" * 76)
    print("  RESOURCE USAGE DURING PHASE 2")
    print("=" * 76)
    print(f"  Samples : {len(samples)}  (every {METRICS_INTERVAL}s)")
    print(f"  Duration: {phase_wall_time:.1f}s  ({duration_min:.1f} min)")
    print()
    print(f"  CPU Usage (host)")
    print(f"    avg : {sum(cpu_vals)/len(cpu_vals):5.1f} %")
    print(f"    peak: {max(cpu_vals):5.1f} %")
    print(f"    min : {min(cpu_vals):5.1f} %")
    print()
    print(f"  Memory (host)  — total: {mem_total:.0f} MB")
    print(f"    avg used : {sum(mem_vals)/len(mem_vals):7.1f} MB  "
          f"({100*sum(mem_vals)/len(mem_vals)/mem_total:.1f} %)")
    print(f"    peak used: {max(mem_vals):7.1f} MB  "
          f"({100*max(mem_vals)/mem_total:.1f} %)")
    print(f"    min used : {min(mem_vals):7.1f} MB  "
          f"({100*min(mem_vals)/mem_total:.1f} %)")
    print()
    print(f"  Network (eth0, during test window)")
    print(f"    RX : {net_rx_delta:7.2f} MB  ({net_rx_delta/duration_min:.2f} MB/min)")
    print(f"    TX : {net_tx_delta:7.2f} MB  ({net_tx_delta/duration_min:.2f} MB/min)")
    print()

    # Timeline (every sample, relative seconds from start)
    t0 = samples[0].ts
    print(f"  {'Time':>6}  {'CPU%':>6}  {'MemMB':>8}  {'Net RX MB':>10}  {'Net TX MB':>10}")
    print(f"  {'-'*6}  {'-'*6}  {'-'*8}  {'-'*10}  {'-'*10}")
    for s in samples:
        print(f"  {s.ts - t0:6.0f}s  {s.cpu_pct:6.1f}  "
              f"{s.mem_used_mb:8.0f}  {s.net_rx_mb:10.2f}  {s.net_tx_mb:10.2f}")
    print("=" * 76 + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 76)
    print("  CSIS Platform — GCP E2E Test  v2")
    print(f"  Target    : {BASE_URL}")
    print(f"  Model     : {MODEL}")
    print(f"  Arrival   : {NUM_USERS} users spread over {ARRIVAL_WINDOW_S}s window")
    print(f"  Tool order: randomised per user")
    print(f"  Retry     : yes (once, if agent didn't invoke tool)")
    print("=" * 76)

    # ── Phase 1: single user, fixed order ────────────────────────────────────
    print("\n▶ PHASE 1 — Single user, all 6 tools sequentially\n")
    p1_result = await run_user_session("phase1-u1", TOOLS_BASE, start_delay=0)
    print_report("PHASE 1 RESULTS — SINGLE USER", [p1_result])

    # ── Phase 2: 5 concurrent users, staggered + random tool order ───────────
    print("\n▶ PHASE 2 — 5 concurrent users  "
          f"(staggered 0-{ARRIVAL_WINDOW_S}s, randomised tool order)\n")

    # Assign unique random arrival delays (spread evenly ± some jitter)
    base_delays = [i * ARRIVAL_WINDOW_S / (NUM_USERS - 1) for i in range(NUM_USERS)]
    jitter      = ARRIVAL_WINDOW_S / (NUM_USERS - 1) * 0.3
    delays      = sorted([d + random.uniform(-jitter, jitter) for d in base_delays])
    delays[0]   = max(0.0, delays[0])  # first user always ≥ 0

    # Shuffle tools independently for each user
    user_tool_lists = []
    for i in range(NUM_USERS):
        shuffled = list(TOOLS_BASE)
        random.shuffle(shuffled)
        user_tool_lists.append(shuffled)

    # Start metrics collector
    metric_samples: list[MetricSample] = []
    stop_metrics   = asyncio.Event()
    metrics_task   = asyncio.create_task(
        metrics_collector(metric_samples, stop_metrics)
    )

    wall_start = time.time()

    tasks = [
        run_user_session(f"phase2-u{i+1}", user_tool_lists[i], delays[i])
        for i in range(NUM_USERS)
    ]
    p2_results = list(await asyncio.gather(*tasks))

    wall_time = time.time() - wall_start

    # Stop metrics
    stop_metrics.set()
    await asyncio.sleep(0.1)
    metrics_task.cancel()

    print(f"\n  Phase 2 wall time: {wall_time:.1f}s")
    print_report("PHASE 2 RESULTS — 5 CONCURRENT USERS", p2_results)
    print_metrics_report(metric_samples, wall_time)


if __name__ == "__main__":
    asyncio.run(main())
