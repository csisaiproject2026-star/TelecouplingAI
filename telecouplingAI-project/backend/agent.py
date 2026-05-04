"""
CSIS Agent — Google Gemini function calling loop with two-phase Skill loading.

Skills are loaded from .claude/skills/ at two distinct moments:

  Phase 1 — PRE_EXECUTION (before first Gemini call):
    All skills' [PRE_EXECUTION] sections are parsed and appended to the
    system instruction. This gives Gemini the knowledge to decide WHEN to
    use each tool and HOW to collect parameters from the user.

  Phase 2 — POST_EXECUTION (after a tool completes):
    The specific skill's [POST_EXECUTION] section is injected alongside
    the tool result, so Gemini can accurately explain outputs and suggest
    next steps.

  [DEV ONLY] sections are never loaded at runtime.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Callable, Any

import os

from google import genai
from google.genai import types
from google.genai.client import HttpOptions
import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini concurrency limiter — max 3 simultaneous API calls
# ---------------------------------------------------------------------------

_GEMINI_SEMAPHORE = asyncio.Semaphore(3)

async def _generate_with_retry(client, model_name: str, contents, config, max_retries: int = 4):
    """Call generate_content with semaphore + exponential backoff on 429/503."""
    import random
    for attempt in range(max_retries):
        async with _GEMINI_SEMAPHORE:
            try:
                return await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str
                is_server_err = "503" in err_str or "unavailable" in err_str
                if (is_rate_limit or is_server_err) and attempt < max_retries - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"[agent] Gemini {'rate limit' if is_rate_limit else 'server error'} "
                                   f"(attempt {attempt+1}/{max_retries}), retrying in {wait:.1f}s")
                    await asyncio.sleep(wait)
                else:
                    raise

# ---------------------------------------------------------------------------
# Gemini client — lazy singleton, created on first use
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    import httpx
    # Always create a fresh client — the genai SDK may close the httpx.AsyncClient
    # after each session, so reusing a cached client causes ConnectError on
    # subsequent requests. Fresh clients are lightweight and avoid stale pool issues.
    return genai.Client(
        api_key=settings.GOOGLE_API_KEY,
        http_options=HttpOptions(
            httpx_client=httpx.Client(verify=False, timeout=300.0),
            httpx_async_client=httpx.AsyncClient(verify=False, timeout=300.0),
        ),
    )


# ---------------------------------------------------------------------------
# Skill directory
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent
SKILL_DIR = _PROJECT_ROOT / ".claude" / "skills"

TOOL_TO_SKILL: dict[str, str] = {
    "run_network_analysis_grouping":          "run-network-analysis",
    "run_coastal_blue_carbon_preprocessor":   "run-cbc-preprocessor",
    "run_coastal_blue_carbon":                "run-coastal-blue-carbon",
    "run_seasonal_water_yield":               "run-seasonal-water-yield",
    "run_crop_production_percentile":         "run-crop-percentile",
    "run_crop_production_regression":         "run-crop-regression",
}

# ---------------------------------------------------------------------------
# Skill parser
# ---------------------------------------------------------------------------

_SECTION_RE = re.compile(r"^##\s+\[(DEV ONLY|PRE_EXECUTION|POST_EXECUTION)\]", re.MULTILINE)


def _parse_skill_sections(content: str) -> dict[str, str]:
    sections: dict[str, str] = {"DEV ONLY": "", "PRE_EXECUTION": "", "POST_EXECUTION": ""}
    matches = list(_SECTION_RE.finditer(content))
    for i, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[name] = content[start:end].strip()
    return sections


def _load_skill_section(tool_name: str, section: str) -> str | None:
    skill_name = TOOL_TO_SKILL.get(tool_name)
    if not skill_name:
        return None
    skill_path = SKILL_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        logger.warning(f"[skill] SKILL.md not found: {skill_path}")
        return None
    try:
        content = skill_path.read_text(encoding="utf-8")
        result = _parse_skill_sections(content).get(section, "").strip()
        if result:
            logger.info(f"[skill] Loaded [{section}] for {tool_name} ({len(result)} chars)")
        return result or None
    except OSError as e:
        logger.error(f"[skill] Failed to read {skill_path}: {e}")
        return None


def _build_pre_execution_context() -> str:
    parts: list[str] = []
    for tool_name in TOOL_TO_SKILL:
        section = _load_skill_section(tool_name, "PRE_EXECUTION")
        if section:
            parts.append(f"---\n{section}")
    if parts:
        return (
            "\n\n## Tool Skill Knowledge (Pre-Execution)\n"
            "Use the following skill specifications to determine when to invoke each tool "
            "and how to collect the required parameters from the user.\n\n"
            + "\n\n".join(parts)
        )
    return ""


# ---------------------------------------------------------------------------
# System instruction (base)
# ---------------------------------------------------------------------------

_BASE_SYSTEM_INSTRUCTION = """
You are CSIS Assistant, an expert in ecosystem services modelling (InVEST) and spatial analysis.
Always respond in the same language as the user.

