"""
LLM-path integration test: sends real natural-language prompts to /api/chat (Gemini),
measures wall-clock time from prompt → tool_result SSE event.

Endpoint: POST /api/chat  (multipart form: message=<str>; header: X-Session-ID)

Run on GCP server:  python3 test_llm_path.py
Results saved to:   /tmp/llm_test_results.json
"""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

BASE_URL = "http://localhost"

SD = "/data/datainput/SampleData"   # NatCap sample data (symlinked)
DD = "/data/datainput"              # demo input data

TESTS = [
    # ── Fast tools (<3 s InVEST) ─────────────────────────────────────────────
    {
        "tool": "CBC Preprocessor",
        "suffix": "cbc_pre",
        "message": (
            "Call run_coastal_blue_carbon_preprocessor with: "
            f"landcover_snapshot_csv={DD}/CoastalBLueCarbonPreprocessor_input/snapshots.csv, "
            f"landcover_lookup_table={DD}/CoastalBLueCarbonPreprocessor_input/lulc_lookup.csv."
        ),
    },
    {
        "tool": "DelineateIt",
        "suffix": "delin",
        "message": (
            "Run DelineateIt watershed delineation. "
            f"dem_path={SD}/DelineateIt/DEM_gura.tif, "
            f"outlet_vector_path={SD}/DelineateIt/outlet_points.shp, "
            "snap_points=true, flow_threshold=1000, snap_distance=50."
        ),
    },
    {
        "tool": "Annual Water Yield",
        "suffix": "awy",
        "message": (
            "Run the Annual Water Yield model. "
            f"lulc_path={SD}/Annual_Water_Yield/land_use_gura.tif, "
            f"eto_path={SD}/Annual_Water_Yield/reference_ET_gura.tif, "
            f"precipitation_path={SD}/Annual_Water_Yield/precipitation_gura.tif, "
            f"depth_to_root_rest_layer_path={SD}/Annual_Water_Yield/depth_to_root_restricting_layer_gura.tif, "
            f"pawc_path={SD}/Annual_Water_Yield/plant_available_water_fraction_gura.tif, "
            f"biophysical_table_path={SD}/Annual_Water_Yield/biophysical_table_gura.csv, "
            f"watersheds_path={SD}/Annual_Water_Yield/watershed_gura.shp, "
            f"sub_watersheds_path={SD}/Annual_Water_Yield/subwatersheds_gura.shp, "
            "seasonality_constant=15."
        ),
    },
    # ── Medium tools (3–10 s InVEST) ─────────────────────────────────────────
    {
        "tool": "Carbon Storage",
        "suffix": "carbon",
        "message": (
            "Run Carbon Storage and Sequestration. "
            f"lulc_cur_path={SD}/Carbon/lulc_current_willamette.tif, "
            f"carbon_pools_path={SD}/Carbon/carbon_pools_willamette.csv."
        ),
    },
    {
        "tool": "Crop Production Percentile",
        "suffix": "crop_pct",
        "message": (
            "Call run_crop_production_percentile with: "
            f"landcover_raster_path={DD}/CropProductionPercentile_input/sample_user_data/landcover.tif, "
            f"landcover_to_crop_table_path={DD}/CropProductionPercentile_input/sample_user_data/landcover_to_crop_table.csv, "
            f"aggregate_polygon_path={DD}/CropProductionPercentile_input/sample_user_data/aggregate_shape.shp."
        ),
    },
    {
        "tool": "Habitat Quality",
        "suffix": "hq",
        "message": (
            "Run Habitat Quality. "
            f"lulc_cur_path={SD}/HabitatQuality/lulc_current_willamette.tif, "
            f"access_vector_path={SD}/HabitatQuality/accessibility_willamette.shp, "
            f"sensitivity_table_path={SD}/HabitatQuality/sensitivity_willamette.csv, "
            f"threats_table_path={SD}/HabitatQuality/threats_willamette.csv, "
            "half_saturation_constant=0.05."
        ),
    },
    {
        "tool": "NDR",
        "suffix": "ndr",
        "message": (
            "Run the Nutrient Delivery Ratio (NDR) model. "
            f"dem_path={SD}/NDR/DEM_gura.tif, "
            f"lulc_path={SD}/NDR/land_use_gura.tif, "
            f"runoff_proxy_path={SD}/NDR/precipitation_gura.tif, "
            f"watersheds_path={SD}/NDR/watershed_gura.shp, "
            f"biophysical_table_path={SD}/NDR/biophysical_table_gura.csv, "
            "calc_p=true, calc_n=true, "
            "threshold_flow_accumulation=1000, k_param=2, "
            "subsurface_critical_length_n=200, subsurface_eff_n=0.8."
        ),
    },
    {
        "tool": "SDR",
        "suffix": "sdr",
        "message": (
            "Call run_Sediment_Delivery_Ratio_SDR with: "
            f"dem_path={SD}/SDR/DEM_gura.tif, "
            f"erosivity_path={SD}/SDR/erosivity_gura.tif, "
            f"erodibility_path={SD}/SDR/erodibility_gura.tif, "
            f"lulc_path={SD}/SDR/land_use_gura.tif, "
            f"watersheds_path={SD}/SDR/watershed_gura.shp, "
            f"biophysical_table_path={SD}/SDR/biophysical_table_Gura.csv, "
            "threshold_flow_accumulation=1000, k_param=2, ic_0_param=0.5, sdr_max=0.8."
        ),
    },
    # ── Slow tools (10–30 s InVEST) ──────────────────────────────────────────
    {
        "tool": "Seasonal Water Yield",
        "suffix": "swy",
        "message": (
            "Call run_seasonal_water_yield with: "
            f"lulc_raster_path={DD}/SeasonalWaterYield_input/land_use_gura.tif, "
            f"et0_dir={DD}/SeasonalWaterYield_input/ET0_monthly/, "
            f"precip_dir={DD}/SeasonalWaterYield_input/Precipitation_monthly/, "
            f"soil_group_path={DD}/SeasonalWaterYield_input/soil_group_gura.tif, "
            f"aoi_path={DD}/SeasonalWaterYield_input/watershed_gura.shp, "
            f"biophysical_table_path={DD}/SeasonalWaterYield_input/biophysical_table_gura_SWY.csv, "
            f"dem_raster_path={DD}/SeasonalWaterYield_input/DEM_gura.tif, "
            f"rain_events_table_path={DD}/SeasonalWaterYield_input/rain_events_gura.csv, "
            "threshold_flow_accumulation=1000, alpha_m=0.083333, beta_i=1.0, gamma=1.0."
        ),
    },
    {
        "tool": "Pollination",
        "suffix": "poll",
        "message": (
            "Call run_crop_pollination with: "
            f"landcover_raster_path={SD}/pollination/landcover.tif, "
            f"landcover_biophysical_table_path={SD}/pollination/landcover_biophysical_table.csv, "
            f"guild_table_path={SD}/pollination/guild_table.csv, "
            f"farm_vector_path={SD}/pollination/farms.shp."
        ),
    },
]


