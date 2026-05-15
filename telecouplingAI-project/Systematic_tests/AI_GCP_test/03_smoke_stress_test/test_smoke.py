"""
03_smoke_stress_test / test_smoke.py
Smoke test: realistic multi-user simulation.

Phase 1 : 1 user, all available tools, sequential
Phase 2 : 5 concurrent users, staggered arrival (0-8s), randomised tool order
          + resource metrics (CPU/RAM/Network) sampled every 5s

Merged from AI_Smoke_GCP_test/test_gcp_e2e.py (updated for all tools).

Run:
    cd Systematic_tests/AI_GCP_test
    CSIS_BASE_URL=http://localhost python 03_smoke_stress_test/test_smoke.py
    CSIS_BASE_URL=http://localhost python 03_smoke_stress_test/test_smoke.py --phase 1
"""
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _utils import (
    BASE_URL, DEMO, SD, DEFAULT_MODEL, new_sid,
    MetricSample, metrics_collector, print_metrics, percentile,
)

REPORT_PATH = os.path.join(os.path.dirname(__file__), "results_smoke.json")
NUM_USERS        = 5
ARRIVAL_WINDOW_S = 8
METRICS_INTERVAL = 5

DD  = DEMO
SAM = SD


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ToolRun:
    tool_name: str
    success:   bool
    duration:  float
    retried:   bool = False
    files:     list = field(default_factory=list)
    error:     Optional[str] = None

@dataclass
class UserResult:
    user_id:       str
    tool_results:  list = field(default_factory=list)
    total_duration: float = 0.0
    start_delay_s: float = 0.0

    @property
    def passed(self): return sum(1 for r in self.tool_results if r.success)
    @property
    def failed(self): return sum(1 for r in self.tool_results if not r.success)


# ── Inline CSV data for TeleBox tools ─────────────────────────────────────────

OLS_CSV  = (b"id,gdp,pop,forest,co2\n"
            b"1,14000,1400,22.3,10000\n2,21000,330,33.8,5000\n"
            b"3,4000,83,31.7,700\n4,3000,67,29.2,400\n5,5000,126,68.5,1200\n"
            b"6,2000,45,15.2,300\n7,1500,33,12.8,200\n8,800,20,45.6,100\n"
            b"9,600,18,62.1,80\n10,400,10,78.3,50\n")
CO2_CSV  = (b"route_id,animal_count,length_km\n"
            b"route_001,50,120.5\nroute_002,30,85.2\nroute_003,75,200.0\n"
            b"route_004,20,45.8\nroute_005,60,310.7\n")
FOOD_CSV = (b"Area,Year,Item,Value\n"
            b"China,2019,Undernourishment,2.5\nIndia,2019,Undernourishment,14.0\n"
            b"Nigeria,2019,Undernourishment,14.8\nBrazil,2019,Undernourishment,6.5\n"
            b"China,2020,Undernourishment,2.5\nIndia,2020,Undernourishment,15.3\n"
            b"Nigeria,2020,Undernourishment,18.0\nBrazil,2020,Undernourishment,7.0\n")


# ── Tool definitions ──────────────────────────────────────────────────────────
# (name, inline_files [(fname, bytes, mime)], prompt, timeout_s)

