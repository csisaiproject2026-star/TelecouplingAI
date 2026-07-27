"""
03_smoke_stress_test / test_stress_50.py
Stress test: 50 concurrent users, 2 tools each.

Design:
  - 50 users arrive randomly over a 90-second window
  - Each user runs 2 randomly chosen tools (no replacement)
  - Auto-retry once if agent asks for clarification instead of running tool
  - Background metrics: CPU / RAM / Network every 5s
  - Final report: per-tool latency stats (p50/p75/p95/p99), failure breakdown

Merged and updated from GCP_test/test_stress_50.py.

Run:
    cd Systematic_tests/AI_GCP_test
    CSIS_BASE_URL=http://localhost python 03_smoke_stress_test/test_stress_50.py
    CSIS_BASE_URL=http://localhost python 03_smoke_stress_test/test_stress_50.py --users 10
"""
import asyncio
import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _utils import (
    BASE_URL, DEMO, SD, DEFAULT_MODEL,
    MetricSample, metrics_collector, print_metrics, percentile,
)

REPORT_PATH      = os.path.join(os.path.dirname(__file__), "results_stress.json")
NUM_USERS        = 50
TOOLS_PER_USER   = 2
ARRIVAL_WINDOW   = 90
METRICS_INTERVAL = 5

DD  = DEMO
SAM = SD

OLS_CSV  = (b"id,gdp,pop,forest,co2\n"
            b"1,14000,1400,22.3,10000\n2,21000,330,33.8,5000\n"
            b"3,4000,83,31.7,700\n4,3000,67,29.2,400\n5,5000,126,68.5,1200\n"
            b"6,2000,45,15.2,300\n7,1500,33,12.8,200\n8,800,20,45.6,100\n"
            b"9,600,18,62.1,80\n10,400,10,78.3,50\n")
CO2_CSV  = (b"route_id,animal_count,length_km\n"
            b"route_001,50,120.5\nroute_002,30,85.2\nroute_003,75,200.0\n"
            b"route_004,20,45.8\nroute_005,60,310.7\n")
CBA_MAIN_CSV = (b"region_id,region_name,area_km2\n"
                b"R01,Yangtze Delta,45000\nR02,Tibetan Plateau,2000000\n"
                b"R03,Pearl River Delta,55000\nR04,Northeast Plain,350000\n")
CBA_ECON_CSV = (b"region_id,COSTS,REVENUES\n"
                b"R01,250000,480000\nR02,80000,150000\n"
                b"R03,600000,950000\nR04,320000,520000\n")
FOOD_CSV = (b"Area,Year,Item,Value\n"
            b"China,2019,Undernourishment,2.5\nIndia,2019,Undernourishment,14.0\n"
            b"Nigeria,2019,Undernourishment,14.8\nBrazil,2019,Undernourishment,6.5\n"
            b"China,2020,Undernourishment,2.5\nIndia,2020,Undernourishment,15.3\n"
            b"Nigeria,2020,Undernourishment,18.0\nBrazil,2020,Undernourishment,7.0\n")


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ToolRun:
    user_id:    str
    tool_name:  str
    success:    bool
    duration:   float
    retried:    bool  = False
    error:      Optional[str] = None
    first_event_delay: float = 0.0
    first_work_delay: float = 0.0
    capacity_queued: bool = False
    queue_position: int = 0


# ── Tool pool (all tools that have data on GCP) ───────────────────────────────
# (name, inline_files [(fname, bytes, mime)], prompt, timeout_s)