def post_form_sse(session_id: str, message: str):
    """POST multipart form to /api/chat and yield parsed SSE event dicts."""
    form_data = urllib.parse.urlencode({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=form_data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Session-ID": session_id,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=360) as resp:
        buf = b""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n\n" in buf:
                block, buf = buf.split(b"\n\n", 1)
                for line in block.decode("utf-8", errors="replace").splitlines():
                    if line.startswith("data: "):
                        raw = line[6:].strip()
                        if raw:
                            try:
                                yield json.loads(raw)
                            except json.JSONDecodeError:
                                pass


def run_one(entry: dict) -> dict:
    tool = entry["tool"]
    session_id = f"llmtest_{entry['suffix']}_{int(time.time())}"
    message = entry["message"]

    print(f"\n{'='*65}")
    print(f"Tool:    {tool}")
    print(f"Session: {session_id}")
    print(f"Prompt:  {message[:100]}...")

    t0 = time.time()
    tool_started = None
    tool_finished = None
    success = None
    error_msg = None
    events_seen = []

    try:
        for ev in post_form_sse(session_id, message):
            ev_type = ev.get("type", "?")
            events_seen.append(ev_type)
            now = time.time()

            if ev_type == "tool_start":
                tool_started = now
                print(f"  [{now-t0:5.1f}s] tool_start  → {ev.get('tool_name','')}")

            elif ev_type == "tool_progress":
                pct = ev.get("progress", "?")
                msg = ev.get("message", "")
                print(f"  [{now-t0:5.1f}s] progress {pct}%: {msg}")

            elif ev_type == "tool_result":
                tool_finished = now
                success = ev.get("success", True)
                fcount = len(ev.get("files", []))
                print(f"  [{now-t0:5.1f}s] tool_result  success={success}  files={fcount}")

            elif ev_type == "error":
                tool_finished = now
                success = False
                error_msg = ev.get("message", str(ev))
                print(f"  [{now-t0:5.1f}s] ERROR: {error_msg}")

            elif ev_type in ("text_chunk", "text"):
                txt = ev.get("content", ev.get("text", ""))
                if txt.strip():
                    print(f"  [{now-t0:5.1f}s] LLM text: {txt[:120]}")

    except Exception as exc:
        if tool_finished is None:
            tool_finished = time.time()
        success = False
        error_msg = str(exc)
        print(f"  EXCEPTION: {exc}")

    total = time.time() - t0
    tool_exec    = (tool_finished - tool_started) if (tool_started and tool_finished) else None
    llm_overhead = (tool_started  - t0)           if tool_started else None

    if success is None:
        success = False

    result = {
        "tool": tool,
        "success": success,
        "total_s": round(total, 1),
        "llm_overhead_s": round(llm_overhead, 1) if llm_overhead is not None else None,
        "tool_exec_s":    round(tool_exec,    1) if tool_exec    is not None else None,
        "error": error_msg,
        "events": events_seen,
    }

    if llm_overhead is not None:
        print(
            f"  → total={total:.1f}s  "
            f"llm_overhead={llm_overhead:.1f}s  "
            f"tool_exec={tool_exec:.1f}s  "
            f"success={success}"
        )
    else:
        print(f"  → total={total:.1f}s  success={success}  error={error_msg}")

    return result


def main():
    results = []
    for entry in TESTS:
        r = run_one(entry)
        results.append(r)
        time.sleep(12)  # pause to avoid Gemini rate limits / safety filter

    print("\n\n" + "="*75)
    print("LLM PATH TEST SUMMARY")
    print("="*75)
    print(f"{'Tool':<30} {'Total':>8} {'LLM OH':>8} {'InVEST':>8}  Status")
    print("-"*75)
    for r in results:
        status = "PASS" if r["success"] else f"FAIL: {(r['error'] or '')[:28]}"
        tot = f"{r['total_s']:.1f}s"          if r["total_s"]        is not None else "N/A"
        llm = f"{r['llm_overhead_s']:.1f}s"   if r["llm_overhead_s"] is not None else "N/A"
        inv = f"{r['tool_exec_s']:.1f}s"      if r["tool_exec_s"]    is not None else "N/A"
        print(f"{r['tool']:<30} {tot:>8} {llm:>8} {inv:>8}  {status}")

    with open("/tmp/llm_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nFull results → /tmp/llm_test_results.json")


if __name__ == "__main__":
    main()