TOOLS_AVAILABLE = [
    ("Tool01_NetworkAnalysis",
     [],
     (f"Run Network Analysis with files at "
      f"{DD}/NetworkAnalysisGrouping_input/Network Analysis Grouping/. "
      f"nodes_table=nodes.csv, links_table=links.csv, "
      f"shapefile_path=World_countries_2002.shp, "
      f"nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, "
      f"clustering_algorithm=walktrap. Run immediately."),
     270),

    ("Tool02_CBCPreprocessor",
     [],
     (f"Call run_coastal_blue_carbon_preprocessor with: "
      f"landcover_snapshot_csv={DD}/CoastalBLueCarbonPreprocessor_input/snapshots.csv, "
      f"landcover_lookup_table={DD}/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv, "
      f"lulc_snapshot_list=[{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2010_mean_Resample.tif,"
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2030_mean_Resample.tif,"
      f"{DD}/CoastalBLueCarbonPreprocessor_input/GBJC_2050_mean_Resample.tif]. Run immediately."),
     270),

    ("Tool07_Carbon",
     [],
     (f"Call run_carbon_storage with: "
      f"lulc_cur_path={SAM}/Carbon/lulc_current_willamette.tif, "
      f"carbon_pools_path={SAM}/Carbon/carbon_pools_willamette.csv. Run immediately."),
     180),

    ("Tool08_HabitatQuality",
     [],
     (f"Call run_habitat_quality with: "
      f"lulc_cur_path={SAM}/HabitatQuality/lulc_current_willamette.tif, "
      f"access_vector_path={SAM}/HabitatQuality/accessibility_willamette.shp, "
      f"sensitivity_table_path={SAM}/HabitatQuality/sensitivity_willamette.csv, "
      f"threats_table_path={SAM}/HabitatQuality/threats_willamette.csv, "
      f"half_saturation_constant=0.05. Run immediately."),
     300),

    ("Tool09_AWY",
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

    ("Tool28_OLS",
     [("ols.csv", OLS_CSV, "text/csv")],
     ("Call run_ols with the uploaded ols.csv: "
      "dependent_variable=co2, independent_variables=gdp,pop,forest. Run immediately."),
     120),

    ("Tool30_CO2",
     [("co2_transport.csv", CO2_CSV, "text/csv")],
     ("Call run_co2_emissions with the uploaded co2_transport.csv. "
      "capacity_per_trip=10, co2_per_km_per_trip=0.8, "
      "animal_count_field=animal_count, length_km_field=length_km. Run immediately."),
     120),

    ("Tool41_FoodSecurity",
     [("food_fao.csv", FOOD_CSV, "text/csv")],
     ("Call run_food_security with the uploaded food_fao.csv. "
      "countries=China,India,Nigeria,Brazil, "
      "indicator_field=Undernourishment, country_field=Area, year_field=Year, "
      "value_field=Value. Run immediately."),
     120),
]


# ── HTTP helpers (async) ──────────────────────────────────────────────────────

async def upload_files_async(client: httpx.AsyncClient, session_id: str,
                              files: list) -> tuple:
    """Upload inline bytes. Returns (ok, error_msg)."""
    if not files:
        return True, ""
    multipart = [("files", (fname, data, mime)) for fname, data, mime in files]
    try:
        r = await client.post(
            f"{BASE_URL}/api/upload",
            headers={"X-Session-ID": session_id},
            files=multipart,
            timeout=60,
        )
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        return True, ""
    except Exception as e:
        return False, str(e)


async def run_chat_async(client: httpx.AsyncClient, session_id: str,
                          prompt: str, timeout: int) -> tuple:
    """Returns (success, files, error, tool_invoked)."""
    output_files = []
    tool_invoked = False
    error = None

    try:
        async with client.stream(
            "POST", f"{BASE_URL}/api/chat",
            headers={"X-Session-ID": session_id},
            data={"message": prompt, "model": DEFAULT_MODEL},
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                return False, [], f"HTTP {resp.status_code}", False
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    ev = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type", "")
                if etype == "tool_start":
                    tool_invoked = True
                elif etype == "tool_result":
                    output_files = [f["filename"] for f in ev.get("files", [])]
                elif etype == "error":
                    error = ev.get("message", "unknown error")
    except Exception as e:
        error = str(e)

    success = bool(output_files) and not error
    return success, output_files, error, tool_invoked


# ── Single user session ───────────────────────────────────────────────────────

async def run_user_session(user_id: str, tools: list,
                            start_delay: float = 0.0) -> UserResult:
    result = UserResult(user_id=user_id, start_delay_s=start_delay)
    if start_delay > 0:
        print(f"[{user_id}] arriving in {start_delay:.1f}s ...")
        await asyncio.sleep(start_delay)

    t_session = time.time()
    print(f"[{user_id}] ▶ started  tools={[t[0] for t in tools]}")

    async with httpx.AsyncClient() as client:
        for tool_name, files, prompt, timeout in tools:
            sid = f"{user_id}-{tool_name}"
            t0 = time.time()

            ok, err = await upload_files_async(client, sid, files)
            if not ok:
                result.tool_results.append(ToolRun(tool_name, False,
                                                    time.time()-t0, error=f"upload: {err}"))
                continue

            retried = False
            for attempt in range(2):
                try:
                    success, out_files, error, invoked = await run_chat_async(
                        client, sid, prompt, timeout)
                except Exception as e:
                    success, out_files, error, invoked = False, [], str(e), False

                if success:
                    break
                if not invoked and attempt == 0:
                    retried = True
                    await asyncio.sleep(2)
                else:
                    break

            duration = time.time() - t0
            result.tool_results.append(ToolRun(tool_name, success, duration,
                                                retried=retried, files=out_files,
                                                error=error))
            icon = "✓" if success else "✗"
            retry = " ↩" if retried else ""
            extra = f"  → {error[:60]}" if error else f"  → {len(out_files)} files"
            print(f"[{user_id}] {icon}{retry} {tool_name:<32}  {duration:.1f}s{extra}")

    result.total_duration = time.time() - t_session
    print(f"[{user_id}] ■ done  {result.passed}/{len(tools)} passed  "
          f"({result.total_duration:.1f}s)")
    return result


# ── Reports ───────────────────────────────────────────────────────────────────

def print_phase_report(phase_name: str, results: list):
    total = sum(len(r.tool_results) for r in results)
    passed = sum(r.passed for r in results)
    failed = sum(r.failed for r in results)
    retried = sum(1 for r in results for tr in r.tool_results if tr.retried)

    print(f"\n{'=' * 78}")
    print(f"  {phase_name}")
    print(f"{'=' * 78}")
    print(f"  Users: {len(results)}  Tests: {total}  "
          f"Passed: {passed}  Failed: {failed}  Auto-retried: {retried}")
    print()
    for ur in results:
        d = f"  (arrived +{ur.start_delay_s:.1f}s)" if ur.start_delay_s else ""
        print(f"  User {ur.user_id:<14}  {ur.passed}/{len(ur.tool_results)} passed  "
              f"({ur.total_duration:.1f}s){d}")
        for tr in ur.tool_results:
            icon = "✓" if tr.success else "✗"
            r = " ↩" if tr.retried else "  "
            e = f"  → {tr.error[:55]}" if tr.error else ""
            print(f"    {icon}{r} {tr.tool_name:<34}  {tr.duration:>7.1f}s{e}")
        print()
    pct = int(100 * passed / total) if total else 0
    print(f"  ── Overall: {passed}/{total} ({pct}%) ──")
    print(f"{'=' * 78}\n")
    return passed, failed


def build_report(p1: list, p2: list, metrics: list, wall_time: float) -> dict:
    def results_dict(results):
        return [{
            "user_id": r.user_id,
            "passed": r.passed,
            "failed": r.failed,
            "total_s": round(r.total_duration, 1),
            "tools": [{"name": t.tool_name, "success": t.success,
                       "duration_s": round(t.duration, 1), "error": t.error}
                      for t in r.tool_results],
        } for r in results]

    cpu = [s.cpu_pct for s in metrics]
    mem = [s.mem_used_mb for s in metrics]
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": BASE_URL,
        "phase1": results_dict(p1),
        "phase2": results_dict(p2),
        "phase2_wall_s": round(wall_time, 1),
        "metrics": {
            "samples": len(metrics),
            "cpu_avg": round(sum(cpu)/len(cpu), 1) if cpu else 0,
            "cpu_peak": round(max(cpu), 1) if cpu else 0,
            "mem_avg_mb": round(sum(mem)/len(mem), 0) if mem else 0,
            "mem_peak_mb": round(max(mem), 0) if mem else 0,
        },
    }


# ── Main ──────────────────────────────────────────────────────────────────────

async def main(run_phase: int = 0):
    print(f"\n{'=' * 78}")
    print(f"  CSIS Smoke Test  →  {BASE_URL}  (model: {DEFAULT_MODEL})")
    print(f"  {len(TOOLS_AVAILABLE)} tools available, {NUM_USERS} concurrent users in Phase 2")
    print(f"{'=' * 78}")

    p1_results = []
    p2_results = []
    metrics: list = []

    # ── Phase 1: single user, sequential ─────────────────────────────────────
    if run_phase in (0, 1):
        print("\n▶ PHASE 1 — Single user, sequential\n")
        r = await run_user_session("phase1-u1", TOOLS_AVAILABLE)
        p1_results = [r]
        print_phase_report("PHASE 1 — SINGLE USER", p1_results)

    # ── Phase 2: concurrent users ─────────────────────────────────────────────
    if run_phase in (0, 2):
        print(f"\n▶ PHASE 2 — {NUM_USERS} concurrent users "
              f"(staggered 0-{ARRIVAL_WINDOW_S}s, randomised tool order)\n")

        delays = sorted(
            [max(0, i * ARRIVAL_WINDOW_S / (NUM_USERS - 1)
                 + random.uniform(-1, 1)) for i in range(NUM_USERS)]
        )
        delays[0] = 0.0

        user_tool_lists = []
        for _ in range(NUM_USERS):
            shuffled = list(TOOLS_AVAILABLE)
            random.shuffle(shuffled)
            user_tool_lists.append(shuffled[:4])   # 4 tools per user in smoke test

        stop = asyncio.Event()
        metrics_task = asyncio.create_task(
            metrics_collector(metrics, stop, interval=METRICS_INTERVAL)
        )
        wall_start = time.time()

        tasks = [
            run_user_session(f"p2-u{i+1}", user_tool_lists[i], delays[i])
            for i in range(NUM_USERS)
        ]
        p2_results = list(await asyncio.gather(*tasks))
        wall_time = time.time() - wall_start

        stop.set()
        await asyncio.sleep(0.1)
        metrics_task.cancel()

        print(f"\n  Phase 2 wall time: {wall_time:.1f}s")
        print_phase_report("PHASE 2 — CONCURRENT USERS", p2_results)
        if metrics:
            print("── Resource Usage ──")
            print_metrics(metrics, wall_time)

    # ── Save report ───────────────────────────────────────────────────────────
    report = build_report(p1_results, p2_results, metrics,
                          wall_time if run_phase in (0, 2) else 0)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → {REPORT_PATH}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, choices=[1, 2], default=0,
                        help="1=single user  2=concurrent  (default: both)")
    args = parser.parse_args()
    asyncio.run(main(run_phase=args.phase))