ALL_TOOLS = [
    ("T01_NetworkAnalysis",
     [],
     (f"Call run_network_analysis with: "
      f"nodes_table={DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv, "
      f"links_table={DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv, "
      f"shapefile_path={DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/World_countries_2002.shp, "
      f"nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap. Run immediately."),
     270),

    ("T02_CBCPreprocessor",
     [],
     (f"Call run_coastal_blue_carbon_preprocessor with: "
      f"landcover_snapshot_csv={DD}/CoastalBLueCarbonPreprocessor_input/snapshots.csv, "
      f"landcover_lookup_table={DD}/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv, "
      f"lulc_snapshot_list=[{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2010_mean_Resample.tif,"
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2030_mean_Resample.tif,"
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2050_mean_Resample.tif]. Run immediately."),
     270),

    ("T07_Carbon",
     [],
     (f"Call run_carbon_storage with: "
      f"lulc_cur_path={SAM}/Carbon/lulc_current_willamette.tif, "
      f"carbon_pools_path={SAM}/Carbon/carbon_pools_willamette.csv. Run immediately."),
     180),

    ("T08_HabitatQuality",
     [],
     (f"Call run_habitat_quality with: "
      f"lulc_cur_path={SAM}/HabitatQuality/lulc_current_willamette.tif, "
      f"access_vector_path={SAM}/HabitatQuality/accessibility_willamette.shp, "
      f"sensitivity_table_path={SAM}/HabitatQuality/sensitivity_willamette.csv, "
      f"threats_table_path={SAM}/HabitatQuality/threats_willamette.csv, "
      f"half_saturation_constant=0.05. Run immediately."),
     300),

    ("T09_AWY",
     [],
     (f"Call run_annual_water_yield with: "
      f"lulc_path={SAM}/Annual_Water_Yield/land_use_gura.tif, "
      f"eto_path={SAM}/Annual_Water_Yield/reference_ET_gura.tif, "
      f"precipitation_path={SAM}/Annual_Water_Yield/precipitation_gura.tif, "
      f"depth_to_root_rest_layer_path={SAM}/Annual_Water_Yield/depth_to_root_restricting_layer_gura.tif, "
      f"pawc_path={SAM}/Annual_Water_Yield/plant_available_water_fraction_gura.tif, "
      f"biophysical_table_path={SAM}/Annual_Water_Yield/biophysical_table_gura.csv, "
      f"watersheds_path={SAM}/Annual_Water_Yield/watershed_gura.shp, "
      f"sub_watersheds_path={SAM}/Annual_Water_Yield/subwatersheds_gura.shp, "
      f"seasonality_constant=15. Run immediately."),
     300),

    ("T10_Pollination",
     [],
     (f"Call run_crop_pollination with: "
      f"landcover_raster_path={SAM}/pollination/landcover.tif, "
      f"landcover_biophysical_table_path={SAM}/pollination/landcover_biophysical_table.csv, "
      f"guild_table_path={SAM}/pollination/guild_table.csv, "
      f"farm_vector_path={SAM}/pollination/farms.shp. Run immediately."),
     300),

    ("T28_OLS",
     [("ols.csv", OLS_CSV, "text/csv")],
     ("Call run_ols with uploaded ols.csv: "
      "dependent_variable=co2, independent_variables=gdp,pop,forest. Run immediately."),
     120),

    ("T30_CO2",
     [("co2_transport.csv", CO2_CSV, "text/csv")],
     ("Call run_co2_emissions with uploaded co2_transport.csv. "
      "capacity_per_trip=10, co2_per_km_per_trip=0.8, "
      "animal_count_field=animal_count, length_km_field=length_km. Run immediately."),
     120),

    ("T31_CBA",
     [("cba_main.csv", CBA_MAIN_CSV, "text/csv"),
      ("cba_econ.csv", CBA_ECON_CSV, "text/csv")],
     ("Call run_cost_benefit_analysis with uploaded cba_main.csv and cba_econ.csv. "
      "key_field=region_id. Run immediately."),
     120),

    ("T41_FoodSecurity",
     [("food_fao.csv", FOOD_CSV, "text/csv")],
     ("Call run_food_security with uploaded food_fao.csv. "
      "countries=China,India,Nigeria,Brazil, "
      "indicator_field=Undernourishment, country_field=Area, year_field=Year, "
      "value_field=Value. Run immediately."),
     120),

    ("T07b_Carbon",
     [],
     (f"Call run_carbon_storage with: "
      f"lulc_cur_path={SAM}/Carbon/lulc_current_willamette.tif, "
      f"carbon_pools_path={SAM}/Carbon/carbon_pools_willamette.csv. Run immediately."),
     180),

    ("T15_UrbanCooling",
     [],
     (f"Call run_urban_cooling with: "
      f"lulc_raster_path=/data/datainput/16_urban_cooling/lulc.tif, "
      f"ref_eto_raster_path=/data/datainput/16_urban_cooling/et0.tif, "
      f"aoi_vector_path=/data/datainput/16_urban_cooling/aoi.shp, "
      f"biophysical_table_path=/data/datainput/16_urban_cooling/Biophysical_UHI_fake.csv, "
      f"green_area_cooling_distance=1000, t_ref=21.5, uhi_max=3.5, "
      f"cc_method=factors, avg_rel_humidity=30, t_air_average_radius=2000. Run immediately."),
     600),

    ("T23_ScenarioGen",
     [],
     (f"Call run_scenario_gen_proximity with: "
      f"base_lulc_path=/data/datainput/27_scenario_gen_proximity/scenario_proximity_lulc.tif, "
      f"aoi_path=/data/datainput/27_scenario_gen_proximity/scenario_proximity_aoi.shp, "
      f"replacement_lucode=12, area_to_convert=20000, "
      f"focal_landcover_codes='1 2 3 4 5', convertible_landcover_codes='1 2 3 4 5', "
      f"convert_nearest_to_edge=True, convert_farthest_from_edge=True. Run immediately."),
     360),

    ("T27_ForestCarbon",
     [],
     (f"Call run_forest_carbon_edge with: "
      f"lulc_raster_path=/data/datainput/10_forest_carbon_edge_effect/forest_carbon_edge_lulc_demo.tif, "
      f"biophysical_table_path=/data/datainput/10_forest_carbon_edge_effect/forest_edge_carbon_lu_table.csv, "
      f"tropical_forest_edge_carbon_model_vector_path=/data/datainput/10_forest_carbon_edge_effect/core_data/forest_carbon_edge_regression_model_parameters.shp, "
      f"aoi_vector_path=/data/datainput/10_forest_carbon_edge_effect/forest_carbon_edge_demo_aoi.shp, "
      f"compute_forest_edge_effects=True, n_nearest_model_points=10. Run immediately."),
     600),
]


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def upload_inline(client: httpx.AsyncClient, sid: str, files: list) -> tuple:
    if not files:
        return True, ""
    try:
        r = await client.post(
            f"{BASE_URL}/api/upload",
            headers={"X-Session-ID": sid},
            files=[("files", (fname, data, mime)) for fname, data, mime in files],
            timeout=60,
        )
        return (True, "") if r.status_code == 200 else (False, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


async def run_chat(client: httpx.AsyncClient, sid: str, prompt: str,
                   timeout: int) -> tuple:
    """Return success plus SSE and capacity-wait observations."""
    output_files = []
    tool_invoked = False
    error = None
    t_first = None
    t_first_work = None
    capacity_queued = False
    queue_position = 0
    done_received = False
    t_send = time.time()

    async def consume_stream():
        nonlocal error, t_first, t_first_work
        nonlocal capacity_queued, queue_position, tool_invoked, output_files
        nonlocal done_received
        async with client.stream(
            "POST", f"{BASE_URL}/api/chat",
            headers={"X-Session-ID": sid},
            data={"message": prompt, "model": DEFAULT_MODEL},
            timeout=httpx.Timeout(connect=30, read=None, write=60, pool=30),
        ) as resp:
            if resp.status_code != 200:
                error = f"HTTP {resp.status_code}"
                return
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
                if etype in {"thinking", "text_chunk", "tool_start"} and t_first_work is None:
                    t_first_work = time.time() - t_send
                if etype == "capacity_wait":
                    capacity_queued = True
                    queue_position = max(queue_position, int(ev.get("queue_position") or 0))
                elif etype == "tool_start":
                    tool_invoked = True
                elif etype == "tool_result":
                    output_files = [f["filename"] for f in ev.get("files", [])]
                elif etype == "error":
                    error = ev.get("message", "unknown")
                elif etype == "done":
                    done_received = True

    try:
        await asyncio.wait_for(consume_stream(), timeout=timeout)
    except asyncio.TimeoutError:
        error = f"absolute timeout after {timeout}s"
    except httpx.HTTPError as exc:
        error = str(exc)

    if not done_received and not error:
        error = "stream ended before terminal done event"
    success = bool(output_files) and done_received and not error
    retryable_no_tool = done_received and not tool_invoked and not error
    return (
        success,
        error,
        tool_invoked,
        t_first or 0.0,
        t_first_work or 0.0,
        capacity_queued,
        queue_position,
        retryable_no_tool,
    )


# ── Single user ───────────────────────────────────────────────────────────────

async def run_user(user_id: str, tool_list: list, delay: float, all_runs: list):
    if delay > 0:
        await asyncio.sleep(delay)

    async with httpx.AsyncClient() as client:
        sid = user_id
        for tool_name, files, prompt, timeout in tool_list:
            t0 = time.time()

            ok, err = await upload_inline(client, sid, files)
            if not ok:
                all_runs.append(ToolRun(user_id, tool_name, False,
                                        time.time()-t0, error=f"upload: {err}"))
                continue

            retried = False
            for attempt in range(2):
                try:
                    (
                        success,
                        error,
                        invoked,
                        first_delay,
                        first_work_delay,
                        capacity_queued,
                        queue_position,
                        retryable_no_tool,
                    ) = await run_chat(
                        client, sid, prompt, timeout)
                except Exception as e:
                    success, error, invoked = False, str(e), False
                    first_delay, first_work_delay = 0.0, 0.0
                    capacity_queued, queue_position = False, 0
                    retryable_no_tool = False
                if success:
                    break
                if retryable_no_tool and attempt == 0:
                    retried = True
                    await asyncio.sleep(2)
                else:
                    break

            duration = time.time() - t0
            all_runs.append(ToolRun(user_id, tool_name, success, duration,
                                    retried=retried, error=error,
                                    first_event_delay=first_delay,
                                    first_work_delay=first_work_delay,
                                    capacity_queued=capacity_queued,
                                    queue_position=queue_position))
            icon = "✓" if success else "✗"
            rs = " ↩" if retried else ""
            extra = f"  → {error[:70]}" if error else ""
            print(f"  [{user_id}] {icon}{rs} {tool_name}  {duration:.1f}s{extra}")


# ── Stats and report ──────────────────────────────────────────────────────────

def print_stress_report(
    all_runs: list,
    wall_time: float,
    capacity_before: dict | None = None,
    capacity_after: dict | None = None,
    retention_probe: dict | None = None,
    run_id: str = "",
):
    total  = len(all_runs)
    passed = sum(1 for r in all_runs if r.success)
    failed = total - passed
    retried = sum(1 for r in all_runs if r.retried)
    durations = [r.duration for r in all_runs if r.success]
    first_events = [r.first_event_delay for r in all_runs if r.first_event_delay > 0]
    first_work = [r.first_work_delay for r in all_runs if r.first_work_delay > 0]
    capacity_queued = [r for r in all_runs if r.capacity_queued]
    retention_ok = bool(
        retention_probe
        and retention_probe.get("requested") == NUM_USERS
        and retention_probe.get("retained") == NUM_USERS
        and not retention_probe.get("missing")
    )

    print(f"\n{'=' * 78}")
    print(f"  STRESS TEST RESULTS")
    print(f"{'=' * 78}")
    print(f"  Users          : {NUM_USERS}")
    print(f"  Tools/user     : {TOOLS_PER_USER}  (random sample)")
    print(f"  Total runs     : {total}")
    print(f"  Passed         : {passed}  ({100*passed//total if total else 0}%)")
    print(f"  Failed         : {failed}")
    print(f"  Auto-retried   : {retried}")
    print(f"  Wall time      : {wall_time:.1f}s  ({wall_time/60:.1f} min)")
    if durations:
        tp = passed / (wall_time / 60)
        print(f"  Throughput     : {tp:.2f} successful runs/min")
    print()

    if first_events:
        print(
            f"  First SSE event: p50 {percentile(first_events,50):.1f}s  "
            f"p95 {percentile(first_events,95):.1f}s"
        )
    if first_work:
        print(
            f"  First model/tool activity: p50 {percentile(first_work,50):.1f}s  "
            f"p95 {percentile(first_work,95):.1f}s"
        )
    print(f"  Capacity queued: {len(capacity_queued)}/{total}")
    if capacity_before or capacity_after:
        print(f"  Capacity before: {capacity_before or 'unavailable'}")
        print(f"  Capacity after : {capacity_after or 'unavailable'}")
        print(f"  Session retention: {'PASS' if retention_ok else 'FAIL'} "
              f"({retention_probe or 'probe unavailable'})")
    print()

    if durations:
        print(f"  Latency (successful runs)")
        print(f"    p50 {percentile(durations,50):6.1f}s  p75 {percentile(durations,75):6.1f}s  "
              f"p95 {percentile(durations,95):6.1f}s  p99 {percentile(durations,99):6.1f}s")
        print(f"    min {min(durations):6.1f}s  avg {statistics.mean(durations):6.1f}s  "
              f"max {max(durations):6.1f}s")
        print()

    tools_seen = list(dict.fromkeys(r.tool_name for r in all_runs))
    print(f"  {'Tool':<34}  {'Runs':>4}  {'Pass':>4}  {'Fail':>4}  "
          f"{'AvgS':>6}  {'P95S':>6}")
    print(f"  {'-'*34}  {'-'*4}  {'-'*4}  {'-'*4}  {'-'*6}  {'-'*6}")
    for tn in tools_seen:
        sub = [r for r in all_runs if r.tool_name == tn]
        ok_dur = [r.duration for r in sub if r.success]
        np = sum(1 for r in sub if r.success)
        nf = len(sub) - np
        avg = statistics.mean(ok_dur) if ok_dur else 0
        p95 = percentile(ok_dur, 95) if ok_dur else 0
        print(f"  {tn:<34}  {len(sub):>4}  {np:>4}  {nf:>4}  "
              f"{avg:>6.1f}  {p95:>6.1f}")
    print()

    errors = [(r.user_id, r.tool_name, r.error) for r in all_runs if not r.success]
    if errors:
        print(f"  Failures ({len(errors)}):")
        seen = set()
        for uid, tn, err in errors[:20]:
            key = (tn, (err or "")[:60])
            if key not in seen:
                print(f"    {tn:<34}  {(err or 'no error')[:60]}")
                seen.add(key)
    print(f"{'=' * 78}\n")

    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": BASE_URL,
        "config": {"run_id": run_id, "num_users": NUM_USERS,
                   "tools_per_user": TOOLS_PER_USER,
                   "arrival_window_s": ARRIVAL_WINDOW},
        "summary": {"total": total, "passed": passed, "failed": failed,
                    "retried": retried, "wall_time_s": round(wall_time, 1),
                    "throughput_per_min": round(passed/(wall_time/60), 2) if wall_time > 0 else 0},
        "latency": {
            "p50": round(percentile(durations, 50), 1),
            "p75": round(percentile(durations, 75), 1),
            "p95": round(percentile(durations, 95), 1),
            "p99": round(percentile(durations, 99), 1),
            "min": round(min(durations), 1) if durations else 0,
            "avg": round(statistics.mean(durations), 1) if durations else 0,
            "max": round(max(durations), 1) if durations else 0,
            "first_event_p50": round(percentile(first_events, 50), 1),
            "first_event_p95": round(percentile(first_events, 95), 1),
            "first_work_p50": round(percentile(first_work, 50), 1),
            "first_work_p95": round(percentile(first_work, 95), 1),
        },
        "capacity": {
            "queued_runs": len(capacity_queued),
            "maximum_reported_queue_position": max(
                (r.queue_position for r in capacity_queued),
                default=0,
            ),
            "before": capacity_before,
            "after": capacity_after,
            "retention_probe": retention_probe,
            "session_retention_ok": retention_ok,
        },
        "per_tool": [{
            "tool": tn,
            "runs": len([r for r in all_runs if r.tool_name == tn]),
            "passed": sum(1 for r in all_runs if r.tool_name == tn and r.success),
        } for tn in tools_seen],
        "failures": [{"user": r.user_id, "tool": r.tool_name, "error": r.error}
                     for r in all_runs if not r.success][:50],
    }