## Greeting Behaviour
When the user sends a greeting (e.g. "hello", "hi", "hey", "good morning", or any equivalent in other languages), respond with exactly:
"I am an expert in Telecoupling toolbox, who has a solid background to assist you on across scales of human natural integrations analysis."
Do not add any other text to this greeting response.

## Available Tools Overview
- Tool 1: run_network_analysis_grouping — network/flow analysis using R + igraph
- Tool 2: run_coastal_blue_carbon_preprocessor — LULC transition preprocessing for blue carbon
- Tool 3: run_coastal_blue_carbon — carbon stock, sequestration and NPV analysis
- Tool 4: run_seasonal_water_yield — quickflow, baseflow and local recharge modelling
- Tool 5: run_crop_production_percentile — crop yield for 172 crops based on climate percentiles
- Tool 6: run_crop_production_regression — crop yield based on fertilizer NPK rates (10 crops)
- read_file_content — read and analyze any output file (CSV, TXT) to answer user questions
- render_spatial_file — render a spatial output file (TIF, SHP) to a map image

## File Analysis
When a user asks to summarize, analyze, or asks questions about a specific output file (e.g. "summarize the CSV", "what are the top nodes?", "which country has the highest degree?"), call read_file_content with the file's internal_path. Then use the returned data to provide a detailed, domain-relevant analysis. Do NOT say you cannot read files.

## Uploaded File Handling
When the user uploads files, their paths are listed at the top of the message in the format:
  "Uploaded file: <filename> at <path>"

Apply the following rules consistently:
- Before asking the user for any file path, check whether an uploaded file already satisfies that parameter
- If an uploaded file matches a required input, use its path directly — do NOT ask the user to provide it again
- Only prompt for file paths that are genuinely missing from the uploaded files
- If all required files have been uploaded and no other parameters are missing, proceed to call the tool immediately

## Domain Knowledge

### Telecoupling framework
All tools in CSIS operate within the telecoupling framework — the study of flows (trade, migration, carbon, water, food) between distant coupled human-nature systems. Network communities reveal systemic dependencies across global supply chains and ecosystems.

### Coastal Blue Carbon (Tools 2 & 3)
Mangroves, salt marshes, and seagrasses sequester carbon 3–5× faster per hectare than tropical forests and store it for centuries. Three carbon pools are tracked: **biomass** (above-ground tissue, fast turnover), **soil** (dominant pool in mangroves; 50–90% of total; slow release), **litter** (surface dead matter). When disturbed, carbon is released via exponential decay based on each pool's half-life. The transitions CSV controls whether each LULC change is `accumulation`, `NCC`, or a disturbance level (`low/med/high-impact-disturb`). NPV is calculated using discounted carbon prices ($15–$150/Mg CO₂e depending on market).

### Seasonal Water Yield (Tool 4)
Quantifies **quickflow** (surface runoff — unproductive, flood-risk), **baseflow** (slow groundwater release — dry-season water supply), and **local recharge** (precipitation − quickflow − ET). Forests produce high baseflow, low quickflow. Urban/bare land does the opposite. Uses the NRCS Curve Number method combined with soil hydrologic groups (A=sandy/low QF → D=clay/high QF). Key policy metric: baseflow index `qb` per sub-watershed identifies water tower areas to protect.

### Crop Production Percentile (Tool 5)
Reports yield at 25th/50th/75th/95th climate percentiles for 172 crops based on Monfreda et al. (2008) global dataset. The 25th percentile ≈ low-intensity farming; 95th ≈ near-optimal management. The **yield gap** (95th − observed) quantifies intensification potential without expanding cropland. Includes 33-nutrient analysis. Use when you need broad crop coverage or multi-crop landscapes.

