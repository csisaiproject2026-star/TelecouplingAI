#!/usr/bin/env python3
"""
CSIS Platform — Stress Test  (50 concurrent users)

Design:
  - 50 users arrive over a 90-second window (random Poisson-like spacing)
  - Each user runs 2 randomly chosen tools (independent, without replacement)
  - Auto-retry once if agent asks for clarification instead of invoking tool
  - Background metrics sampler: CPU / RAM / Network every 5 s
  - Final report: per-tool stats, p50/p95/p99 latency, resource summary

Why 2 tools per user (not 6):
  - 6 × 50 = 300 invocations behind 4 Celery workers ≈ 2+ hours
  - 2 × 50 = 100 invocations ≈ 30-40 min — realistic session depth
"""

import asyncio
import json
import os
import random
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

# ─── Config ──────────────────────────────────────────────────────────────────

BASE_URL        = "http://localhost"
DATA_ROOT       = Path("/home/csisaiproject2026/csis-platform/datainput_for_demo")
MODEL           = "gemini-2.5-flash"
NUM_USERS       = 50
TOOLS_PER_USER  = 2        # each user runs 2 randomly chosen tools
ARRIVAL_WINDOW  = 90       # seconds — all 50 users arrive within this window
METRICS_INTERVAL = 5       # seconds between resource samples

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

ALL_TOOLS = [
    ("Tool1_NetworkAnalysis",    TOOL1_FILES, TOOL1_PROMPT, 180),
    ("Tool2_CBCPreprocessor",    TOOL2_FILES, TOOL2_PROMPT, 360),
    ("Tool3_CBCMain",            TOOL3_FILES, TOOL3_PROMPT, 420),
    ("Tool4_SeasonalWaterYield", TOOL4_FILES, TOOL4_PROMPT, 720),
    ("Tool5_CropPercentile",     TOOL5_FILES, TOOL5_PROMPT, 360),
    ("Tool6_CropRegression",     TOOL6_FILES, TOOL6_PROMPT, 360),
]

# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class ToolRun:
    user_id:      str
    tool_name:    str
    success:      bool
    duration:     float
    retried:      bool = False
    error:        Optional[str] = None
    queue_wait:   float = 0.0   # time from upload-done to first SSE event


@dataclass
class MetricSample:
    ts:           float
    cpu_pct:      float
    mem_used_mb:  float
    mem_total_mb: float
    net_rx_mb:    float
    net_tx_mb:    float

# ─── Metric helpers ───────────────────────────────────────────────────────────

def _proc_stat():
    with open("/proc/stat") as f:
        line = f.readline()
    vals = [int(x) for x in line.split()[1:]]
    idle  = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def _meminfo_mb():
    info: dict[str, int] = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k.strip()] = int(v.split()[0])
    total     = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    return (total - available) / 1024, total / 1024


def _net_mb(iface: str = "eth0"):
    with open("/proc/net/dev") as f:
        for line in f:
            if iface in line:
                cols = line.split()
                return int(cols[1]) / 1048576, int(cols[9]) / 1048576
    return 0.0, 0.0


async def metrics_collector(samples: list, stop: asyncio.Event, interval=METRICS_INTERVAL):
    prev_idle, prev_total = _proc_stat()
    await asyncio.sleep(interval)
    while not stop.is_set():
        try:
            idle, total = _proc_stat()
            d_idle  = idle  - prev_idle
            d_total = total - prev_total
            cpu_pct = 100.0 * (1 - d_idle / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total
            mu, mt   = _meminfo_mb()
            rx, tx   = _net_mb()
            samples.append(MetricSample(time.time(), cpu_pct, mu, mt, rx, tx))
        except Exception:
            pass
        await asyncio.sleep(interval)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

async def upload_files(client, session_id, files):
    for i in range(0, len(files), 3):
        batch   = [Path(f) for f in files[i:i+3] if Path(f).exists()]
        missing = [str(f) for f in files[i:i+3] if not Path(f).exists()]
        if missing:
            return False, f"Missing: {missing}"
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
                return False, f"HTTP {r.status_code}"
        finally:
            for _, (_, fh) in handles:
                fh.close()
    return True, ""


async def run_chat(client, session_id, prompt, timeout):
    """Returns (success, error, tool_invoked, first_event_delay)."""
    output_files = []
    tool_invoked = False
    error        = None
    t_first      = None

    t_send = time.time()
    async with client.stream(
        "POST",
        f"{BASE_URL}/api/chat",
        headers={"X-Session-ID": session_id},
        data={"message": prompt, "model": MODEL},
        timeout=timeout,
    ) as resp:
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}", False, 0.0

        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if t_first is None:
                t_first = time.time() - t_send
            etype = ev.get("type", "")
            if etype == "tool_start":
                tool_invoked = True
            elif etype == "tool_result":
                output_files = [f["filename"] for f in ev.get("files", [])]
            elif etype == "error" and "task_id" in ev:
                error = ev.get("message", "unknown error")

    success = bool(output_files) and not error
    return success, error, tool_invoked, t_first or 0.0


