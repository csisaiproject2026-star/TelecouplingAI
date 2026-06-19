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
from shared.utils import sanitize_error_message, validate_file_params_exist, validate_input_files, CSISError
from shared.tool_file_specs import TOOL_FILE_SPECS

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


class _StreamedResponse:
    """Minimal stand-in for a GenerateContentResponse, assembled from a stream so
    the rest of run_agent (function-call extraction, history append, empty-recovery)
    works unchanged. content.parts is None when nothing usable streamed."""
    def __init__(self, content):
        self.candidates = [types.Candidate(content=content)]


async def _generate_streaming(client, model_name: str, contents, config, emit,
                              max_retries: int = 4):
    """Like _generate_with_retry but STREAMS: emits `thinking`/`text_chunk` events
    live as deltas arrive (so the UI's thinking block grows in real time), then
    returns the fully assembled response. Falls back through the same 429/503 retry."""
    import random, inspect
    for attempt in range(max_retries):
        async with _GEMINI_SEMAPHORE:
            try:
                collected = []
                maybe = client.aio.models.generate_content_stream(
                    model=model_name, contents=contents, config=config,
                )
                stream = await maybe if inspect.isawaitable(maybe) else maybe
                async for chunk in stream:
                    cand = chunk.candidates[0] if getattr(chunk, "candidates", None) else None
                    if not cand or cand.content is None or not cand.content.parts:
                        continue
                    for part in cand.content.parts:
                        if part.function_call is not None:
                            collected.append(part)
                        elif part.text:
                            if getattr(part, "thought", False):
                                await _maybe_await(emit({"type": "thinking", "content": part.text}))
                            else:
                                await _maybe_await(emit({"type": "text_chunk", "content": part.text}))
                            collected.append(part)
                content = (types.Content(role="model", parts=collected)
                           if collected else types.Content(role="model"))
                return _StreamedResponse(content)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str
                is_server_err = "503" in err_str or "unavailable" in err_str
                if (is_rate_limit or is_server_err) and attempt < max_retries - 1:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"[agent] Gemini stream {'rate limit' if is_rate_limit else 'server error'} "
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
    "run_carbon_storage":                     "run-carbon-storage",
    "run_habitat_quality":                    "run-habitat-quality",
    "run_annual_water_yield":                 "run-annual-water-yield",
    "run_forest_carbon_edge_effect":          "run-forest-carbon-edge",
    "run_crop_pollination":                   "run-crop-pollination",
    "run_delineateit":                        "run-delineateit",
    "run_routedem":                           "run-routedem",
    "run_Sediment_Delivery_Ratio_SDR":        "run-sdr",
    "run_ndr":                                "run-ndr",
    "run_urban_cooling":                      "run-urban-cooling",
    "run_urban_flood_risk_mitigation":        "run-urban-flood",
    "run_urban_stormwater_retention":         "run-urban-stormwater",
    "run_urban_nature_access":                "run-urban-nature-access",
    "run_urban_mental_health":                "run-urban-mental-health",
    "run_scenic_quality":                     "run-scenic-quality",
    "run_habitat_risk_assessment":            "run-habitat-risk-assessment",
    "run_wave_energy_production":             "run-wave-energy-production",
    "run_scenario_gen_proximity":             "run-scenario-gen-proximity",
    "run_coastal_vulnerability":              "run-coastal-vulnerability",
    "run_offshore_wind_energy":               "run-offshore-wind-energy",
    "run_model_selection_ols":               "run-model-selection-ols",
    "run_factor_analysis_mixed_data":        "run-famd",
    "run_co2_emissions":                     "run-co2-emissions",
    "run_cost_benefit_analysis":             "run-cost-benefit-analysis",
    "run_population_count_density":          "run-population-density",
    "run_draw_radial_flows":                 "run-radial-flows",
    "run_commodity_trade":                   "run-commodity-trade",
    "run_add_agents_interactively":          "run-add-agents",
    "run_draw_agents_from_table":            "run-draw-agents-table",
    "run_add_causes_interactively":          "run-add-causes",
    "run_add_systems_interactively":         "run-add-systems",
    "run_draw_systems_from_table":           "run-draw-systems-table",
    "run_add_media_flows":                   "run-add-media-flows",
    "run_food_security":                     "run-food-security",
    "run_nutrition_metrics":                 "run-nutrition-metrics",
    "run_geographical_detector":             "run-geographical-detector",
    "run_spatial_autocorrelation_moran":     "run-spatial-moran",
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

## Available Tools Overview

When a user asks you to list all supported tools, respond with the exact markdown list below. Copy it verbatim — do NOT rephrase, reorder, or add function call names (run_xxx). Always start the list on a new paragraph (blank line before the first section header).

**InVEST Ecosystem Services Tools**
- **Network Analysis Grouping**: Performs network/flow analysis using R + igraph for community detection and clustering.
- **Coastal Blue Carbon Preprocessor**: Preprocesses LULC transitions for blue carbon modeling.
- **Coastal Blue Carbon**: Analyzes carbon stock, sequestration, and Net Present Value (NPV) for coastal blue carbon habitats.
- **Seasonal Water Yield**: Models quickflow, baseflow, and local recharge in watersheds.
- **Crop Production Percentile**: Estimates crop yield for 172 crops based on climate percentiles.
- **Crop Production Regression**: Estimates crop yield for 10 staple crops based on fertilizer NPK rates.
- **Carbon Storage**: Estimates carbon stocks and sequestration based on LULC.
- **Habitat Quality**: Maps habitat degradation and quality from human threats.
- **Annual Water Yield**: Estimates annual water yield using the Budyko curve.
- **Forest Carbon Edge Effect**: Estimates above-ground carbon in tropical forests, accounting for edge effects.
- **Crop Pollination**: Models wild bee pollination services on farms.
- **DelineateIt**: Delineates watersheds from a Digital Elevation Model (DEM) and outlet points.
- **RouteDEM**: Computes flow direction, flow accumulation, streams, and slope from a DEM.
- **Sediment Delivery Ratio (SDR)**: Estimates soil erosion and sediment export.
- **Nutrient Delivery Ratio (NDR)**: Estimates nitrogen and phosphorus export from watersheds.
- **Urban Cooling Island**: Estimates urban heat mitigation from green spaces.
- **Urban Flood Risk Mitigation**: Estimates stormwater runoff and flood risk using curve numbers.
- **Urban Stormwater Retention**: Estimates runoff retention and recharge in urban areas.
- **Urban Nature Access**: Estimates population access to urban green space.
- **Urban Mental Health**: Estimates mental health benefits from urban green space.
- **Scenic Quality**: Computes viewshed visibility from structure points.
- **Habitat Risk Assessment (HRA)**: Evaluates cumulative risk to habitats from multiple stressors.
- **Wave Energy Production**: Estimates ocean wave energy potential.
- **Scenario Generator - Proximity-Based**: Generates LULC conversion scenarios based on proximity.
- **Coastal Vulnerability**: Assesses shoreline exposure and risk from waves, wind, and sea level.
- **Offshore Wind Energy**: Estimates offshore wind power potential.

**Telecoupling Toolbox**
- **Model Selection OLS**: Runs Ordinary Least Squares (OLS) regression with automated model selection.
- **Factor Analysis Mixed Data (FAMD)**: Performs PCA, MCA, or FAMD for dimensionality reduction.
- **CO2 Emissions**: Calculates CO2 emissions from transport routes.
- **Cost-Benefit Analysis**: Joins economic data and computes net returns.
- **Population Count Density**: Calculates population density and change.
- **Draw Radial Flows**: Generates radial flow lines from origin-destination coordinates.
- **Commodity Trade**: Maps bilateral commodity trade flows between countries.
- **Add Agents Interactively**: Creates point features for telecoupling agents from a CSV.
- **Draw Agents from Table**: Renders agent point features from an uploaded coordinate table.
- **Add Causes Interactively**: Creates point features for telecoupling causes from a CSV.
- **Add Systems Interactively**: Creates point features for telecoupling systems from a CSV.
- **Draw Systems from Table**: Renders system point features from an uploaded coordinate table.
- **Add Media Flows**: Parses HTML for country mentions and generates media flow lines.
- **Food Security**: Analyzes FAO food security indicators and generates trend charts.
- **Nutrition Metrics**: Calculates Lower Limit Energy Requirements (LLER) by age group and sex.

**Utility Tools**
- **Read File Content**: Reads and returns the content of an output file (CSV or TXT) to answer user questions.
- **Render Spatial File**: Renders a spatial output file (TIF, SHP) to a map image.

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

## Handling Incomplete Parameters (Multi-turn Collection)
Users often provide parameters across multiple messages. Follow this pattern:

1. If the user requests a tool but some required parameters are missing, DO NOT call the tool yet.
   Instead, reply with a friendly message listing exactly which parameters are still needed.
   Example format:
   "To run [Tool Name], I still need the following:
   - `param_name_1`: [brief description of what it is]
   - `param_name_2`: [brief description]
   Please provide these and I'll run the model right away."

2. Once the user replies with the missing information, combine it with what was provided earlier
   (visible in the conversation history) and call the tool.

3. Never ask for parameters that were already provided in earlier messages — check the full
   conversation history before asking.

4. If the user provides a file by uploading it (path listed at top of message), treat that as
   satisfying the corresponding parameter — do not ask for it again.