async def get_capacity_snapshot() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{BASE_URL}/health/capacity")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        return None


async def get_session_retention(session_ids: list[str]) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{BASE_URL}/health/capacity/sessions",
                json={"session_ids": session_ids},
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(num_users: int = NUM_USERS):
    run_id = f"stress-{time.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
    print(f"\n{'=' * 78}")
    print(f"  CSIS Stress Test  →  {BASE_URL}  (model: {DEFAULT_MODEL})")
    print(f"  {num_users} users  {TOOLS_PER_USER} tools/user  "
          f"arrival window: {ARRIVAL_WINDOW}s  run: {run_id}")
    print(f"{'=' * 78}\n")

    arrivals = sorted([random.uniform(0, ARRIVAL_WINDOW) for _ in range(num_users)])
    arrivals[0] = 0.0

    user_tools = []
    for _ in range(num_users):
        chosen = random.sample(ALL_TOOLS, min(TOOLS_PER_USER, len(ALL_TOOLS)))
        random.shuffle(chosen)
        user_tools.append(chosen)
    session_ids = [f"{run_id}-u{i+1:03d}" for i in range(num_users)]

    print("  First 5 users:")
    for i in range(min(5, num_users)):
        print(f"    u{i+1:02d}  +{arrivals[i]:.1f}s  {[t[0] for t in user_tools[i]]}")
    print(f"  ... ({num_users} total)\n")

    all_runs: list = []
    metric_samples: list = []
    stop = asyncio.Event()
    metrics_task = asyncio.create_task(
        metrics_collector(metric_samples, stop, interval=METRICS_INTERVAL))

    wall_start = time.time()
    capacity_before = await get_capacity_snapshot()
    print("▶ Starting stress test ...\n")

    tasks = [
        run_user(session_ids[i], user_tools[i], arrivals[i], all_runs)
        for i in range(num_users)
    ]
    await asyncio.gather(*tasks)

    wall_time = time.time() - wall_start
    stop.set()
    await asyncio.sleep(0.2)
    metrics_task.cancel()

    print(f"\n■ Complete  wall={wall_time:.1f}s\n")
    capacity_after = await get_capacity_snapshot()
    retention_probe = await get_session_retention(session_ids)
    report = print_stress_report(
        all_runs,
        wall_time,
        capacity_before=capacity_before,
        capacity_after=capacity_after,
        retention_probe=retention_probe,
        run_id=run_id,
    )

    if metric_samples:
        print("── Resource Usage ──")
        print_metrics(metric_samples, wall_time)

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved → {REPORT_PATH}")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=NUM_USERS,
                        help=f"Number of concurrent users (default: {NUM_USERS})")
    parser.add_argument("--request-timeout", type=int, default=900)
    parser.add_argument("--min-pass-rate", type=float, default=99.0)
    args = parser.parse_args()
    NUM_USERS = args.users
    ALL_TOOLS = [
        (name, files, prompt, max(timeout, args.request_timeout))
        for name, files, prompt, timeout in ALL_TOOLS
    ]
    result = asyncio.run(main(num_users=args.users))
    pass_rate = 100 * result["summary"]["passed"] / max(1, result["summary"]["total"])
    capacity_ok = result["capacity"]["session_retention_ok"] is True
    raise SystemExit(0 if pass_rate >= args.min_pass_rate and capacity_ok else 1)