### Crop Production Regression (Tool 6)
Estimates yield for 10 staple crops (barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, wheat) from N/P/K fertilizer rates (kg/ha). Uses **Liebig's Law of the Minimum** — final yield = minimum of N-yield, P-yield, K-yield across pixels. Running at multiple fertilizer levels reveals the response curve and the economically optimal input rate. Compare with Tool 5 percentiles to evaluate fertilizer efficiency.

### Network Analysis (Tool 1)
Detects community clusters in flow networks using igraph. **Walktrap** (random walks) suits dense, well-separated communities. **Spin glass** suits fuzzy, overlapping communities. Key metrics: degree (hub size), closeness centrality (network reach, ~1.0 = highly central), betweenness centrality (bridge role; 0 = peripheral leaf node).

## General Rules
- Always respond in the same language as the user
- Collect ALL required parameters before calling any tool — never guess or assume file paths
- Detailed parameter strategies are provided in the skill specifications below

## File Path Rules (CRITICAL)
- NEVER display raw file system paths (e.g. C:\\..., /home/...) to the user in your text responses
- When listing output files, mention only the filename (e.g. `aligned_lulc_2010.tif`), not the full path
- internal_path values in tool results are for your internal tool calls only — do NOT echo them to the user
- Uploaded file paths prepended to messages are for tool parameter resolution only — do NOT repeat them to the user
"""

# ---------------------------------------------------------------------------
# Tool declarations (Gemini function calling format)
# ---------------------------------------------------------------------------

TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="run_network_analysis_grouping",
            description="Run Network Analysis Grouping using R + igraph to detect community clusters in flow networks. Use when user asks about network analysis, flow network, community detection, node clustering, trade network.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "nodes_table":             types.Schema(type=types.Type.STRING, description="Path to nodes CSV file"),
                    "links_table":             types.Schema(type=types.Type.STRING, description="Path to links/edges CSV file"),
                    "shapefile_path":          types.Schema(type=types.Type.STRING, description="Path to input shapefile (.shp)"),
                    "nodes_join_attri":        types.Schema(type=types.Type.STRING, description="Column name in nodes CSV used for joining"),
                    "layer_join_attri":        types.Schema(type=types.Type.STRING, description="Column name in shapefile for joining"),
                    "clustering_algorithm":    types.Schema(type=types.Type.STRING, description="Graph clustering method: 'walktrap' or 'spin_glass'"),
                    "weight_within_clusters":  types.Schema(type=types.Type.INTEGER, description="Edge weight within same cluster, default 10"),
                    "weight_between_clusters": types.Schema(type=types.Type.INTEGER, description="Edge weight between clusters, default 2"),
                    "color_set":               types.Schema(type=types.Type.STRING, description="RColorBrewer palette name, default Set3"),
                    "node_size":               types.Schema(type=types.Type.NUMBER, description="Node size scaling, default 0.05"),
                    "edge_width":              types.Schema(type=types.Type.NUMBER, description="Edge width scaling, default 0.833333"),
                    "label_size":              types.Schema(type=types.Type.NUMBER, description="Label font size scaling, default 0.8"),
                },
                required=["nodes_table", "links_table", "shapefile_path",
                          "nodes_join_attri", "layer_join_attri", "clustering_algorithm"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_coastal_blue_carbon_preprocessor",
            description="Run InVEST Coastal Blue Carbon Preprocessor to identify LULC transitions between time periods. Use when user asks about blue carbon preprocessing, LULC transition analysis, or coastal carbon prep.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "landcover_snapshot_csv": types.Schema(type=types.Type.STRING, description="Path to CSV with columns: snapshot_year(int), raster_path(str)"),
                    "landcover_lookup_table": types.Schema(type=types.Type.STRING, description="Path to LULC lookup CSV: lucode, lulc-class, is_coastal_blue_carbon_habitat"),
                },
                required=["landcover_snapshot_csv", "landcover_lookup_table"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_coastal_blue_carbon",
            description="Run InVEST Coastal Blue Carbon main model for carbon stock, sequestration, and NPV. Use when user asks about carbon stock, carbon sequestration, coastal carbon, or net present value of carbon.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "landcover_snapshot_csv":      types.Schema(type=types.Type.STRING),
                    "landcover_transitions_table": types.Schema(type=types.Type.STRING, description="Path to MANUALLY EDITED transitions CSV from preprocessor"),
                    "biophysical_table_path":      types.Schema(type=types.Type.STRING),
                    "analysis_year":               types.Schema(type=types.Type.INTEGER),
                    "do_economic_analysis":        types.Schema(type=types.Type.BOOLEAN, description="Enable NPV calculation, default false"),
                    "discount_rate":               types.Schema(type=types.Type.NUMBER),
                    "inflation_rate":              types.Schema(type=types.Type.NUMBER),
                    "price":                       types.Schema(type=types.Type.NUMBER, description="Carbon price per ton"),
                    "use_price_table":             types.Schema(type=types.Type.BOOLEAN, description="Use price schedule CSV instead of single price"),
                    "price_table_path":            types.Schema(type=types.Type.STRING),
                },
                required=["landcover_snapshot_csv", "landcover_transitions_table", "biophysical_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_seasonal_water_yield",
            description="Run InVEST Seasonal Water Yield model to estimate quickflow, baseflow, and local recharge. Use when user asks about seasonal water yield, baseflow, quickflow, SWY, or watershed hydrology.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "aoi_path":                    types.Schema(type=types.Type.STRING, description="Path to watershed AOI shapefile"),
                    "lulc_raster_path":            types.Schema(type=types.Type.STRING),
                    "dem_raster_path":             types.Schema(type=types.Type.STRING),
                    "soil_group_path":             types.Schema(type=types.Type.STRING),
                    "biophysical_table_path":      types.Schema(type=types.Type.STRING),
                    "precip_dir":                  types.Schema(type=types.Type.STRING, description="Directory containing 12 monthly precipitation rasters"),
                    "et0_dir":                     types.Schema(type=types.Type.STRING, description="Directory containing 12 monthly ET0 rasters"),
                    "rain_events_table_path":      types.Schema(type=types.Type.STRING, description="CSV with columns: month, events"),
                    "threshold_flow_accumulation": types.Schema(type=types.Type.INTEGER, description="Flow accumulation threshold, default 1000"),
                    "alpha_m":                     types.Schema(type=types.Type.NUMBER, description="Default 0.083333"),
                    "beta_i":                      types.Schema(type=types.Type.NUMBER, description="Default 1.0"),
                    "gamma":                       types.Schema(type=types.Type.NUMBER, description="Default 1.0"),
                },
                required=["aoi_path", "lulc_raster_path", "dem_raster_path", "soil_group_path",
                          "biophysical_table_path", "precip_dir", "et0_dir",
                          "rain_events_table_path", "threshold_flow_accumulation"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_crop_production_percentile",
            description="Run InVEST Crop Production Percentile model for up to 172 crops based on climate percentiles. Use when user asks about crop yield percentile, 172 crops, or food production estimation.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "landcover_raster_path":        types.Schema(type=types.Type.STRING),
                    "landcover_to_crop_table_path": types.Schema(type=types.Type.STRING, description="CSV mapping lucode to crop_name"),
                    "aggregate_polygon_path":       types.Schema(type=types.Type.STRING, description="Optional shapefile for spatial aggregation"),
                },
                required=["landcover_raster_path", "landcover_to_crop_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_crop_production_regression",
            description="Run InVEST Crop Production Regression based on fertilizer NPK rates. Supports 10 crops: barley, maize, oil palm, potato, rice, soybean, sugar beet, sugar cane, sunflower, wheat.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "landcover_raster_path":         types.Schema(type=types.Type.STRING),
                    "landcover_to_crop_table_path":  types.Schema(type=types.Type.STRING),
                    "fertilization_rate_table_path": types.Schema(type=types.Type.STRING, description="CSV: crop_name, nitrogen_rate, phosphorus_rate, potassium_rate (kg/ha)"),
                    "aggregate_polygon_path":        types.Schema(type=types.Type.STRING, description="Optional shapefile for spatial aggregation"),
                },
                required=["landcover_raster_path", "landcover_to_crop_table_path",
                          "fertilization_rate_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="read_file_content",
            description=(
                "Read and return the content of an output file (CSV or TXT) so you can analyze, "
                "summarize, or answer questions about it. Use this whenever the user asks to "
                "summarize, analyze, explain, or ask questions about a specific output file "
                "(e.g. a network_stats CSV, a result_table CSV). "
                "Pass the full absolute internal_path of the file."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "file_path": types.Schema(
                        type=types.Type.STRING,
                        description="Absolute path to the file to read (use internal_path from previous tool results).",
                    ),
                },
                required=["file_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="render_spatial_file",
            description=(
                "Render an existing output spatial file to a PNG image using QGIS. "
                "ONLY call this tool when the user explicitly requests to visualize, render, or display "
                "a specific output file that was already produced by a previous tool run. "
                "Do NOT call this when the user is asking to run a model or upload input files — "
                "only call it after a tool has already produced output .tif or .shp files and the user "
                "specifically asks to see one of those outputs as an image. "
                "The file_path must be an absolute path to an existing file on disk."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "file_path": types.Schema(
                        type=types.Type.STRING,
                        description="Absolute path to the spatial file (.tif, .tiff, .shp, .geojson, or .gpkg) to render.",
                    ),
                },
                required=["file_path"],
            ),
        ),
    ])
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _maybe_await(result: Any) -> None:
    if asyncio.iscoroutine(result):
        await result


def _build_function_response(
    tool_name: str,
    tool_result_event: dict,
) -> tuple[str, str]:
    """
    Returns (result_summary, post_skill_text).
    result_summary goes into the function_response part.
    post_skill_text is appended as extra context for Gemini's final reply.
    """
    files = tool_result_event.get("files", [])
    content = tool_result_event.get("content", "")

    if content:
        # read_file_content returns file text for the AI to analyze
        result_summary = f"File contents:\n\n{content}"
    elif files:
        # Include internal_path for tool use (e.g. render_spatial_file), but
        # the system instruction tells Gemini never to show paths to the user.
        file_list = "\n".join(
            f"  - {f['filename']} | internal_path={f.get('path', '')} | type={f.get('render_type', 'download')}"
            for f in files
        )
        result_summary = f"Tool completed successfully. Output files:\n{file_list}"
    else:
        result_summary = "Tool completed successfully. No output files were produced."

    post_skill = _load_skill_section(tool_name, "POST_EXECUTION")
    post_skill_text = ""
    if post_skill:
        post_skill_text = (
            f"[POST-EXECUTION SKILL for {tool_name}]\n"
            f"Use the following to accurately explain the outputs, "
            f"highlight any warnings, and suggest next steps to the user.\n\n"
            f"{post_skill}"
        )

    return result_summary, post_skill_text


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

async def run_agent(
    message: str,
    session_id: str,
    files: list,
    event_callback: Callable[[dict], Any],
    model: str | None = None,
) -> None:
    """
    Main agent loop using Gemini native function calling.

    Phase 1 (PRE_EXECUTION): All skills' [PRE_EXECUTION] sections are
    appended to the system instruction before the first Gemini call.

    Phase 2 (POST_EXECUTION): After each tool completes, the specific
    skill's [POST_EXECUTION] section is injected back so Gemini can
    explain outputs and suggest next steps accurately.

    Race condition fix: Redis pubsub is subscribed BEFORE Celery dispatch
    so no progress events are missed, then tool_start is sent to frontend.
    """
    from workers.task_queue import run_tool_task

    # Map each InVEST tool to its dedicated Celery queue (concurrency=1 per queue
    # prevents GDAL/InVEST multi-process conflicts under concurrent user load).
    _TOOL_QUEUES = {
        "run_network_analysis_grouping":        "q_net",
        "run_coastal_blue_carbon_preprocessor": "q_cbc_pre",
        "run_coastal_blue_carbon":              "q_cbc_main",
        "run_seasonal_water_yield":             "q_swy",
        "run_crop_production_percentile":       "q_crop_pct",
        "run_crop_production_regression":       "q_crop_reg",
        "render_spatial_file":                  "q_render",
        "read_file_content":                    "q_render",
        "run_carbon_storage":                   "q_carbon",
        "run_habitat_quality":                  "q_habitat_quality",
        "run_annual_water_yield":               "q_awy",
        "run_forest_carbon_edge_effect":        "q_forest_carbon",
        "run_crop_pollination":                 "q_pollination",
        "run_delineateit":                      "q_delineateit",
        "run_routedem":                         "q_routedem",
        "run_sdr":                              "q_sdr",
        "run_ndr":                              "q_ndr",
        "run_urban_cooling":                    "q_urban_cooling",
        "run_urban_flood_risk_mitigation":      "q_urban_flood",
        "run_urban_stormwater_retention":       "q_urban_stormwater",
        "run_urban_nature_access":              "q_urban_nature",
        "run_urban_mental_health":              "q_urban_mental_health",
        "run_scenario_gen_proximity":           "q_scenario_gen",
    }

    client = _get_client()
    model_name = model or settings.DEFAULT_MODEL

    # Phase 1: build system instruction with PRE_EXECUTION skill sections
    pre_execution_context = _build_pre_execution_context()
    system_instruction = _BASE_SYSTEM_INSTRUCTION + pre_execution_context

    # Build initial user message (uploaded + previous output file paths prepended)
    from shared.session_manager import SessionManager as _SM
    _sm = _SM()
    context_lines = []
    if files:
        context_lines += [
            f"Uploaded file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in files
        ]
    output_files = _sm.get_output_files(session_id)
    if output_files:
        context_lines += [
            f"Previous output file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in output_files
        ]
    user_text = "\n".join(context_lines) + "\n\n" + message if context_lines else message

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
    ]

    # Agentic loop
    max_iterations = 10
    for iteration in range(max_iterations):
        logger.info(f"[agent] iteration={iteration} session={session_id} model={model_name}")

        response = await _generate_with_retry(
            client,
            model_name,
            contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=TOOLS,
                temperature=0.7,
            ),
        )

        if not response.candidates:
            logger.warning("[agent] Gemini returned no candidates, stopping")
            break

        candidate = response.candidates[0]
        if candidate.content is None or candidate.content.parts is None:
            logger.warning("[agent] Gemini returned candidate with no content/parts (safety filter or rate limit), stopping")
            break

        contents.append(candidate.content)

        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call is not None
        ]

        # Stream any text parts to frontend
        for part in candidate.content.parts:
            if part.text:
                await _maybe_await(event_callback({
                    "type": "text_chunk",
                    "content": part.text,
                }))

        if not function_calls:
            break

        function_response_parts: list[types.Part] = []

        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args)
            logger.info(f"[agent] function_call: {tool_name}")

            # ── Step 1: dispatch Celery to obtain the real task_id ──────────
            queue = _TOOL_QUEUES.get(tool_name, "q_default")
            celery_result = run_tool_task.apply_async(
                args=[tool_name, tool_input, session_id],
                queue=queue,
            )
            task_id = celery_result.id
            logger.info(f"[agent] Celery task dispatched: {task_id}")

            # ── Step 2: subscribe Redis BEFORE any worker events arrive ─────
            r_sub = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = r_sub.pubsub()
            await pubsub.subscribe(f"progress:{session_id}:{task_id}")

            # ── Step 3: notify frontend (agent's own tool_start with real id)
            await _maybe_await(event_callback({
                "type": "tool_start",
                "tool": tool_name,
                "message": f"Starting {tool_name}...",
                "task_id": task_id,
            }))

            try:
                # ── Step 4: relay worker events until done/error ─────────────
                loop = asyncio.get_running_loop()
                tool_result_event: dict = {}
                deadline = loop.time() + 1800.0

                async for raw_msg in pubsub.listen():
                    if loop.time() > deadline:
                        raise TimeoutError(f"Tool {task_id} timed out after 1800s")
                    if raw_msg["type"] != "message":
                        continue
                    try:
                        event = json.loads(raw_msg["data"])
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    # Skip worker's tool_start — agent already sent one above
                    if event_type == "tool_start":
                        continue

                    await _maybe_await(event_callback(event))

                    if event_type == "tool_result":
                        tool_result_event = event
                    elif event_type == "done":
                        break
                    elif event_type == "error":
                        raise RuntimeError(event.get("message", "Tool execution failed"))

                await pubsub.unsubscribe(f"progress:{session_id}:{task_id}")

                # ── Step 5: build Gemini function_response + POST_EXECUTION ──
                result_summary, post_skill_text = _build_function_response(
                    tool_name, tool_result_event
                )
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": result_summary},
                    )
                )
                if post_skill_text:
                    function_response_parts.append(
                        types.Part.from_text(text=post_skill_text)
                    )

            except Exception as exc:
                logger.exception(f"[agent] Tool {tool_name} failed: {exc}")
                await _maybe_await(event_callback({
                    "type": "error",
                    "message": str(exc),
                    "error_code": "TOOL_FAILED",
                }))
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"error": str(exc)},
                    )
                )
            finally:
                await r_sub.aclose()

        # Feed all function responses back to Gemini for final reply
        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

    await _maybe_await(event_callback({"type": "done"}))