## File Path Rules (CRITICAL)
- NEVER display raw file system paths (e.g. C:\\..., /home/...) to the user in your text responses
- When listing output files, mention only the filename (e.g. `aligned_lulc_2010.tif`), not the full path
- internal_path values in tool results are for your internal tool calls only — do NOT echo them to the user
- Uploaded file paths prepended to messages are for tool parameter resolution only — do NOT repeat them to the user

## Image / Map Output Rules (CRITICAL)
- NEVER write inline image data in your text response. Specifically: do NOT emit `![...](data:image/png;base64,...)`, do NOT emit any `data:image/*;base64,...` URLs, and do NOT emit fake/fabricated base64 byte strings.
- The ONLY way to show a rendered map or image is to call the `render_spatial_file` tool. The frontend will display the resulting PNG automatically — you do not need to embed it in your reply.
- NEVER claim, state, or imply that you rendered/showed/displayed a map or image (e.g. "Here is the rendered map", "the image is shown above", "you can download this image") UNLESS you actually called `render_spatial_file` for that exact file. Describing or announcing a render you did not perform is a hard error — it produces NO image for the user.
- When the user asks to show / render / display / visualize / 可视化 a specific .tif or .shp file, you MUST call `render_spatial_file` on that file. Never answer with text alone claiming it is done.
- The ONLY exception to calling `render_spatial_file` again: if you yourself called it for the SAME file in the IMMEDIATELY preceding turn of THIS conversation, you may say it is already shown above. In every other case — including when an older render exists earlier in the history — you MUST call `render_spatial_file` again.
- You cannot draw images yourself. If asked to "show a map" or "visualize" and you have not rendered that file this turn, call `render_spatial_file` on the relevant .tif / .shp file.
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
        # ── 20 additional InVEST tools ─────────────────────────────────────────
        types.FunctionDeclaration(
            name="run_carbon_storage",
            description="Run InVEST Carbon Storage and Sequestration. Use when user asks about carbon stocks, LULC carbon pools, carbon sequestration, REDD, or valuation of carbon storage.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_cur_path":         types.Schema(type=types.Type.STRING, description="Path to current LULC raster"),
                    "carbon_pools_path":     types.Schema(type=types.Type.STRING, description="CSV with columns: lucode, C_above, C_below, C_soil, C_dead"),
                    "lulc_fut_path":         types.Schema(type=types.Type.STRING, description="Future LULC raster (for sequestration)"),
                    "lulc_redd_path":        types.Schema(type=types.Type.STRING, description="REDD scenario LULC raster"),
                    "do_valuation":          types.Schema(type=types.Type.BOOLEAN, description="Enable economic valuation, default false"),
                    "price_per_metric_ton_of_c": types.Schema(type=types.Type.NUMBER),
                    "discount_rate":         types.Schema(type=types.Type.NUMBER),
                    "rate_change":           types.Schema(type=types.Type.NUMBER),
                    "lulc_cur_year":         types.Schema(type=types.Type.INTEGER),
                    "lulc_fut_year":         types.Schema(type=types.Type.INTEGER),
                },
                required=["lulc_cur_path", "carbon_pools_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_habitat_quality",
            description="Run InVEST Habitat Quality to map habitat degradation and quality from threats. Use when user asks about habitat quality, biodiversity, threat analysis, or degradation index.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_cur_path":           types.Schema(type=types.Type.STRING, description="Current LULC raster"),
                    "threats_table_path":      types.Schema(type=types.Type.STRING, description="CSV describing threats: threat, max_dist, weight, decay"),
                    "sensitivity_table_path":  types.Schema(type=types.Type.STRING, description="CSV with columns: lulc, habitat, plus one column per threat"),
                    "lulc_fut_path":           types.Schema(type=types.Type.STRING, description="Future LULC raster"),
                    "lulc_bas_path":           types.Schema(type=types.Type.STRING, description="Baseline LULC raster"),
                    "access_vector_path":      types.Schema(type=types.Type.STRING, description="Shapefile of protection/access areas"),
                    "half_saturation_constant": types.Schema(type=types.Type.NUMBER, description="Half-saturation constant k, default 0.5"),
                },
                required=["lulc_cur_path", "threats_table_path", "sensitivity_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_annual_water_yield",
            description="Run InVEST Annual Water Yield (Budyko curve) to estimate water yield per watershed. Use when user asks about annual water yield, AWY, Budyko, water supply, or watershed water balance.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_path":                    types.Schema(type=types.Type.STRING),
                    "eto_path":                     types.Schema(type=types.Type.STRING, description="Reference evapotranspiration raster"),
                    "precipitation_path":           types.Schema(type=types.Type.STRING),
                    "depth_to_root_rest_layer_path": types.Schema(type=types.Type.STRING, description="Depth-to-root-restricting-layer raster (mm)"),
                    "pawc_path":                    types.Schema(type=types.Type.STRING, description="Plant available water content raster"),
                    "biophysical_table_path":       types.Schema(type=types.Type.STRING),
                    "watersheds_path":              types.Schema(type=types.Type.STRING),
                    "sub_watersheds_path":          types.Schema(type=types.Type.STRING),
                    "seasonality_constant":         types.Schema(type=types.Type.NUMBER, description="Zhang seasonality constant, default 15"),
                    "demand_table_path":            types.Schema(type=types.Type.STRING),
                    "valuation_table_path":         types.Schema(type=types.Type.STRING),
                },
                required=["lulc_path", "eto_path", "precipitation_path",
                          "depth_to_root_rest_layer_path", "pawc_path",
                          "biophysical_table_path", "watersheds_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_forest_carbon_edge_effect",
            description="Run InVEST Forest Carbon Edge Effect to estimate above-ground carbon in tropical forests accounting for edge effects. Use when user asks about forest carbon, tropical carbon, edge effect, or above-ground biomass.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_raster_path":           types.Schema(type=types.Type.STRING),
                    "biophysical_table_path":     types.Schema(type=types.Type.STRING),
                    "tropical_forest_edge_carbon_model_vector_path": types.Schema(type=types.Type.STRING, description="Carbon model vector from InVEST data"),
                    "aoi_vector_path":            types.Schema(type=types.Type.STRING),
                    "pools_to_calculate":         types.Schema(type=types.Type.STRING, description="'all' or 'above_ground', default 'all'"),
                    "compute_forest_edge_effects": types.Schema(type=types.Type.BOOLEAN, description="Default true"),
                    "n_nearest_model_points":     types.Schema(type=types.Type.INTEGER, description="Default 10"),
                    "biomass_to_carbon_conversion_factor": types.Schema(type=types.Type.NUMBER, description="Default 0.47"),
                },
                required=["lulc_raster_path", "biophysical_table_path",
                          "tropical_forest_edge_carbon_model_vector_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_crop_pollination",
            description="Run InVEST Pollination model to estimate wild bee pollination services on farms. Use when user asks about pollination, pollinators, bees, farm pollination, or crop pollination services.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "landcover_raster_path":           types.Schema(type=types.Type.STRING),
                    "guild_table_path":                types.Schema(type=types.Type.STRING, description="CSV describing pollinator species: species, nesting, foraging columns"),
                    "landcover_biophysical_table_path": types.Schema(type=types.Type.STRING, description="CSV: lucode + nesting/foraging suitability columns per species"),
                    "farm_vector_path":                types.Schema(type=types.Type.STRING, description="Shapefile of farm polygons"),
                },
                required=["landcover_raster_path", "guild_table_path", "landcover_biophysical_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_delineateit",
            description="Run InVEST DelineateIt to delineate watersheds from a DEM and outlet points. Use when user asks about watershed delineation, catchment boundaries, or outlet snapping.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "dem_path":             types.Schema(type=types.Type.STRING, description="Digital elevation model raster"),
                    "outlet_vector_path":   types.Schema(type=types.Type.STRING, description="Shapefile of outlet/pour points"),
                    "detect_pour_points":   types.Schema(type=types.Type.BOOLEAN, description="Auto-detect pour points from DEM, default false"),
                    "snap_points":          types.Schema(type=types.Type.BOOLEAN, description="Snap outlets to nearest stream, default false"),
                    "flow_threshold":       types.Schema(type=types.Type.INTEGER, description="Flow accumulation threshold for snapping, default 1000"),
                    "snap_distance":        types.Schema(type=types.Type.INTEGER, description="Max snap distance in pixels, default 20"),
                },
                required=["dem_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_routedem",
            description="Run InVEST RouteDEM to compute flow direction, flow accumulation, streams, and slope from a DEM. Use when user asks about flow direction, flow accumulation, stream extraction, or DEM routing.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "dem_path":                      types.Schema(type=types.Type.STRING),
                    "algorithm":                     types.Schema(type=types.Type.STRING, description="'D8' or 'MFD', default 'D8'"),
                    "calculate_flow_direction":      types.Schema(type=types.Type.BOOLEAN, description="Default true"),
                    "calculate_flow_accumulation":   types.Schema(type=types.Type.BOOLEAN, description="Default true"),
                    "calculate_stream_threshold":    types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                    "threshold_flow_accumulation":   types.Schema(type=types.Type.INTEGER, description="Required if calculate_stream_threshold=true"),
                    "calculate_slope":               types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                    "calculate_stream_order":        types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                    "calculate_downstream_distance": types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                },
                required=["dem_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_Sediment_Delivery_Ratio_SDR",
            description="Run InVEST Sediment Delivery Ratio (SDR) to estimate soil erosion and sediment export. Use when user asks about SDR, sediment delivery, erosion, RUSLE, or soil retention.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "dem_path":                    types.Schema(type=types.Type.STRING),
                    "erosivity_path":              types.Schema(type=types.Type.STRING, description="Rainfall erosivity raster (R factor)"),
                    "erodibility_path":            types.Schema(type=types.Type.STRING, description="Soil erodibility raster (K factor)"),
                    "lulc_path":                   types.Schema(type=types.Type.STRING),
                    "watersheds_path":             types.Schema(type=types.Type.STRING),
                    "biophysical_table_path":      types.Schema(type=types.Type.STRING, description="CSV with usle_c, usle_p per lucode"),
                    "threshold_flow_accumulation": types.Schema(type=types.Type.INTEGER, description="Flow accumulation threshold, default 1000"),
                    "k_param":                     types.Schema(type=types.Type.NUMBER, description="Borselli K parameter, default 2"),
                    "sdr_max":                     types.Schema(type=types.Type.NUMBER, description="Max SDR value, default 0.8"),
                    "ic_0_param":                  types.Schema(type=types.Type.NUMBER, description="Borselli IC0, default 0.5"),
                    "l_max":                       types.Schema(type=types.Type.NUMBER, description="Max slope length, default 122"),
                    "drainage_path":               types.Schema(type=types.Type.STRING, description="Optional drainage channel raster"),
                },
                required=["dem_path", "erosivity_path", "erodibility_path", "lulc_path",
                          "watersheds_path", "biophysical_table_path", "threshold_flow_accumulation"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_ndr",
            description="Run InVEST Nutrient Delivery Ratio (NDR) to estimate nitrogen and phosphorus export from watersheds. Use when user asks about NDR, nutrient delivery, nitrogen export, phosphorus, or water quality nutrients.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "dem_path":                    types.Schema(type=types.Type.STRING),
                    "lulc_path":                   types.Schema(type=types.Type.STRING),
                    "runoff_proxy_path":           types.Schema(type=types.Type.STRING, description="Runoff proxy raster (e.g. precipitation)"),
                    "watersheds_path":             types.Schema(type=types.Type.STRING),
                    "biophysical_table_path":      types.Schema(type=types.Type.STRING),
                    "threshold_flow_accumulation": types.Schema(type=types.Type.INTEGER, description="Default 1000"),
                    "k_param":                     types.Schema(type=types.Type.NUMBER, description="Default 2"),
                    "calc_n":                      types.Schema(type=types.Type.BOOLEAN, description="Calculate nitrogen, default true"),
                    "calc_p":                      types.Schema(type=types.Type.BOOLEAN, description="Calculate phosphorus, default false"),
                    "subsurface_critical_length_n": types.Schema(type=types.Type.INTEGER, description="Default 150"),
                    "subsurface_eff_n":            types.Schema(type=types.Type.NUMBER, description="Default 0.8"),
                    "subsurface_critical_length_p": types.Schema(type=types.Type.INTEGER),
                    "subsurface_eff_p":            types.Schema(type=types.Type.NUMBER),
                },
                required=["dem_path", "lulc_path", "runoff_proxy_path", "watersheds_path",
                          "biophysical_table_path", "threshold_flow_accumulation"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_urban_cooling",
            description="Run InVEST Urban Cooling Island model to estimate urban heat mitigation from green spaces. Use when user asks about urban heat island, cooling effect, urban green space, UHI, or city temperature.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_raster_path":           types.Schema(type=types.Type.STRING),
                    "ref_eto_raster_path":        types.Schema(type=types.Type.STRING, description="Reference ET0 raster"),
                    "aoi_vector_path":            types.Schema(type=types.Type.STRING, description="AOI polygon shapefile"),
                    "biophysical_table_path":     types.Schema(type=types.Type.STRING, description="CSV with Kc, albedo, green_area columns"),
                    "t_ref":                      types.Schema(type=types.Type.NUMBER, description="Reference air temperature (°C) in rural area"),
                    "uhi_max":                    types.Schema(type=types.Type.NUMBER, description="Maximum UHI effect (°C)"),
                    "green_area_cooling_distance": types.Schema(type=types.Type.NUMBER, description="Distance (m) over which green areas cool surroundings, default 100"),
                    "t_air_average_radius":       types.Schema(type=types.Type.INTEGER, description="Radius (m) to average air temperature, default 2000"),
                    "cc_method":                  types.Schema(type=types.Type.STRING, description="'factors' (default) or 'intensity'"),
                    "avg_rel_humidity":           types.Schema(type=types.Type.INTEGER, description="Average relative humidity %, default 30"),
                    "building_vector_path":       types.Schema(type=types.Type.STRING),
                    "energy_consumption_table_path": types.Schema(type=types.Type.STRING),
                },
                required=["lulc_raster_path", "ref_eto_raster_path", "aoi_vector_path",
                          "biophysical_table_path", "t_ref", "uhi_max", "green_area_cooling_distance"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_urban_flood_risk_mitigation",
            description="Run InVEST Urban Flood Risk Mitigation to estimate stormwater runoff and flood risk using curve numbers. Use when user asks about urban flood, stormwater runoff, curve number, SCS-CN, or flood mitigation.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "aoi_watersheds_path":             types.Schema(type=types.Type.STRING, description="AOI/watershed shapefile"),
                    "rainfall_depth":                  types.Schema(type=types.Type.NUMBER, description="Rainfall depth (mm)"),
                    "lulc_path":                       types.Schema(type=types.Type.STRING),
                    "soils_hydrological_group_raster_path": types.Schema(type=types.Type.STRING, description="Hydrological soil group raster (values 1-4 for A-D)"),
                    "curve_number_table_path":         types.Schema(type=types.Type.STRING, description="CSV with lucode and curve number columns for soil groups A-D"),
                    "built_infrastructure_vector_path": types.Schema(type=types.Type.STRING),
                    "infrastructure_damage_loss_table_path": types.Schema(type=types.Type.STRING),
                },
                required=["aoi_watersheds_path", "rainfall_depth", "lulc_path",
                          "soils_hydrological_group_raster_path", "curve_number_table_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_urban_stormwater_retention",
            description="Run InVEST Urban Stormwater Retention model to estimate runoff retention and recharge. Use when user asks about urban stormwater retention, infiltration, pervious surfaces, or retention ratios.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_path":               types.Schema(type=types.Type.STRING),
                    "soil_group_path":         types.Schema(type=types.Type.STRING, description="Hydrological soil group raster"),
                    "precipitation_path":      types.Schema(type=types.Type.STRING, description="Annual precipitation raster (mm)"),
                    "biophysical_table":       types.Schema(type=types.Type.STRING, description="CSV with lucode, EMC_*, RC_* columns"),
                    "adjust_retention_ratios": types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                    "retention_radius":        types.Schema(type=types.Type.NUMBER, description="Required if adjust_retention_ratios=true"),
                    "road_centerlines_path":   types.Schema(type=types.Type.STRING),
                    "aggregate_areas_path":    types.Schema(type=types.Type.STRING),
                    "replacement_cost":        types.Schema(type=types.Type.STRING),
                },
                required=["lulc_path", "soil_group_path", "precipitation_path", "biophysical_table"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_urban_nature_access",
            description="Run InVEST Urban Nature Access to estimate population access to urban green space. Use when user asks about urban nature access, urban green equity, greenspace accessibility, or UNA.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_raster_path":         types.Schema(type=types.Type.STRING),
                    "lulc_attribute_table":     types.Schema(type=types.Type.STRING, description="CSV mapping lucode to is_green_space and other attrs"),
                    "population_raster_path":   types.Schema(type=types.Type.STRING),
                    "admin_boundaries_vector_path": types.Schema(type=types.Type.STRING, description="Administrative boundary polygons"),
                    "search_radius_mode":       types.Schema(type=types.Type.STRING, description="'uniform radius' (default) | 'radius per population group' | 'radius per urban nature class'"),
                    "decay_function":           types.Schema(type=types.Type.STRING, description="'gaussian' (default) | 'exponential' | 'linear' | 'power' | 'uniform'"),
                    "search_radius":            types.Schema(type=types.Type.INTEGER, description="Radius in meters (required for uniform radius mode)"),
                    "population_group_radii_table": types.Schema(type=types.Type.STRING),
                },
                required=["lulc_raster_path", "lulc_attribute_table",
                          "population_raster_path", "admin_boundaries_vector_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_urban_mental_health",
            description="Run Urban Mental Health model (extended Urban Nature Access) to estimate mental health benefits from urban greenspace. Use when user asks about mental health, urban mental wellness, greenspace benefits, or psychological well-being.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "lulc_raster_path":         types.Schema(type=types.Type.STRING),
                    "lulc_attribute_table":     types.Schema(type=types.Type.STRING),
                    "population_raster_path":   types.Schema(type=types.Type.STRING),
                    "admin_boundaries_vector_path": types.Schema(type=types.Type.STRING),
                    "search_radius_mode":       types.Schema(type=types.Type.STRING, description="'uniform radius' (default)"),
                    "decay_function":           types.Schema(type=types.Type.STRING, description="'gaussian' (default)"),
                    "search_radius":            types.Schema(type=types.Type.INTEGER, description="Default 300 m"),
                    "population_group_radii_table": types.Schema(type=types.Type.STRING),
                },
                required=["lulc_raster_path", "lulc_attribute_table",
                          "population_raster_path", "admin_boundaries_vector_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_scenic_quality",
            description="Run InVEST Scenic Quality to compute viewshed visibility from structure points. Use when user asks about scenic quality, viewshed, visual impact, sight lines, or landscape aesthetics.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "aoi_vector_path":           types.Schema(type=types.Type.STRING, description="Area of interest polygon"),
                    "structure_vector_path":     types.Schema(type=types.Type.STRING, description="Shapefile of structures/viewpoints"),
                    "dem_path":                  types.Schema(type=types.Type.STRING, description="Digital elevation model"),
                    "refractivity_coefficient":  types.Schema(type=types.Type.NUMBER, description="Atmospheric refraction coefficient, default 0.13"),
                    "do_valuation":              types.Schema(type=types.Type.BOOLEAN, description="Enable valuation, default false"),
                    "valuation_function":        types.Schema(type=types.Type.STRING, description="'linear' | 'logarithmic' | 'exponential' (required if do_valuation=true)"),
                    "a_coef":                    types.Schema(type=types.Type.NUMBER),
                    "b_coef":                    types.Schema(type=types.Type.NUMBER),
                    "max_valuation_radius":      types.Schema(type=types.Type.STRING),
                },
                required=["aoi_vector_path", "structure_vector_path", "dem_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_habitat_risk_assessment",
            description="Run InVEST Habitat Risk Assessment (HRA) to evaluate cumulative risk to habitats from multiple stressors. Use when user asks about habitat risk, HRA, stressor impact, cumulative impact, or marine risk assessment.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "info_table_path":          types.Schema(type=types.Type.STRING, description="CSV listing habitats and stressors with file paths"),
                    "criteria_table_path":      types.Schema(type=types.Type.STRING, description="CSV/Excel with ratings for each habitat-stressor pair"),
                    "resolution":               types.Schema(type=types.Type.INTEGER, description="Output raster resolution in meters"),
                    "max_rating":               types.Schema(type=types.Type.INTEGER, description="Maximum rating value used in criteria table (e.g. 3)"),
                    "risk_eq":                  types.Schema(type=types.Type.STRING, description="'Euclidean' or 'Multiplicative'"),
                    "decay_eq":                 types.Schema(type=types.Type.STRING, description="'exponential', 'linear', or 'none'"),
                    "n_overlapping_stressors":  types.Schema(type=types.Type.INTEGER, description="Number of stressors overlapping at once to normalize risk"),
                    "aoi_vector_path":          types.Schema(type=types.Type.STRING, description="AOI polygon shapefile"),
                    "visualize_outputs":        types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                },
                required=["info_table_path", "criteria_table_path", "resolution",
                          "max_rating", "risk_eq", "decay_eq",
                          "n_overlapping_stressors", "aoi_vector_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_wave_energy_production",
            description="Run InVEST Wave Energy Production to estimate wave energy potential. Use when user asks about wave energy, offshore wave power, wave resource assessment, or marine renewable energy. ONLY analysis_area, machine_perf_path and machine_param_path are required; every other parameter is optional with a server default. Once those three are available, call the tool immediately — do NOT ask the user for any optional parameter (number_of_machines, wave_base_data_path, bathymetry_path, aoi_vector_path, etc.).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "wave_base_data_path":  types.Schema(type=types.Type.STRING, description="Optional. Path to InVEST wave base data directory. Omit it to use the server's built-in default WaveData (the user does not need to upload or know this path)."),
                    "analysis_area":        types.Schema(type=types.Type.STRING, description="One of: 'Australia', 'East Coast of North America and Puerto Rico', 'Global', 'North Sea 10 meter resolution', 'North Sea 4 meter resolution', 'West Coast of North America and Hawaii'"),
                    "machine_perf_path":    types.Schema(type=types.Type.STRING, description="Wave energy machine performance CSV"),
                    "machine_param_path":   types.Schema(type=types.Type.STRING, description="Wave energy machine parameters CSV"),
                    "bathymetry_path":      types.Schema(type=types.Type.STRING, description="Optional. Bathymetry raster (DEM). Omit it to use the server's built-in default global DEM (the user does not need to upload or know this path)."),
                    "aoi_vector_path":      types.Schema(type=types.Type.STRING),
                    "do_valuation":         types.Schema(type=types.Type.BOOLEAN, description="Default false"),
                    "grid_points_path":     types.Schema(type=types.Type.STRING, description="Required if do_valuation=true"),
                    "machine_econ_path":    types.Schema(type=types.Type.STRING, description="Required if do_valuation=true"),
                    "number_of_machines":   types.Schema(type=types.Type.INTEGER, description="Optional, default 28. Only used when do_valuation=true. Do NOT ask the user for this — omit it and call the tool."),
                },
                required=["analysis_area", "machine_perf_path", "machine_param_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_scenario_gen_proximity",
            description="Run InVEST Scenario Generator: Proximity-Based to generate LULC conversion scenarios. Use when user asks about scenario generation, LULC conversion, proximity-based scenarios, or land use change scenarios.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "base_lulc_path":              types.Schema(type=types.Type.STRING, description="Base LULC raster to convert"),
                    "replacement_lucode":          types.Schema(type=types.Type.INTEGER, description="LULC code to convert pixels to"),
                    "area_to_convert":             types.Schema(type=types.Type.NUMBER, description="Area (ha) to convert"),
                    "focal_landcover_codes":       types.Schema(type=types.Type.STRING, description="Space-separated LULC codes to measure distance from, e.g. '1 2 3'. Accepts one or many codes."),
                    "convertible_landcover_codes": types.Schema(type=types.Type.STRING, description="Space-separated LULC codes eligible for conversion, e.g. '1 2 3'. Accepts one or many codes."),
                    "convert_nearest_to_edge":     types.Schema(type=types.Type.BOOLEAN, description="Convert pixels nearest to focal LULC, default true"),
                    "convert_farthest_from_edge":  types.Schema(type=types.Type.BOOLEAN, description="Convert pixels farthest from focal LULC, default false"),
                    "aoi_path":                    types.Schema(type=types.Type.STRING),
                    "n_steps":                     types.Schema(type=types.Type.INTEGER, description="Number of conversion steps, default 1"),
                },
                required=["base_lulc_path", "replacement_lucode", "area_to_convert",
                          "focal_landcover_codes", "convertible_landcover_codes"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_coastal_vulnerability",
            description="Run InVEST Coastal Vulnerability to assess shoreline exposure and risk from waves, wind, and sea level. Use when user asks about coastal vulnerability, shoreline risk, CV index, coastal exposure, or coastal hazard.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "aoi_vector_path":          types.Schema(type=types.Type.STRING, description="AOI polygon shapefile"),
                    "bathymetry_raster_path":   types.Schema(type=types.Type.STRING),
                    "dem_path":                 types.Schema(type=types.Type.STRING),
                    "geomorphology_vector_path": types.Schema(type=types.Type.STRING, description="Shoreline geomorphology shapefile"),
                    "geomorphology_fill_value": types.Schema(type=types.Type.INTEGER, description="Fill value for geomorphology rank"),
                    "landmass_vector_path":     types.Schema(type=types.Type.STRING, description="Global landmass polygon shapefile"),
                    "wwiii_vector_path":        types.Schema(type=types.Type.STRING, description="WAVEWATCH III wave data shapefile"),
                    "model_resolution":         types.Schema(type=types.Type.INTEGER, description="Resolution of model in meters"),
                    "max_fetch_distance":       types.Schema(type=types.Type.INTEGER, description="Maximum fetch distance (m), default 12000"),
                    "dem_averaging_radius":     types.Schema(type=types.Type.INTEGER, description="DEM averaging radius in meters"),
                    "habitat_table_path":       types.Schema(type=types.Type.STRING),
                    "population_raster_path":   types.Schema(type=types.Type.STRING),
                    "shelf_contour_vector_path": types.Schema(type=types.Type.STRING),
                    "slr_vector_path":          types.Schema(type=types.Type.STRING),
                    "slr_field":                types.Schema(type=types.Type.STRING),
                },
                required=["aoi_vector_path", "bathymetry_raster_path", "dem_path",
                          "geomorphology_vector_path", "geomorphology_fill_value",
                          "landmass_vector_path", "wwiii_vector_path",
                          "model_resolution", "max_fetch_distance", "dem_averaging_radius"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_offshore_wind_energy",
            description="Run InVEST Offshore Wind Energy to estimate offshore wind power potential. Use when user asks about offshore wind, wind energy, marine wind, or wind turbine siting.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "wind_data_path":                  types.Schema(type=types.Type.STRING, description="Wind data point shapefile (NOAA/ECMWF)"),
                    "aoi_vector_path":                 types.Schema(type=types.Type.STRING, description="AOI polygon shapefile"),
                    "bathymetry_path":                 types.Schema(type=types.Type.STRING, description="Optional. Bathymetry raster. Omit it to use the server's built-in default global DEM (the user does not need to upload or know this path)."),
                    "land_polygon_vector_path":        types.Schema(type=types.Type.STRING, description="Optional. Land polygon for distance calculation. Omit it to use the server's built-in default global land polygon (the user does not need to upload or know this path)."),
                    "turbine_parameters_path":         types.Schema(type=types.Type.STRING, description="CSV with turbine specs"),
                    "global_wind_parameters_path":     types.Schema(type=types.Type.STRING, description="CSV with global wind model parameters"),
                    "number_of_turbines":              types.Schema(type=types.Type.INTEGER, description="Number of turbines per wind farm"),
                    "min_depth":                       types.Schema(type=types.Type.NUMBER, description="Minimum water depth (m), default 3"),
                    "max_depth":                       types.Schema(type=types.Type.NUMBER, description="Maximum water depth (m), default 60"),
                    "min_distance":                    types.Schema(type=types.Type.NUMBER, description="Minimum distance from shore (m), default 0"),
                    "max_distance":                    types.Schema(type=types.Type.NUMBER, description="Maximum distance from shore (m), default 200000"),
                    "valuation_container":             types.Schema(type=types.Type.BOOLEAN, description="Enable economic valuation, default false"),
                    "avg_grid_distance":               types.Schema(type=types.Type.NUMBER, description="Average grid distance (km), default 4"),
                },
                required=["wind_data_path", "aoi_vector_path", "turbine_parameters_path",
                          "global_wind_parameters_path", "number_of_turbines"],
            ),
        ),
        # ── Telecoupling Toolbox — Statistical & Analytical Tools ──────────────
        types.FunctionDeclaration(
            name="run_model_selection_ols",
            description="Run Ordinary Least Squares (OLS) regression on tabular CSV data. Supports model selection mode to test all variable combinations. Use when user asks about OLS, linear regression, model selection, R-squared, or explanatory variable analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":              types.Schema(type=types.Type.STRING, description="Path to input CSV with data"),
                    "dependent_variable":     types.Schema(type=types.Type.STRING, description="Column name of the dependent (Y) variable"),
                    "independent_variables":  types.Schema(type=types.Type.STRING, description="Comma-separated list of independent variable column names"),
                    "model_selection":        types.Schema(type=types.Type.BOOLEAN, description="If true, test all variable combinations and rank by Adj R², default false"),
                    "min_r2":                 types.Schema(type=types.Type.NUMBER, description="Minimum R² threshold for model selection, default 0.5"),
                    "max_vif":                types.Schema(type=types.Type.NUMBER, description="Maximum VIF for model selection, default 7.5"),
                    "max_p_value":            types.Schema(type=types.Type.NUMBER, description="Maximum coefficient p-value for model selection, default 0.05"),
                },
                required=["input_csv", "dependent_variable", "independent_variables"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_factor_analysis_mixed_data",
            description="Run Factor Analysis for Mixed Data (FAMD), PCA, or MCA via R/FactoMineR. Use when user asks about factor analysis, PCA, MCA, FAMD, dimensionality reduction, or mixed data analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":                types.Schema(type=types.Type.STRING, description="Path to input CSV with variables"),
                    "quantitative_variables":   types.Schema(type=types.Type.STRING, description="Comma-separated list of numeric variable column names"),
                    "qualitative_variables":    types.Schema(type=types.Type.STRING, description="Comma-separated list of categorical variable column names"),
                    "n_components":             types.Schema(type=types.Type.INTEGER, description="Number of components/dimensions, default 5"),
                    "handle_na":                types.Schema(type=types.Type.BOOLEAN, description="Impute missing values using missMDA, default true"),
                },
                required=["input_csv"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_co2_emissions",
            description="Calculate CO2 emissions from wildlife or goods transport routes. Use when user asks about CO2 emissions, transport emissions, carbon footprint of transport, or animal transport.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":              types.Schema(type=types.Type.STRING, description="CSV with transport route data"),
                    "capacity_per_trip":      types.Schema(type=types.Type.NUMBER, description="Number of animals/units per trip"),
                    "co2_per_km_per_trip":    types.Schema(type=types.Type.NUMBER, description="CO2 emissions in kg per km per trip"),
                    "animal_count_field":     types.Schema(type=types.Type.STRING, description="Column name for animal/unit count, default 'animal_count'"),
                    "length_km_field":        types.Schema(type=types.Type.STRING, description="Column name for route length in km, default 'length_km'"),
                    "id_field":               types.Schema(type=types.Type.STRING, description="Optional column name for route ID"),
                },
                required=["input_csv", "capacity_per_trip", "co2_per_km_per_trip"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_cost_benefit_analysis",
            description="Join cost and revenue data to a feature table and compute net returns (RETURNS = REVENUES - COSTS). Use when user asks about cost-benefit analysis, CBA, economic returns, costs vs revenues.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":          types.Schema(type=types.Type.STRING, description="Main feature CSV"),
                    "economic_data_csv":  types.Schema(type=types.Type.STRING, description="CSV with economic data containing cost and revenue columns"),
                    "key_field":          types.Schema(type=types.Type.STRING, description="Column name used to join the two CSVs"),
                    "cost_field":         types.Schema(type=types.Type.STRING, description="Column name for costs in economic_data_csv, default 'COSTS'"),
                    "revenue_field":      types.Schema(type=types.Type.STRING, description="Column name for revenues in economic_data_csv, default 'REVENUES'"),
                },
                required=["input_csv", "economic_data_csv", "key_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_population_count_density",
            description="Calculate population density per reporting unit and optionally compute population change between two time periods. Use when user asks about population density, population count, population growth, or demographic analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":                          types.Schema(type=types.Type.STRING, description="CSV with reporting unit data"),
                    "population_field":                   types.Schema(type=types.Type.STRING, description="Column name for population count"),
                    "area_km2_field":                     types.Schema(type=types.Type.STRING, description="Column name for area in km²"),
                    "unit_id_field":                      types.Schema(type=types.Type.STRING, description="Optional column name for unit ID (for joining second period data)"),
                    "second_period_csv":                  types.Schema(type=types.Type.STRING, description="Optional CSV for second time period (for population change analysis)"),
                    "second_period_population_field":     types.Schema(type=types.Type.STRING, description="Column name for population in second period CSV"),
                },
                required=["input_csv", "population_field", "area_km2_field"],
            ),
        ),
        # ── Telecoupling Toolbox — Spatial Flow & Visualization Tools ──────────
        types.FunctionDeclaration(
            name="run_draw_radial_flows",
            description="Generate radial flow lines from a CSV of origin-destination coordinate pairs. Use when user asks about radial flows, flow lines, OD matrix visualization, or origin-destination mapping.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":     types.Schema(type=types.Type.STRING, description="CSV with origin and destination coordinates"),
                    "from_x_field":  types.Schema(type=types.Type.STRING, description="Column name for origin longitude/X"),
                    "from_y_field":  types.Schema(type=types.Type.STRING, description="Column name for origin latitude/Y"),
                    "to_x_field":    types.Schema(type=types.Type.STRING, description="Column name for destination longitude/X"),
                    "to_y_field":    types.Schema(type=types.Type.STRING, description="Column name for destination latitude/Y"),
                    "crs":           types.Schema(type=types.Type.STRING, description="Coordinate reference system, default 'EPSG:4326'"),
                },
                required=["input_csv", "from_x_field", "from_y_field", "to_x_field", "to_y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_commodity_trade",
            description="Map bilateral commodity trade flows between countries as GeoJSON flow lines. Use when user asks about commodity trade, bilateral trade, trade flows, import/export mapping.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "trade_csv":            types.Schema(type=types.Type.STRING, description="CSV with trade data (country pairs and values)"),
                    "from_country_field":   types.Schema(type=types.Type.STRING, description="Column name for exporting country (ISO3 code recommended)"),
                    "to_country_field":     types.Schema(type=types.Type.STRING, description="Column name for importing country (ISO3 code recommended)"),
                    "value_field":          types.Schema(type=types.Type.STRING, description="Column name for trade value"),
                    "year_field":           types.Schema(type=types.Type.STRING, description="Optional column name for year"),
                    "year":                 types.Schema(type=types.Type.STRING, description="Optional year to filter (e.g. '2020')"),
                    "top_n_partners":       types.Schema(type=types.Type.INTEGER, description="Optional: keep only top N trade flows by value"),
                    "centroids_csv":        types.Schema(type=types.Type.STRING, description="Optional CSV with country centroids (columns: iso3, lon, lat)"),
                },
                required=["trade_csv", "from_country_field", "to_country_field", "value_field"],
            ),
        ),
        # ── Telecoupling Toolbox — Agents / Causes / Systems ───────────────────
        types.FunctionDeclaration(
            name="run_add_agents_interactively",
            description="Create a point feature layer for telecoupling agents from a CSV with Name, X (lon), Y (lat) columns. Use when user asks about adding agents, telecoupling agents, or placing agent points on a map.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":    types.Schema(type=types.Type.STRING, description="CSV with agent data including X and Y coordinates"),
                    "x_field":      types.Schema(type=types.Type.STRING, description="Column name for longitude/X"),
                    "y_field":      types.Schema(type=types.Type.STRING, description="Column name for latitude/Y"),
                    "name_field":   types.Schema(type=types.Type.STRING, description="Column name for agent name, default 'Name'"),
                    "text_field":   types.Schema(type=types.Type.STRING, description="Optional column name for additional text/description"),
                    "crs":          types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["input_csv", "x_field", "y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_draw_agents_from_table",
            description="Upload a pre-collected agent coordinate table (CSV) and render as point features. Use when user asks about drawing agents from a table, uploading agent coordinates, or batch agent mapping.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":    types.Schema(type=types.Type.STRING, description="CSV with agent coordinates"),
                    "x_field":      types.Schema(type=types.Type.STRING, description="Column name for longitude/X"),
                    "y_field":      types.Schema(type=types.Type.STRING, description="Column name for latitude/Y"),
                    "name_field":   types.Schema(type=types.Type.STRING, description="Optional column name for agent name"),
                    "crs":          types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["input_csv", "x_field", "y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_add_causes_interactively",
            description="Create point features for telecoupling causes (drivers/pressures) from a CSV with coordinates and description. Use when user asks about adding causes, telecoupling drivers, or cause points.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":          types.Schema(type=types.Type.STRING, description="CSV with cause data and coordinates"),
                    "x_field":            types.Schema(type=types.Type.STRING, description="Column name for longitude/X"),
                    "y_field":            types.Schema(type=types.Type.STRING, description="Column name for latitude/Y"),
                    "description_field":  types.Schema(type=types.Type.STRING, description="Column name for cause description, default 'DESCRIPTION'"),
                    "crs":                types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["input_csv", "x_field", "y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_add_systems_interactively",
            description="Create point features for telecoupling systems (sending/receiving/spillover) from a CSV with Name and coordinates. Use when user asks about adding systems, telecoupling systems, or system points.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":    types.Schema(type=types.Type.STRING, description="CSV with system data and coordinates"),
                    "x_field":      types.Schema(type=types.Type.STRING, description="Column name for longitude/X"),
                    "y_field":      types.Schema(type=types.Type.STRING, description="Column name for latitude/Y"),
                    "name_field":   types.Schema(type=types.Type.STRING, description="Column name for system name, default 'Name'"),
                    "crs":          types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["input_csv", "x_field", "y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_draw_systems_from_table",
            description="Upload a systems coordinate table (CSV) and render as point features. Use when user asks about drawing systems from a table, uploading system coordinates, or batch system mapping.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":  types.Schema(type=types.Type.STRING, description="CSV with system coordinates"),
                    "x_field":    types.Schema(type=types.Type.STRING, description="Column name for longitude/X"),
                    "y_field":    types.Schema(type=types.Type.STRING, description="Column name for latitude/Y"),
                    "crs":        types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["input_csv", "x_field", "y_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_add_media_flows",
            description="Parse an HTML file for country mentions and generate flow lines from a source point to each mentioned country. Use when user asks about media flows, information flows, country mentions in media, or media analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "html_file":               types.Schema(type=types.Type.STRING, description="Path to HTML file to parse for country mentions"),
                    "source_lon":              types.Schema(type=types.Type.NUMBER, description="Longitude of the source location (media outlet)"),
                    "source_lat":              types.Schema(type=types.Type.NUMBER, description="Latitude of the source location"),
                    "country_reference_csv":   types.Schema(type=types.Type.STRING, description="CSV with country names and centroids (columns: country/name, lon, lat)"),
                    "source_name":             types.Schema(type=types.Type.STRING, description="Name of the source (e.g. media outlet name), default 'Source'"),
                    "min_mentions":            types.Schema(type=types.Type.INTEGER, description="Minimum mention count to include a country, default 1"),
                    "crs":                     types.Schema(type=types.Type.STRING, description="CRS, default 'EPSG:4326'"),
                },
                required=["html_file", "source_lon", "source_lat", "country_reference_csv"],
            ),
        ),
        # ── Telecoupling Toolbox — Social & Food System Tools ──────────────────
        types.FunctionDeclaration(
            name="run_food_security",
            description="Analyze FAO food security indicators for selected countries and generate trend charts. Use when user asks about food security, FAO indicators, undernourishment, food availability, or food access analysis.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "fao_csv":           types.Schema(type=types.Type.STRING, description="Path to FAO food security CSV data"),
                    "countries":         types.Schema(type=types.Type.STRING, description="Comma-separated list of country names to analyze"),
                    "indicator_field":   types.Schema(type=types.Type.STRING, description="Indicator name or column name to analyze (e.g. 'Prevalence of undernourishment')"),
                    "country_field":     types.Schema(type=types.Type.STRING, description="Column name for country, default 'Area'"),
                    "year_field":        types.Schema(type=types.Type.STRING, description="Column name for year, default 'Year'"),
                    "value_field":       types.Schema(type=types.Type.STRING, description="Column name for indicator value, default 'Value'"),
                    "unit_field":        types.Schema(type=types.Type.STRING, description="Optional column name for unit"),
                },
                required=["fao_csv", "countries", "indicator_field"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_nutrition_metrics",
            description="Calculate Lower Limit Energy Requirements (LLER) by age group and sex using FAO nutritional formulas. Use when user asks about nutrition metrics, LLER, energy requirements, caloric needs, or nutrition by age group.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "population_csv":               types.Schema(type=types.Type.STRING, description="CSV with population data by age group and sex"),
                    "age_group_field":              types.Schema(type=types.Type.STRING, description="Column name for age group (e.g. '18-30'), default 'age_group'"),
                    "sex_field":                    types.Schema(type=types.Type.STRING, description="Column name for sex ('male'/'female'), default 'sex'"),
                    "population_count_field":       types.Schema(type=types.Type.STRING, description="Column name for population count, default 'population'"),
                    "weight_kg_field":              types.Schema(type=types.Type.STRING, description="Optional column name for body weight in kg (uses FAO defaults if not provided)"),
                    "male_height_cm":               types.Schema(type=types.Type.NUMBER, description="Reference male height in cm, default 170"),
                    "female_height_cm":             types.Schema(type=types.Type.NUMBER, description="Reference female height in cm, default 158"),
                },
                required=["population_csv"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_geographical_detector",
            description="Run the Geographical Detector (Geodetector, Wang Jinfeng) on tabular data to find which categorical factors drive the spatial variation of a continuous variable. Returns factor q-statistics, factor interactions, risk (stratum means), and ecological detectors. Use when user asks about geodetector, geographical detector, spatial stratified heterogeneity, q-statistic, driving factors, or factor/interaction detection.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_csv":     types.Schema(type=types.Type.STRING, description="Path to input CSV/xlsx with the dependent variable and factor columns"),
                    "y_variable":    types.Schema(type=types.Type.STRING, description="Column name of the continuous dependent variable Y (e.g. incidence)"),
                    "x_variables":   types.Schema(type=types.Type.STRING, description="Comma-separated list of CATEGORICAL factor column names (X). Continuous factors must be discretized into strata beforehand."),
                    "alpha":         types.Schema(type=types.Type.NUMBER, description="Significance level, default 0.05"),
                },
                required=["input_csv", "y_variable", "x_variables"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_spatial_autocorrelation_moran",
            description="Compute spatial autocorrelation (Moran's I) on a vector layer: global Moran's I with a significance test, plus local Moran (LISA) classifying each feature as hot spot (HH), cold spot (LL), or spatial outlier (HL/LH). Use when user asks about Moran's I, spatial autocorrelation, spatial clustering, hot spot / cold spot analysis, or LISA.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "input_vector":  types.Schema(type=types.Type.STRING, description="Path to a vector file (shapefile .shp, GeoJSON, or GPKG) with geometry and the value field"),
                    "value_field":   types.Schema(type=types.Type.STRING, description="Name of the numeric attribute column to analyse for spatial autocorrelation"),
                    "weights_type":  types.Schema(type=types.Type.STRING, description="Spatial weights: 'queen' (default) or 'rook' contiguity for polygons, or 'knn' for points/k-nearest neighbours"),
                    "k_neighbors":   types.Schema(type=types.Type.INTEGER, description="Number of neighbours when weights_type='knn', default 8"),
                    "permutations":  types.Schema(type=types.Type.INTEGER, description="Permutations for the pseudo p-value, default 999"),
                },
                required=["input_vector", "value_field"],
            ),
        ),
        # ── Utility tools ──────────────────────────────────────────────────────
        types.FunctionDeclaration(
            name="read_file_content",
            description=(
                "Read and return the content of an output file (CSV, TXT, JSON, or HTML) so you can "
                "analyze, summarize, or answer questions about it. HTML support is intended for "
                "InVEST report.html files — tables are flattened to pipe-separated rows and "
                "headings preserved. Use this whenever the user asks to summarize, analyze, "
                "explain, or ask questions about a specific output file (e.g. a network_stats CSV, "
                "a result_table CSV, an InVEST report.html). "
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


# ── Use-case workflow planning + execution layer (confirm-gated) ─────────────
from workflow.catalog import (
    PROPOSE_WORKFLOW_PLAN_DECLARATION, EXECUTE_WORKFLOW_PLAN_DECLARATION,
    CAPABILITY_CATALOG, WORKFLOW_PROMPT, plan_from_llm_args, input_map_from_llm_args,
)
from workflow import plan_from_dict, validate_plan
from workflow.engine import run_plan_async
TOOLS[0].function_declarations.append(PROPOSE_WORKFLOW_PLAN_DECLARATION)
TOOLS[0].function_declarations.append(EXECUTE_WORKFLOW_PLAN_DECLARATION)


def _format_plan_summary(plan_dict: dict) -> str:
    """Deterministic plain-language plan summary (fallback if the model emits no text)."""
    steps = plan_dict.get("steps", [])
    reqs = plan_dict.get("required_inputs", [])
    lines = [f"**{plan_dict.get('description') or plan_dict.get('case_name', 'Workflow plan')}**", "", "**Steps:**"]
    for i, s in enumerate(steps, 1):
        rat = f" — {s.get('rationale')}" if s.get("rationale") else ""
        lines.append(f"{i}. `{s.get('tool')}`{rat}")
    if reqs:
        lines.append("\n**Files to upload:**")
        for r in reqs:
            lines.append(f"- {r.get('label', r.get('id'))}")
    lines.append("\nConfirm and upload these files, and I'll run it.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Keyword-based tool routing
# ---------------------------------------------------------------------------

_TOOL_KEYWORDS: dict[str, list[str]] = {
    "run_network_analysis_grouping":        ["network analysis", "run_network_analysis"],
    "run_coastal_blue_carbon_preprocessor": ["coastal blue carbon preprocessor", "cbc preprocessor", "run_coastal_blue_carbon_preprocessor"],
    "run_coastal_blue_carbon":              ["coastal blue carbon main", "run_coastal_blue_carbon"],
    "run_seasonal_water_yield":             ["seasonal water yield", "run_seasonal_water_yield", " swy "],
    "run_crop_production_percentile":       ["crop production percentile", "run_crop_production_percentile"],
    "run_crop_production_regression":       ["crop production regression", "run_crop_production_regression"],
    "run_carbon_storage":                   ["carbon storage", "carbon sequestration", "run_carbon_storage"],
    "run_habitat_quality":                  ["habitat quality", "run_habitat_quality"],
    "run_annual_water_yield":               ["annual water yield", "run_annual_water_yield"],
    "run_forest_carbon_edge_effect":        ["forest carbon", "run_forest_carbon"],
    "run_crop_pollination":                 ["pollination", "run_crop_pollination", "run_pollination"],
    "run_delineateit":                      ["delineateit", "watershed delineation", "run_delineateit"],
    "run_routedem":                         ["routedem", "run_routedem"],
    "run_Sediment_Delivery_Ratio_SDR":      ["sediment delivery ratio", " sdr", "run_sdr", "run_sediment", "run_Sediment_Delivery_Ratio_SDR"],
    "run_ndr":                              ["nutrient delivery ratio", " ndr", "run_ndr"],
    "run_urban_cooling":                    ["urban cooling", "run_urban_cooling"],
    "run_urban_flood_risk_mitigation":      ["urban flood", "run_urban_flood"],
    "run_urban_stormwater_retention":       ["urban stormwater", "run_urban_stormwater"],
    "run_urban_nature_access":              ["urban nature access", "run_urban_nature"],
    "run_urban_mental_health":              ["urban mental health", "run_urban_mental"],
    "run_scenic_quality":                   ["scenic quality", "run_scenic_quality"],
    "run_habitat_risk_assessment":          ["habitat risk assessment", " hra", "run_habitat_risk"],
    "run_wave_energy_production":           ["wave energy", "run_wave_energy"],
    "run_scenario_gen_proximity":           ["scenario generator proximity", "scenario gen proximity", "run_scenario_gen"],
    "run_coastal_vulnerability":            ["coastal vulnerability", "run_coastal_vulnerability"],
    "run_offshore_wind_energy":             ["offshore wind", "run_offshore_wind"],
}

_TOOL_BY_NAME: dict[str, types.Tool] = {
    fd.name: tool
    for tool in TOOLS
    for fd in tool.function_declarations
}


def _detect_tool_from_message(message: str) -> str | None:
    """Return the function name that best matches the user message, or None."""
    msg_lower = message.lower()
    for tool_name, keywords in _TOOL_KEYWORDS.items():
        if any(kw.lower() in msg_lower for kw in keywords):
            return tool_name
    return None


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
    chat_history: list[dict] | None = None,
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
        "run_Sediment_Delivery_Ratio_SDR":      "q_sdr",
        "run_ndr":                              "q_ndr",
        "run_urban_cooling":                    "q_urban_cooling",
        "run_urban_flood_risk_mitigation":      "q_urban_flood",
        "run_urban_stormwater_retention":       "q_urban_stormwater",
        "run_urban_nature_access":              "q_urban_nature",
        "run_urban_mental_health":              "q_urban_mental_health",
        "run_scenic_quality":                   "q_scenic_quality",
        "run_habitat_risk_assessment":          "q_hra",
        "run_wave_energy_production":           "q_wave_energy",
        "run_scenario_gen_proximity":           "q_scenario_gen",
        "run_coastal_vulnerability":            "q_coastal_vuln",
        "run_offshore_wind_energy":             "q_wind_energy",
        "run_model_selection_ols":              "q_ols",
        "run_factor_analysis_mixed_data":       "q_famd",
        "run_co2_emissions":                    "q_co2",
        "run_cost_benefit_analysis":            "q_cba",
        "run_population_count_density":         "q_pop_density",
        "run_draw_radial_flows":                "q_radial_flows",
        "run_commodity_trade":                  "q_commodity_trade",
        "run_add_agents_interactively":         "q_add_agents",
        "run_draw_agents_from_table":           "q_draw_agents",
        "run_add_causes_interactively":         "q_add_causes",
        "run_add_systems_interactively":        "q_add_systems",
        "run_draw_systems_from_table":          "q_draw_systems",
        "run_add_media_flows":                  "q_add_media",
        "run_food_security":                    "q_food_security",
        "run_nutrition_metrics":                "q_nutrition",
        "run_geographical_detector":            "q_geodetector",
        "run_spatial_autocorrelation_moran":    "q_spatial_moran",
    }

    client = _get_client()
    model_name = model or settings.DEFAULT_MODEL

    # Phase 1: build system instruction with PRE_EXECUTION skill sections
    pre_execution_context = _build_pre_execution_context()
    system_instruction = (
        _BASE_SYSTEM_INSTRUCTION
        + "\n\n" + WORKFLOW_PROMPT
        + "\n\n" + CAPABILITY_CATALOG
        + pre_execution_context
    )

    # Build initial user message (uploaded + previous output file paths prepended)
    from shared.session_manager import SessionManager as _SM
    _sm = _SM()
    context_lines = []
    current_paths = {f.get('path', '') for f in (files or [])}
    if files:
        context_lines += [
            f"Uploaded file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in files
        ]
    # Re-inject files uploaded in previous turns so Gemini can use them even when
    # the user spreads parameter collection across multiple messages.
    prev_uploaded = [
        f for f in _sm.get_uploaded_files(session_id)
        if f.get('path', '') not in current_paths
    ]
    if prev_uploaded:
        context_lines += [
            f"Previously uploaded file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in prev_uploaded
        ]
    output_files = _sm.get_output_files(session_id)
    if output_files:
        context_lines += [
            f"Previous output file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in output_files
        ]
    user_text = "\n".join(context_lines) + "\n\n" + message if context_lines else message

    # Build multi-turn contents: prepend prior conversation history so Gemini
    # remembers what was discussed in earlier turns of this session.
    contents: list[types.Content] = []
    for turn in (chat_history or []):
        contents.append(types.Content(
            role=turn["role"],
            parts=[types.Part.from_text(text=turn["text"])],
        ))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))

    # Detect which tool the user is requesting. Used in retry nudge messages.
    detected_tool_name = _detect_tool_from_message(user_text)
    if detected_tool_name:
        logger.info(f"[agent] keyword-routing → {detected_tool_name}")

    # When a specific tool is detected, use only that tool's FunctionDeclaration
    # on the first call. With just 1 function in scope, Gemini has no ambiguity
    # and reliably calls it. Falls back to all TOOLS if no tool is detected or
    # after the first iteration (tool call already made).
    _single_tool: list[types.Tool] | None = (
        [_TOOL_BY_NAME[detected_tool_name]]
        if detected_tool_name and detected_tool_name in _TOOL_BY_NAME
        else None
    )

    # run_crop_pollination consistently returns empty content at temperature=0.
    # Start at 0.9 directly so it passes on the first call without retries.
    # (run_Sediment_Delivery_Ratio_SDR behaves inconsistently at 0.9 and recovers faster via retries at 0.)
    _HIGH_TEMP_TOOLS = {"run_crop_pollination"}
    base_temperature = 0.9 if detected_tool_name in _HIGH_TEMP_TOOLS else 0

    # Agentic loop
    max_iterations = 10
    # Gemini 2.5 supports "thinking": ask for thought summaries so the UI can show
    # a collapsible "Thinking…" block. Older models don't accept the config.
    thinking_cfg = types.ThinkingConfig(include_thoughts=True) if "2.5" in model_name else None

    for iteration in range(max_iterations):
        logger.info(f"[agent] iteration={iteration} session={session_id} model={model_name}")

        # Use the single-tool list on iteration 0 (when we know which tool to call),
        # then switch to full TOOLS list for follow-up iterations.
        active_tools = _single_tool if (iteration == 0 and _single_tool is not None) else TOOLS

        gen_cfg = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=active_tools,
            temperature=base_temperature,
            thinking_config=thinking_cfg,
        )

        response = await _generate_streaming(
            client,
            model_name,
            contents,
            gen_cfg,
            event_callback,
        )

        if not response.candidates:
            logger.warning("[agent] Gemini returned no candidates, stopping")
            break

        candidate = response.candidates[0]
        if candidate.content is None or candidate.content.parts is None:
            finish = getattr(candidate, "finish_reason", "?")
            logger.warning(f"[agent] Empty content (finish_reason={finish}), retrying up to 10x")
            fn_name = detected_tool_name or "the appropriate function"
            # Escalating temperatures; never drop below base_temperature so retries
            # don't regress to a state already known to produce empty content.
            _retry_temps = [max(base_temperature, t)
                            for t in [0.5, 0.7, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]
            recovered = False
            for _r in range(10):
                await asyncio.sleep(2 ** min(_r, 3))
                retry_temp = _retry_temps[_r]
                # Use a FRESH single-turn conversation on every retry so Gemini
                # never sees two consecutive user messages (invalid turn structure).
                direct_cmd = (
                    f"Call `{fn_name}` with the following parameters:\n{user_text}"
                )
                retry_contents = [
                    types.Content(role="user", parts=[types.Part.from_text(text=direct_cmd)]),
                ]
                retry_cfg = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=active_tools,
                    temperature=retry_temp,
                    thinking_config=thinking_cfg,
                )
                resp2 = await _generate_streaming(client, model_name, retry_contents, retry_cfg, event_callback)
                c0 = resp2.candidates[0] if resp2.candidates else None
                if c0 and c0.content is not None and c0.content.parts is not None:
                    response = resp2
                    candidate = c0
                    contents = retry_contents
                    recovered = True
                    logger.info(f"[agent] Recovered on retry {_r + 1} (temp={retry_temp})")
                    break
                logger.warning(f"[agent] Retry {_r + 1} still empty/no-parts (temp={retry_temp})")
            if not recovered:
                logger.warning("[agent] All retries exhausted, stopping")
                break

        contents.append(candidate.content)

        function_calls = [
            part.function_call
            for part in candidate.content.parts
            if part.function_call is not None
        ]

        # NOTE: text/thinking are already streamed live to the frontend inside
        # _generate_streaming as deltas arrive — do NOT re-emit them here.

        if not function_calls:
            break

        function_response_parts: list[types.Part] = []
        workflow_proposed = False        # propose_workflow_plan is terminal for the turn
        plan_summary_fallback = ""

        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args)
            logger.info(f"[agent] function_call: {tool_name}")

            # ── Workflow planning: validate + surface the plan; do NOT execute.
            # The confirm-gate: the model proposes, the user confirms later.
            if tool_name == "propose_workflow_plan":
                try:
                    plan_dict = plan_from_llm_args(tool_input)
                    plan = plan_from_dict(plan_dict)
                    plan_errors = validate_plan(plan, available_tools=set(TOOL_FILE_SPECS))
                except Exception as pe:  # malformed plan args
                    plan_dict = tool_input
                    plan_errors = [f"could not parse plan: {pe}"]
                await _maybe_await(event_callback({
                    "type": "workflow_plan",
                    "plan": plan_dict,
                    "valid": not plan_errors,
                    "errors": plan_errors,
                }))
                if plan_errors:
                    fr = {"status": "invalid_plan", "errors": plan_errors,
                          "instruction": "Fix these issues and call propose_workflow_plan again."}
                else:
                    # Stash the valid plan so a later confirm turn can execute it.
                    try:
                        from shared.session_manager import SessionManager as _SMx
                        _SMx().set_workflow_plan(session_id, plan_dict)
                    except Exception:
                        logger.exception("[agent] failed to stash workflow plan")
                    workflow_proposed = True
                    plan_summary_fallback = _format_plan_summary(plan_dict)
                    fr = {"status": "plan_proposed", "n_steps": len(plan_dict.get("steps", [])),
                          "files_needed": [ri.get("label", ri.get("id"))
                                           for ri in plan_dict.get("required_inputs", [])],
                          "instruction": ("Plan is valid and saved. Summarize the steps in plain language, list "
                                          "the files the user must upload, and ask them to confirm before running. "
                                          "Do NOT claim it has run.")}
                function_response_parts.append(
                    types.Part.from_function_response(name=tool_name, response={"result": fr})
                )
                continue

            # ── Workflow execution: run the confirmed plan (reconcile + stream each step).
            if tool_name == "execute_workflow_plan":
                from shared.session_manager import SessionManager as _SMx
                _sm = _SMx()
                stored = _sm.get_workflow_plan(session_id)
                if not stored:
                    function_response_parts.append(types.Part.from_function_response(
                        name=tool_name, response={"result": {
                            "status": "no_plan",
                            "instruction": "No saved plan; call propose_workflow_plan first."}}))
                    continue
                wf_plan = plan_from_dict(stored)
                inputs_map = input_map_from_llm_args(tool_input)
                unmapped = sorted(wf_plan.input_ids - set(inputs_map))
                missing = sorted([p for p in inputs_map.values() if not os.path.exists(p)])
                if unmapped or missing:
                    function_response_parts.append(types.Part.from_function_response(
                        name=tool_name, response={"result": {
                            "status": "need_files", "unmapped_inputs": unmapped, "missing_files": missing,
                            "instruction": "Ask the user to provide the missing files, then call execute_workflow_plan again."}}))
                    continue

                # Bridge engine events -> the tool-card events the frontend already renders.
                async def _wf_emit(ev: dict) -> None:
                    t = ev.get("type")
                    if t == "step_started":
                        await _maybe_await(event_callback({
                            "type": "tool_start", "tool": ev["tool"], "task_id": ev["step"],
                            "message": f"[{ev['index']}/{ev['total']}] {ev['tool']}"}))
                    elif t == "step_progress":
                        await _maybe_await(event_callback({
                            "type": "tool_progress", "task_id": ev["step"],
                            "progress": ev["progress"], "message": ev["message"]}))
                    elif t == "step_done":
                        await _maybe_await(event_callback({
                            "type": "tool_result", "task_id": ev["step"],
                            "files": ev.get("files", []), "content": ""}))
                        await _maybe_await(event_callback({"type": "done", "task_id": ev["step"]}))
                    elif t == "step_error":
                        await _maybe_await(event_callback({
                            "type": "error", "task_id": ev["step"], "error_code": "TOOL_FAILED",
                            "message": f"step {ev['step']}: {ev['error']}"}))
                    elif t == "plan_reconciled":
                        fixes = "; ".join(f"{f['param']}:{f['from']}->{f['to']}" for f in ev["fixes"])
                        await _maybe_await(event_callback({"type": "text_chunk", "content": f"\n(Calibrated columns: {fixes})\n"}))
                    elif t == "plan_reconcile_failed":
                        mm = "; ".join(f"{m['step']}.{m['param']}='{m['value']}'" for m in ev["mismatches"])
                        await _maybe_await(event_callback({
                            "type": "error", "error_code": "INVALID_PARAMS",
                            "message": f"Column mismatch, cannot run: {mm}"}))

                try:
                    wf_ctx = await run_plan_async(wf_plan, inputs_map, session_id, _wf_emit)
                except Exception as wfe:
                    logger.exception("[agent] workflow execution failed")
                    function_response_parts.append(types.Part.from_function_response(
                        name=tool_name, response={"error": sanitize_error_message(str(wfe))}))
                    continue

                try:
                    _sm.add_output_files(session_id, wf_ctx.get("files", []))
                except Exception:
                    pass

                fr = {"status": wf_ctx.get("status"),
                      "steps": {sid: s.get("status") for sid, s in wf_ctx.get("steps", {}).items()},
                      "n_files": len(wf_ctx.get("files", [])),
                      "output_files": [f.get("filename") for f in wf_ctx.get("files", [])],
                      "warnings": wf_ctx.get("warnings", []),
                      "mismatches": wf_ctx.get("mismatches", []),
                      "instruction": ("Summarize for the user which steps ran, key outputs, and any warnings. "
                                      "Output files are already shown as cards above; do not re-list raw paths.")}
                function_response_parts.append(types.Part.from_function_response(
                    name=tool_name, response={"result": fr}))
                continue

            # ── Step 0: generic pre-flight — catch missing input files before
            # dispatching, so the user gets a friendly "file not found / not
            # uploaded" message instead of a cryptic crash inside the worker.
            try:
                validate_file_params_exist(tool_input)
                _specs = TOOL_FILE_SPECS.get(tool_name)
                if _specs:
                    validate_input_files(tool_input, _specs)
            except CSISError as ve:
                safe_msg = sanitize_error_message(ve.message)
                logger.info(f"[agent] pre-flight blocked {tool_name}: {safe_msg}")
                await _maybe_await(event_callback({
                    "type": "error",
                    "message": safe_msg,
                    "error_code": ve.error_code,
                }))
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"error": safe_msg},
                    )
                )
                continue

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
                safe_msg = sanitize_error_message(str(exc))
                await _maybe_await(event_callback({
                    "type": "error",
                    "message": safe_msg,
                    "error_code": "TOOL_FAILED",
                }))
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"error": safe_msg},
                    )
                )
            finally:
                await r_sub.aclose()

        # A proposed plan is terminal for this turn: stop now so we don't run a
        # second LLM turn (which would re-think and re-summarize -> duplicate plans).
        # The user confirms in the next message, which triggers execute_workflow_plan.
        if workflow_proposed:
            has_answer_text = any(
                getattr(p, "text", None) and not getattr(p, "thought", False)
                for p in candidate.content.parts
            )
            if not has_answer_text and plan_summary_fallback:
                await _maybe_await(event_callback({"type": "text_chunk", "content": plan_summary_fallback}))
            break

        # Feed all function responses back to Gemini for final reply
        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

    await _maybe_await(event_callback({"type": "done"}))