# ─── Single user ──────────────────────────────────────────────────────────────

async def run_user(user_id: str, tool_list: list, delay: float, all_runs: list):
    if delay > 0:
        await asyncio.sleep(delay)

    async with httpx.AsyncClient() as client:
        for tool_name, files, prompt, timeout in tool_list:
            session_id = f"{user_id}-{tool_name}"
            t_start = time.time()

            ok, err = await upload_files(client, session_id, files)
            if not ok:
                all_runs.append(ToolRun(user_id, tool_name, False,
                                        time.time() - t_start, error=f"upload: {err}"))
                continue

            t_upload_done = time.time()
            retried = False

            for attempt in range(2):
                try:
                    success, error, invoked, first_delay = await run_chat(
                        client, session_id, prompt, timeout
                    )
                except Exception as e:
                    success, error, invoked, first_delay = False, str(e), False, 0.0

                if success:
                    break
                if not invoked and attempt == 0:
                    retried = True
                    await asyncio.sleep(2)
                else:
                    break

            duration   = time.time() - t_start
            queue_wait = first_delay
            run = ToolRun(user_id, tool_name, success, duration,
                          retried=retried, error=error, queue_wait=queue_wait)
            all_runs.append(run)

            icon = "✓" if success else "✗"
            rstag = " ↩" if retried else ""
            extra = f"  → {error[:80]}" if error else ""
            print(f"  [{user_id}] {icon}{rstag} {tool_name}  {duration:.1f}s{extra}")


# ─── Stats helpers ────────────────────────────────────────────────────────────

def percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)


def print_stress_report(all_runs: list, wall_time: float):
    total = len(all_runs)
    passed = sum(1 for r in all_runs if r.success)
    failed = total - passed
    retried = sum(1 for r in all_runs if r.retried)
    durations = [r.duration for r in all_runs if r.success]

    print("\n" + "=" * 76)
    print("  STRESS TEST RESULTS — 50 CONCURRENT USERS")
    print("=" * 76)
    print(f"  Users          : {NUM_USERS}")
    print(f"  Tools per user : {TOOLS_PER_USER}  (randomly selected)")
    print(f"  Total runs     : {total}")
    print(f"  Passed         : {passed}  ({100*passed//total if total else 0}%)")
    print(f"  Failed         : {failed}")
    print(f"  Auto-retried   : {retried}")
    print(f"  Wall time      : {wall_time:.1f}s  ({wall_time/60:.1f} min)")
    if durations:
        throughput = passed / (wall_time / 60)
        print(f"  Throughput     : {throughput:.2f} successful tool runs / min")
    print()

    # Latency stats (successful runs only)
    if durations:
        print(f"  Response time (end-to-end, successful runs only)")
        print(f"    p50 : {percentile(durations, 50):7.1f}s")
        print(f"    p75 : {percentile(durations, 75):7.1f}s")
        print(f"    p95 : {percentile(durations, 95):7.1f}s")
        print(f"    p99 : {percentile(durations, 99):7.1f}s")
        print(f"    min : {min(durations):7.1f}s")
        print(f"    max : {max(durations):7.1f}s")
        print(f"    avg : {statistics.mean(durations):7.1f}s")
        print()

    # Per-tool breakdown
    tools_seen = list(dict.fromkeys(r.tool_name for r in all_runs))
    print(f"  {'Tool':<32}  {'Runs':>4}  {'Pass':>4}  {'Fail':>4}  "
          f"{'AvgS':>6}  {'P95S':>6}")
    print(f"  {'-'*32}  {'-'*4}  {'-'*4}  {'-'*4}  {'-'*6}  {'-'*6}")
    for tn in tools_seen:
        subset = [r for r in all_runs if r.tool_name == tn]
        ok_dur = [r.duration for r in subset if r.success]
        n_pass = sum(1 for r in subset if r.success)
        n_fail = len(subset) - n_pass
        avg_s  = statistics.mean(ok_dur) if ok_dur else 0
        p95_s  = percentile(ok_dur, 95)  if ok_dur else 0
        print(f"  {tn:<32}  {len(subset):>4}  {n_pass:>4}  {n_fail:>4}  "
              f"{avg_s:>6.1f}  {p95_s:>6.1f}")
    print()

    # Failures summary
    errors = [(r.user_id, r.tool_name, r.error) for r in all_runs if not r.success]
    if errors:
        print(f"  Failure details ({len(errors)} total):")
        shown = set()
        for uid, tn, err in errors:
            key = (tn, (err or "")[:60])
            if key not in shown:
                print(f"    {tn:<32}  {(err or 'no error')[:70]}")
                shown.add(key)
    print("=" * 76 + "\n")


def print_metrics_report(samples: list, wall_time: float, phase: str):
    if not samples:
        print(f"  [{phase}] No metrics samples.\n")
        return

    cpu_vals  = [s.cpu_pct     for s in samples]
    mem_vals  = [s.mem_used_mb for s in samples]
    mem_total = samples[0].mem_total_mb

    rx0, tx0 = samples[0].net_rx_mb,  samples[0].net_tx_mb
    rx1, tx1 = samples[-1].net_rx_mb, samples[-1].net_tx_mb
    dur_min  = wall_time / 60

    print("=" * 76)
    print(f"  RESOURCE METRICS — {phase}")
    print("=" * 76)
    print(f"  Samples : {len(samples)}  every {METRICS_INTERVAL}s")
    print(f"  Window  : {wall_time:.0f}s")
    print()
    print(f"  CPU (host)")
    print(f"    avg  {statistics.mean(cpu_vals):5.1f}%   peak {max(cpu_vals):5.1f}%   "
          f"min {min(cpu_vals):5.1f}%")
    print()
    print(f"  Memory (host)  total={mem_total:.0f} MB")
    print(f"    avg  {statistics.mean(mem_vals):7.0f} MB  "
          f"({100*statistics.mean(mem_vals)/mem_total:.1f}%)")
    print(f"    peak {max(mem_vals):7.0f} MB  ({100*max(mem_vals)/mem_total:.1f}%)")
    print(f"    min  {min(mem_vals):7.0f} MB  ({100*min(mem_vals)/mem_total:.1f}%)")
    print()
    print(f"  Network (eth0)")
    print(f"    RX  {rx1-rx0:7.2f} MB total  ({(rx1-rx0)/dur_min:.2f} MB/min)")
    print(f"    TX  {tx1-tx0:7.2f} MB total  ({(tx1-tx0)/dur_min:.2f} MB/min)")
    print()
    t0 = samples[0].ts
    print(f"  {'Time':>5}  {'CPU%':>6}  {'MemMB':>7}  {'NetRX':>8}  {'NetTX':>8}")
    print(f"  {'-'*5}  {'-'*6}  {'-'*7}  {'-'*8}  {'-'*8}")
    for s in samples:
        print(f"  {s.ts-t0:5.0f}s  {s.cpu_pct:6.1f}  "
              f"{s.mem_used_mb:7.0f}  {s.net_rx_mb:8.2f}  {s.net_tx_mb:8.2f}")
    print("=" * 76 + "\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "=" * 76)
    print("  CSIS Platform — Stress Test  (50 Users)")
    print(f"  Target         : {BASE_URL}")
    print(f"  Model          : {MODEL}")
    print(f"  Users          : {NUM_USERS}")
    print(f"  Tools/user     : {TOOLS_PER_USER}  (random, without replacement)")
    print(f"  Arrival window : {ARRIVAL_WINDOW}s")
    print(f"  Retry          : yes (once, if agent didn't invoke tool)")
    print("=" * 76 + "\n")

    # Assign random arrival times within the window
    arrivals = sorted([random.uniform(0, ARRIVAL_WINDOW) for _ in range(NUM_USERS)])
    arrivals[0] = 0.0  # at least one user starts immediately

    # Assign tool subset per user (2 tools, no replacement, random order)
    user_tools = []
    for i in range(NUM_USERS):
        chosen = random.sample(ALL_TOOLS, TOOLS_PER_USER)
        random.shuffle(chosen)
        user_tools.append(chosen)

    print("  Tool assignment preview (first 5 users):")
    for i in range(min(5, NUM_USERS)):
        print(f"    user{i+1}  +{arrivals[i]:.1f}s  "
              f"{[t[0] for t in user_tools[i]]}")
    print(f"    ... ({NUM_USERS} users total)\n")

    # Start metrics
    all_runs:      list = []
    metric_samples: list = []
    stop_metrics   = asyncio.Event()
    metrics_task   = asyncio.create_task(
        metrics_collector(metric_samples, stop_metrics)
    )

    wall_start = time.time()
    print("▶ Starting stress test ...\n")

    tasks = [
        run_user(f"u{i+1:02d}", user_tools[i], arrivals[i], all_runs)
        for i in range(NUM_USERS)
    ]
    await asyncio.gather(*tasks)

    wall_time = time.time() - wall_start
    stop_metrics.set()
    await asyncio.sleep(0.2)
    metrics_task.cancel()

    print(f"\n■ Stress test complete  wall={wall_time:.1f}s\n")
    print_stress_report(all_runs, wall_time)
    print_metrics_report(metric_samples, wall_time, "STRESS TEST — 50 USERS")


if __name__ == "__main__":
    asyncio.run(main())
