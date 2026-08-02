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
import random
import re
import uuid
from pathlib import Path
from typing import Callable, Any

import httpx
import os

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from google.genai.client import HttpOptions
import redis.asyncio as aioredis

from config import resolve_model_name, settings
from shared.gemini_capacity import gemini_capacity_gate
from shared.utils import sanitize_error_message, validate_file_params_exist, validate_input_files, CSISError
from shared.tool_file_specs import TOOL_FILE_SPECS

logger = logging.getLogger(__name__)

_CJK_TEXT_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]")
_THINKING_ENGLISH_FALLBACK = "Processing the request and preparing the next step.\n"
_GEMINI_STALL_TIMEOUT = 60
_GEMINI_ATTEMPT_TIMEOUT = 120
_TOOL_EVENT_TIMEOUT = 1800
_PUBSUB_SUBSCRIBE_TIMEOUT = 5


def _supports_thinking(model_name: str) -> bool:
    return model_name.startswith(("gemini-2.5-", "gemini-3.5-"))


def _sanitize_visible_thinking_text(text: str) -> str:
    if not text:
        return ""
    if not _CJK_TEXT_RE.search(text):
        return text
    safe_lines = [
        line
        for line in text.splitlines(keepends=True)
        if not _CJK_TEXT_RE.search(line)
    ]
    safe_text = "".join(safe_lines)
    return "" if _CJK_TEXT_RE.search(safe_text) else safe_text

def _transient_error_kind(exc: BaseException) -> str | None:
    if isinstance(exc, genai_errors.APIError):
        code = int(exc.code or 0)
        if code == 429:
            return "rate limit"
        if code in {500, 502, 503, 504}:
            return "server error"
        if code in {408}:
            return "timeout"
        return None
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return "timeout"
    if isinstance(exc, httpx.TransportError):
        return "transport error"
    return None


def _retry_delay(exc: BaseException, attempt: int) -> float:
    if isinstance(exc, genai_errors.APIError) and exc.response is not None:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    return (2 ** attempt) + random.uniform(0, 1)


async def _generate_with_retry(client, model_name: str, contents, config, max_retries: int = 4):
    """Call Gemini with bounded admission and backoff outside the active slot."""
    estimated_tokens = gemini_capacity_gate.estimate_input_tokens(contents, config)
    for attempt in range(max_retries):
        try:
            async with gemini_capacity_gate.slot(estimated_tokens):
                return await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    ),
                    timeout=_GEMINI_STALL_TIMEOUT,
                )
        except (genai_errors.APIError, httpx.HTTPError, asyncio.TimeoutError) as exc:
            kind = _transient_error_kind(exc)
            if kind is None or attempt >= max_retries - 1:
                raise
            wait = _retry_delay(exc, attempt)
            logger.warning(
                "[agent] Gemini %s (attempt %s/%s), retrying in %.1fs",
                kind,
                attempt + 1,
                max_retries,
                wait,
            )
            await asyncio.sleep(wait)


class _StreamedResponse:
    """Minimal stand-in for a GenerateContentResponse, assembled from a stream so
    the rest of run_agent (function-call extraction, history append, empty-recovery)
    works unchanged. content.parts is None when nothing usable streamed."""
    def __init__(self, content):
        self.candidates = [types.Candidate(content=content)]


async def _consume_gemini_stream(client, model_name: str, contents, config, emit):
    """Consume one SDK stream attempt without owning a capacity slot."""
    import inspect
    collected = []
    thinking_fallback_sent = False
    maybe = client.aio.models.generate_content_stream(
        model=model_name, contents=contents, config=config,
    )
    stream = (
        await asyncio.wait_for(maybe, timeout=_GEMINI_STALL_TIMEOUT)
        if inspect.isawaitable(maybe)
        else maybe
    )
    ait = stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(
                ait.__anext__(),
                timeout=_GEMINI_STALL_TIMEOUT,
            )
        except StopAsyncIteration:
            break
        cand = chunk.candidates[0] if getattr(chunk, "candidates", None) else None
        if not cand or cand.content is None or not cand.content.parts:
            continue
        for part in cand.content.parts:
            if part.function_call is not None:
                collected.append(part)
            elif part.text:
                if getattr(part, "thought", False):
                    visible_thinking = _sanitize_visible_thinking_text(part.text)
                    if visible_thinking:
                        await _maybe_await(emit({
                            "type": "thinking",
                            "content": visible_thinking,
                        }))
                    elif not thinking_fallback_sent:
                        await _maybe_await(emit({
                            "type": "thinking",
                            "content": _THINKING_ENGLISH_FALLBACK,
                        }))
                        thinking_fallback_sent = True
                else:
                    await _maybe_await(emit({
                        "type": "text_chunk",
                        "content": part.text,
                    }))
                collected.append(part)

    has_real = any(
        getattr(part, "function_call", None) is not None
        or (
            getattr(part, "text", None)
            and not getattr(part, "thought", False)
        )
        for part in collected
    )
    content = (
        types.Content(role="model", parts=collected)
        if collected
        else types.Content(role="model")
    )
    return _StreamedResponse(content), has_real


async def _generate_streaming(client, model_name: str, contents, config, emit,
                              max_retries: int = 4):
    """Stream Gemini with bounded admission and cancellation-resistant retries."""
    estimated_tokens = gemini_capacity_gate.estimate_input_tokens(contents, config)
    capacity_notice_sent = False

    async def emit_capacity_wait(event: dict) -> None:
        nonlocal capacity_notice_sent
        if not capacity_notice_sent:
            capacity_notice_sent = True
            await _maybe_await(emit(event))

    for attempt in range(max_retries):
        retry_wait: float | None = None
        attempt_state = {"active": True}

        async def attempt_emit(event, state=attempt_state):
            if state["active"]:
                await _maybe_await(emit(event))

        try:
            async with gemini_capacity_gate.slot(
                estimated_tokens,
                on_wait=emit_capacity_wait,
            ):
                stream_task = asyncio.create_task(
                    _consume_gemini_stream(
                        client,
                        model_name,
                        contents,
                        config,
                        attempt_emit,
                    )
                )
                try:
                    done, _ = await asyncio.wait(
                        {stream_task},
                        timeout=_GEMINI_ATTEMPT_TIMEOUT,
                    )
                except asyncio.CancelledError:
                    attempt_state["active"] = False
                    stream_task.cancel()
                    stream_task.add_done_callback(_discard_task_result)
                    raise

                if not done:
                    attempt_state["active"] = False
                    stream_task.cancel()
                    stream_task.add_done_callback(_discard_task_result)
                    raise asyncio.TimeoutError(
                        f"Gemini stream exceeded {_GEMINI_ATTEMPT_TIMEOUT}s"
                    )

                response, has_real = stream_task.result()

            if not has_real and attempt < max_retries - 1:
                logger.warning(
                    "[agent] Gemini empty/answer-less stream "
                    "(attempt %s/%s), retrying on fresh connection",
                    attempt + 1,
                    max_retries,
                )
                retry_wait = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
            else:
                return response
        except asyncio.TimeoutError:
            if attempt >= max_retries - 1:
                raise
            retry_wait = 0.5 + random.uniform(0, 0.5)
            logger.warning(
                "[agent] Gemini stream STALLED >%ss with no output "
                "(attempt %s/%s), retrying on fresh connection",
                _GEMINI_STALL_TIMEOUT,
                attempt + 1,
                max_retries,
            )
        except (genai_errors.APIError, httpx.HTTPError) as exc:
            kind = _transient_error_kind(exc)
            if kind is None or attempt >= max_retries - 1:
                raise
            retry_wait = _retry_delay(exc, attempt)
            logger.warning(
                "[agent] Gemini stream %s (attempt %s/%s), retrying in %.1fs",
                kind,
                attempt + 1,
                max_retries,
                retry_wait,
            )

        if retry_wait is not None:
            await asyncio.sleep(retry_wait)


def _discard_task_result(task: asyncio.Task) -> None:
    """Consume a detached timed-out task without waiting for SDK cancellation."""
    try:
        task.result()
    except (asyncio.CancelledError, Exception):
        pass


# ---------------------------------------------------------------------------
# Gemini client — lazy singleton, created on first use
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    import httpx
    timeout = httpx.Timeout(60.0, connect=30.0, pool=30.0)
    # Always create a fresh client — the genai SDK may close the httpx.AsyncClient
    # after each session, so reusing a cached client causes ConnectError on
    # subsequent requests. Fresh clients are lightweight and avoid stale pool issues.
    return genai.Client(
        api_key=settings.GOOGLE_API_KEY,
        http_options=HttpOptions(
            httpx_client=httpx.Client(verify=False, timeout=timeout),
            httpx_async_client=httpx.AsyncClient(verify=False, timeout=timeout),
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

Do NOT proactively list, enumerate, or describe the available tools/models in your replies. When the user asks to run an analysis or names a task, silently pick the single most appropriate tool and either run it or ask only for its missing parameters — never preface your answer with the tool catalog or a rundown of what you "can" do. Output the full list below ONLY when the user explicitly asks something like "what tools/models do you support?" or "list all tools". In that one case, respond with the exact markdown list below, copied verbatim — do NOT rephrase, reorder, or add function call names (run_xxx). Always start the list on a new paragraph (blank line before the first section header).

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

## Describing Outputs (IMPORTANT — accuracy over enthusiasm)
- Only mention output files that ACTUALLY appear in the tool result's returned file list. Never claim a file was produced (e.g. a report.html, a .tif, a chart, a map) unless it is present in those results.
- Do not describe results, maps, numbers, or findings you did not actually receive from a tool call or a read_file_content result. Base every claim strictly on real returned data — not on the tool's general description of what it "can" do.
- If the user expected an output that was not produced (e.g. no .tif, no report), say so plainly instead of implying it exists.

## Image / Map Output Rules (CRITICAL)
- NEVER write inline image data in your text response. Specifically: do NOT emit `![...](data:image/png;base64,...)`, do NOT emit any `data:image/*;base64,...` URLs, and do NOT emit fake/fabricated base64 byte strings.
- The ONLY way to show a rendered map or image is to call the `render_spatial_file` tool. The frontend will display the resulting PNG automatically — you do not need to embed it in your reply.
- NEVER claim, state, or imply that you rendered/showed/displayed a map or image (e.g. "Here is the rendered map", "the image is shown above", "you can download this image") UNLESS you actually called `render_spatial_file` for that exact file. Describing or announcing a render you did not perform is a hard error — it produces NO image for the user.
- When the user asks to show / render / display / visualize / 可视化 ANY spatial file (.tif, .tiff, .shp, .geojson, .gpkg — including point layers like agents/systems and line layers like flows), you MUST call `render_spatial_file` on that file. Never answer with text alone claiming it is done.
- There is NO exception and NO shortcut. EVERY time the user asks to show/render/display/visualize a file, call `render_spatial_file` for it AGAIN, even if you or an earlier turn already rendered it. Re-rendering is cheap, fast, and safe. You must NEVER say "already shown above", "rendered in the previous turn", "the map is displayed", or anything implying an image exists, UNLESS you are calling `render_spatial_file` in THIS same response. Claiming a prior render instead of calling the tool is a hard error that leaves the user with no image.
- You cannot draw images yourself and you cannot remember/reuse a previous render. If asked to "show a map" or "visualize", call `render_spatial_file` on the relevant file in this very turn — no matter how many times it has been rendered before.
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
                    "decay_function":           types.Schema(
                        type=types.Type.STRING,
                        enum=["gaussian", "exponential", "dichotomy", "density"],
                        description="'gaussian' (default) | 'exponential' | 'dichotomy' | 'density'",
                    ),
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
                "The file_path must be an absolute path to an existing file on disk. "
                "For radial-flow layers (radial_flows.shp), you MUST also pass magnitude_field — "
                "the column whose value sets each flow's color and line width (e.g. tourists/volume/trips). "
                "If you don't know which column to use, render once without it: the tool will reply with "
                "the list of available numeric columns; show those to the user, ask which one is the flow "
                "magnitude, then call again with magnitude_field set."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "file_path": types.Schema(
                        type=types.Type.STRING,
                        description="Absolute path to the spatial file (.tif, .tiff, .shp, .geojson, or .gpkg) to render.",
                    ),
                    "magnitude_field": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "For radial-flow layers only: the numeric column that drives flow color "
                            "and line width (e.g. 'tourists'). Omit for non-flow files."
                        ),
                    ),
                    "category_field": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "For systems-point layers only: the column to categorize markers by "
                            "(e.g. 'type' = Sending/Receiving/Spillover). Optional; auto-detected if omitted."
                        ),
                    ),
                    "render_as": types.Schema(
                        type=types.Type.STRING,
                        description=(
                            "Telecoupling render style override: one of 'flow', 'system', 'agent', 'cause'. "
                            "Files produced by the telecoupling tools are auto-detected (they carry a tc_role tag), "
                            "so you normally OMIT this. ONLY set it when the user uploads their OWN .shp/.geojson and "
                            "explicitly asks to render it as a flow/system/agent/cause map. If the user uploads a "
                            "spatial file and wants telecoupling styling but does NOT say which type, ask them."
                        ),
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
    ADD_WORKFLOW_STEPS_DECLARATION,
    CAPABILITY_CATALOG, WORKFLOW_PROMPT, plan_from_llm_args, input_map_from_llm_args,
    field_overrides_from_llm_args, file_overrides_from_llm_args,
)
from workflow import plan_from_dict, validate_plan
from workflow.engine import run_plan_async
TOOLS[0].function_declarations.append(PROPOSE_WORKFLOW_PLAN_DECLARATION)
TOOLS[0].function_declarations.append(EXECUTE_WORKFLOW_PLAN_DECLARATION)
TOOLS[0].function_declarations.append(ADD_WORKFLOW_STEPS_DECLARATION)

# Telecoupling composite map (Phase B): overlay flows + systems + agents into ONE
# Fig.10-style image. Use when the user wants the combined telecoupling map, not a
# single layer. Pass the absolute paths of whichever layers exist; flows REQUIRE a
# magnitude_field (render once without it to get the candidate column list).
TOOLS[0].function_declarations.append(
    types.FunctionDeclaration(
        name="render_telecoupling_scene",
        description=(
            "Composite a single Tonini & Liu Fig.10-style telecoupling map by overlaying any "
            "subset of these previously-produced layers onto a satellite basemap: flows "
            "(radial_flows.shp), systems (systems_from_table.shp), agents (agents_from_table.shp). "
            "Use this when the user asks for the combined/overall telecoupling map (systems + agents "
            "+ flows together), as opposed to rendering one file. Provide the absolute path of each "
            "layer that exists (at least one is required). If flows are included you MUST pass "
            "magnitude_field (the flow volume column, e.g. tourists); if you don't know it, call once "
            "without it and the tool returns the candidate numeric columns to ask the user about. "
            "If the user UPLOADED several telecoupling layer files (e.g. radial_flows.geojson, "
            "systems.geojson, agents.geojson, causes.geojson) and asks to combine them, just pass ALL "
            "their paths in `layers` — the tool auto-detects each file's role from its tc_role tag, so "
            "you do NOT need to sort them into flows_file/systems_file/etc."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "layers": types.Schema(
                    type=types.Type.ARRAY,
                    items=types.Schema(type=types.Type.STRING),
                    description=(
                        "List of absolute paths to telecoupling layer files (.shp/.geojson) to "
                        "auto-route by their tc_role tag. Best for combining freshly-uploaded files: "
                        "pass them all here and the tool assigns each to flows/systems/agents/causes. "
                        "Explicit *_file params (below) take priority over these."
                    ),
                ),
                "flows_file": types.Schema(
                    type=types.Type.STRING,
                    description="Absolute path to the radial_flows .shp/.geojson (optional).",
                ),
                "systems_file": types.Schema(
                    type=types.Type.STRING,
                    description="Absolute path to the systems_from_table .shp/.geojson (optional).",
                ),
                "agents_file": types.Schema(
                    type=types.Type.STRING,
                    description="Absolute path to the agents .shp/.geojson (optional).",
                ),
                "causes_file": types.Schema(
                    type=types.Type.STRING,
                    description="Absolute path to the causes .shp/.geojson (optional; drawn as star markers).",
                ),
                "magnitude_field": types.Schema(
                    type=types.Type.STRING,
                    description="Flow volume column driving color/width (required when flows_file is given).",
                ),
                "category_field": types.Schema(
                    type=types.Type.STRING,
                    description="System type column (e.g. 'type'); optional, auto-detected if omitted.",
                ),
            },
            required=[],
        ),
    )
)


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


def _subset_plan_dict(plan_dict: dict, selected_ids: list[str]) -> dict:
    """Filter a plan dict down to the user-chosen steps (plan card multi-select).

    Keeps only `selected_ids` steps and the required_inputs those steps actually
    reference (source=input). Returns the original plan unchanged if nothing matches
    (defensive — better to run the whole plan than an empty one)."""
    sel = {s for s in selected_ids if s}
    steps = [s for s in plan_dict.get("steps", []) if s.get("id") in sel]
    if not steps:
        return plan_dict
    used_inputs: set[str] = set()
    for s in steps:
        for src in (s.get("inputs") or {}).values():
            if src.get("source") == "input" and src.get("ref"):
                used_inputs.add(src["ref"])
    reqs = [r for r in plan_dict.get("required_inputs", []) if r.get("id") in used_inputs]
    return {**plan_dict, "steps": steps, "required_inputs": reqs}


def _subset_dep_error(plan) -> str | None:
    """If a kept step consumes a dropped step's output (source=step → missing id),
    the subset is broken. Return a human message naming the gap, else None."""
    kept = plan.step_ids
    for st in plan.steps:
        for src in st.inputs.values():
            if src.source == "step" and src.ref not in kept:
                return (f"step '{st.id}' needs the output of '{src.ref}', which you deselected. "
                        f"Include '{src.ref}' (or deselect '{st.id}').")
    return None


# ── Deterministic re-plan (plan card "Add & re-plan") ───────────────────────
# The card sends the kept step ids in a machine token + the new analysis text. The
# backend keeps those steps EXACTLY and asks the LLM only for the NEW step(s), then
# merges — so the model can never silently re-add steps the user deselected (the
# "kept 3, added 1, got 6" bug). The LLM never touches the kept steps.
_REPLAN_KEEP_RE = re.compile(r"\[\[REPLAN_KEEP=([^\]]*)\]\]", re.IGNORECASE)


def _parse_replan_keep(message: str) -> list[str] | None:
    """Parse the kept step ids from the card's re-plan token.
    Returns None if the token is absent (caller should keep ALL stored steps — safe
    default), or a list (possibly empty = user kept none) if the token is present."""
    m = _REPLAN_KEEP_RE.search(message or "")
    if not m:
        return None
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def _replan_base_subset(plan_dict: dict, keep_ids: list[str]) -> dict:
    """Exact subset of a plan to keep_ids (no defensive fallback — an empty keep list
    yields an empty base, unlike _subset_plan_dict). Keeps only the required_inputs the
    kept steps reference."""
    keep = {s for s in keep_ids if s}
    steps = [s for s in plan_dict.get("steps", []) if s.get("id") in keep]
    used: set[str] = set()
    for s in steps:
        for src in (s.get("inputs") or {}).values():
            if src.get("source") == "input" and src.get("ref"):
                used.add(src["ref"])
    reqs = [r for r in plan_dict.get("required_inputs", []) if r.get("id") in used]
    return {**plan_dict, "steps": steps, "required_inputs": reqs}


def _merge_added_steps(base: dict, added: dict) -> dict:
    """Append the LLM's NEW steps to the deterministically-kept base plan. Kept steps
    are never modified; colliding new step ids are renamed and their depends_on /
    source=step refs rewritten. New required_inputs whose id already exists in base are
    treated as a reuse (deduped)."""
    base_step_ids = {s.get("id") for s in base.get("steps", [])}
    base_input_ids = {r.get("id") for r in base.get("required_inputs", [])}

    new_inputs = [r for r in added.get("required_inputs", []) if r.get("id") not in base_input_ids]

    id_map: dict[str, str] = {}
    used_ids = set(base_step_ids)
    for s in added.get("steps", []):
        old = s.get("id") or "step"
        new = old
        i = 2
        while new in used_ids:
            new = f"{old}_{i}"
            i += 1
        id_map[old] = new
        used_ids.add(new)

    new_steps = []
    for s in added.get("steps", []):
        s = {**s, "id": id_map.get(s.get("id"), s.get("id"))}
        s["depends_on"] = [id_map.get(d, d) for d in (s.get("depends_on") or [])
                           if id_map.get(d, d) in used_ids]
        rewired = {}
        for param, src in (s.get("inputs") or {}).items():
            src = dict(src)
            if src.get("source") == "step" and src.get("ref") in id_map:
                src["ref"] = id_map[src["ref"]]
            rewired[param] = src
        s["inputs"] = rewired
        new_steps.append(s)

    merged_inputs = list(base.get("required_inputs", [])) + new_inputs

    # Auto-declare any input id a NEW step references but nobody declared. The model
    # generating "only the new step(s)" doesn't know the kept plan's input ids, so when
    # its new step also needs an existing file it often invents an undeclared id (e.g.
    # cost-benefit needs the flows table but refers to 'tourism_flows_csv', not the kept
    # 'flows_table'). Without this the merged plan is invalid ("references unknown
    # upload"). We add a proper upload slot using the tool's real file kind.
    known = {r.get("id") for r in merged_inputs}
    for s in new_steps:
        kinds = {sp[0]: sp[2] for sp in TOOL_FILE_SPECS.get(s.get("tool"), []) if len(sp) >= 3}
        for param, src in (s.get("inputs") or {}).items():
            if src.get("source") == "input" and src.get("ref") and src["ref"] not in known:
                ref = src["ref"]
                merged_inputs.append({
                    "id": ref,
                    "label": ref.replace("_", " ").strip().title() or ref,
                    "file_kind": kinds.get(param, "table"),
                    "description": "Auto-added: a file the added step needs — upload it here.",
                })
                known.add(ref)

    return {
        "case_name": base.get("case_name", "workflow"),
        "description": base.get("description", ""),
        "required_inputs": merged_inputs,
        "steps": list(base.get("steps", [])) + new_steps,
    }


def _apply_field_overrides(plan_dict: dict, overrides: list[dict]) -> dict:
    """Apply user-stated column/param overrides onto the plan's step literals before
    running. The planner fills column names from a few-shot (e.g. x_field='LON'); when
    the user uploads data with different columns and tells us the real names (x_field=
    'longitude'), we set them here so the run isn't blocked on a column mismatch.
    Numeric values for non-column params (capacity_per_trip='50') are coerced to numbers."""
    if not overrides:
        return plan_dict
    by_id = {s.get("id"): s for s in plan_dict.get("steps", [])}
    applied = []
    for ov in overrides:
        st = by_id.get(ov.get("step_id"))
        param, value = ov.get("param"), ov.get("value")
        if not st or not param or value is None:
            continue
        v = value
        if not param.endswith(("_field", "_attri", "_col")):
            try:
                v = int(value)
            except (TypeError, ValueError):
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    v = value
        st.setdefault("inputs", {})[param] = {"source": "literal", "value": v}
        applied.append(f"{ov['step_id']}.{param}={v}")
    if applied:
        logger.info(f"[agent] applied field_overrides: {', '.join(applied)}")
    return plan_dict


def _apply_file_overrides(plan_dict: dict, file_ovr: list[dict]) -> dict[str, str]:
    """Wire specific step file params directly to specific uploaded files, so a tool can
    read its OWN data file (e.g. CO2 reads a route/trip CSV, not the flows file the plan
    wired it to). Mutates plan_dict (adds a synthetic required_input + repoints the step's
    param) and returns {synthetic_input_id: file_path} to add to the execute inputs map."""
    extra: dict[str, str] = {}
    if not file_ovr:
        return extra
    by_id = {s.get("id"): s for s in plan_dict.get("steps", [])}
    applied = []
    for ov in file_ovr:
        st = by_id.get(ov.get("step_id"))
        param, fp = ov.get("param"), ov.get("file_path")
        if not st or not param or not fp:
            continue
        synth = f"_ovr__{ov['step_id']}__{param}"
        kinds = {sp[0]: sp[2] for sp in TOOL_FILE_SPECS.get(st.get("tool"), []) if len(sp) >= 3}
        st.setdefault("inputs", {})[param] = {"source": "input", "ref": synth}
        reqs = [r for r in plan_dict.get("required_inputs", []) if r.get("id") != synth]
        reqs.append({"id": synth, "label": os.path.basename(fp),
                     "file_kind": kinds.get(param, "table"),
                     "description": "Per-step file override."})
        plan_dict["required_inputs"] = reqs
        extra[synth] = fp
        applied.append(f"{ov['step_id']}.{param}={os.path.basename(fp)}")
    if applied:
        logger.info(f"[agent] applied file_overrides: {', '.join(applied)}")
    return extra


_KIND_EXTS = {
    "table": {".csv"},
    "vector": {".shp", ".geojson", ".gpkg"},
    "raster": {".tif", ".tiff", ".img", ".vrt", ".bil", ".asc", ".jp2"},
    "html": {".html", ".htm"},
    "shapefile-set": {".shp"},
}


def _name_tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 3}


def _csv_header_cols(path: str) -> set[str]:
    """Lower-cased column names from a CSV's header row (empty for non-CSV / unreadable)."""
    if not path.lower().endswith(".csv"):
        return set()
    try:
        import csv as _csv
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
            row = next(_csv.reader([fh.readline()]))
        return {c.strip().strip('"').strip().lower() for c in row if c.strip()}
    except Exception:
        return set()


_COL_PARAM_RE = re.compile(r"(_field|_fields|_attri|_variables|_col|_column)$")


def _expected_cols_by_input(plan) -> dict[str, set[str]]:
    """For each TABLE input id, the column names its consuming step references via literal
    column params (x_field='X', quantitative_variables='affin,gdplog,dist', ...). Lets
    auto-map bind a CSV input to the uploaded file that ACTUALLY has those columns — so two
    same-kind files (e.g. two *_Systems.csv, one with X/Y and one with LON/LAT) can't
    cross-bind when both happen to sit in the same session."""
    by_id = {ri.id: ri for ri in plan.required_inputs}
    out: dict[str, set[str]] = {}
    for st in plan.steps:
        cols: set[str] = set()
        for pname, src in st.inputs.items():
            if src.source == "literal" and _COL_PARAM_RE.search(pname or ""):
                val = src.value
                if isinstance(val, str) and val.strip():
                    cols |= {t.strip().lower() for t in val.split(",") if t.strip()}
        if not cols:
            continue
        for pname, src in st.inputs.items():
            if src.source == "input" and src.ref:
                ri = by_id.get(src.ref)
                if ri and (ri.file_kind or "table").lower() in ("table", "csv"):
                    out.setdefault(src.ref, set()).update(cols)
    return out


def _auto_map_inputs(plan, inputs_map: dict[str, str], uploaded: list[dict],
                     prefer_paths: set[str] | None = None) -> dict[str, str]:
    """Deterministically fill any required input the LLM did NOT map (or mapped to a
    nonexistent path) by matching the user's actually-uploaded files. Takes the fragile
    filename-matching out of the LLM's hands — e.g. required input 'systems_table' (table)
    auto-binds to the uploaded 'tourism_Systems.csv'.

    Scoring per (input, file), highest first:
      1. COLUMN match — if the step references literal columns (x_field='X', ...), the file
         whose header HAS them wins; a file missing them is pushed below (so an X/Y systems
         step never binds to a LON/LAT file even if both are in the session).
      2. CURRENT-BATCH — files uploaded in THIS turn (prefer_paths) beat leftovers from an
         earlier workflow in the same session (resolves ties like two flows CSVs that share
         FROM_X/TO_X columns — the one just uploaded with this run wins).
      3. name overlap (token intersection / jaccard / ratio).

    GLOBAL-GREEDY assignment (best pairs first) so a strong match is claimed before a weak
    one can steal its file."""
    import difflib
    prefer_paths = prefer_paths or set()
    by_id = {ri.id: ri for ri in plan.required_inputs}
    expected_cols = _expected_cols_by_input(plan)
    _hdr_cache: dict[str, set[str]] = {}
    used = {p for p in inputs_map.values() if p}
    need = [iid for iid in plan.input_ids
            if not (inputs_map.get(iid) and os.path.exists(inputs_map[iid]))]

    pairs = []  # (score, iid, path)
    for iid in need:
        ri = by_id.get(iid)
        kind = (ri.file_kind if ri else "table").lower()
        if "shp" in kind or "shape" in kind or "vector" in kind:
            kind = "vector"
        elif "rast" in kind or "tif" in kind:
            kind = "raster"
        exts = _KIND_EXTS.get(kind) or set().union(*_KIND_EXTS.values())  # unknown -> any data ext
        key_toks = _name_tokens(f"{iid} {ri.label if ri else ''} {ri.description if ri else ''}")
        want_cols = expected_cols.get(iid)
        for f in uploaded:
            path = f.get("path", "")
            if (os.path.splitext(f.get("filename", ""))[1].lower() not in exts
                    or path in used or not os.path.exists(path)):
                continue
            stem = os.path.splitext(os.path.basename(f["filename"]))[0]
            ft = _name_tokens(stem)
            inter = len(key_toks & ft)
            jacc = inter / (len(key_toks | ft) or 1)
            ratio = difflib.SequenceMatcher(None, iid.lower(), stem.lower()).ratio()
            col_match = 0
            if want_cols:
                if path not in _hdr_cache:
                    _hdr_cache[path] = _csv_header_cols(path)
                fcols = _hdr_cache[path]
                if fcols:
                    col_match = 1 if want_cols <= fcols else -1
            recent = 1 if path in prefer_paths else 0
            pairs.append(((col_match, recent, inter, jacc, ratio), iid, path))

    pairs.sort(key=lambda x: x[0], reverse=True)   # best matches first
    done_inputs: set[str] = set()
    for _score, iid, path in pairs:
        if iid in done_inputs or path in used:
            continue
        inputs_map[iid] = path
        done_inputs.add(iid)
        used.add(path)
        logger.info(f"[agent] auto-mapped input '{iid}' -> {os.path.basename(path)}")
    return inputs_map


# ---------------------------------------------------------------------------
# Keyword-based tool routing
# ---------------------------------------------------------------------------

_TOOL_KEYWORDS: dict[str, list[str]] = {
    "run_network_analysis_grouping":        ["network analysis", "flow network", "run_network_analysis"],
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
    fd.name: types.Tool(function_declarations=[fd])
    for tool in TOOLS
    for fd in tool.function_declarations
}

# Map each function name -> its FunctionDeclaration, so we can surface the tool's
# REAL parameter contract (names/types/required/descriptions) to the plan card UI
# instead of relying on the LLM's free-text file descriptions.
_FD_BY_NAME: dict[str, types.FunctionDeclaration] = {
    fd.name: fd
    for tool in TOOLS
    for fd in tool.function_declarations
}


def _tool_param_contract(tool: str) -> list[dict]:
    """The authoritative parameter contract for a tool, from its FunctionDeclaration
    (+ TOOL_FILE_SPECS for which params are files and their kind). Used by the plan
    card to show, per tool, exactly what files/params it takes."""
    fd = _FD_BY_NAME.get(tool)
    if fd is None or fd.parameters is None:
        return []
    props = fd.parameters.properties or {}
    required = set(fd.parameters.required or [])
    file_kinds = {spec[0]: spec[2] for spec in TOOL_FILE_SPECS.get(tool, []) if len(spec) >= 3}
    out: list[dict] = []
    for pname, pschema in props.items():
        ptype = getattr(pschema.type, "name", str(pschema.type)) if pschema.type is not None else ""
        out.append({
            "name": pname,
            "type": str(ptype),
            "required": pname in required,
            "is_file": pname in file_kinds,
            "file_kind": file_kinds.get(pname),
            "description": pschema.description or "",
        })
    return out


def _enrich_plan_for_ui(plan_dict: dict) -> dict:
    """Add UI-only metadata to the workflow_plan event:
      * tool_specs: {tool -> param contract}  (authoritative file/param info)
      * each step's depends_on REWRITTEN to the REAL data dependencies only — i.e.
        steps it actually consumes via a source=step input. The model's free-form
        depends_on is unreliable (it adds "logical order" edges with no data behind
        them), which made independent steps look serial/mixed. Basing the diagram on
        source=step means truly independent steps correctly show as parallel."""
    steps = plan_dict.get("steps", [])
    for s in steps:
        deps = set()
        for src in (s.get("inputs") or {}).values():
            if src.get("source") == "step" and src.get("ref"):
                deps.add(src["ref"])
        s["depends_on"] = sorted(deps)
    tools = {s.get("tool") for s in steps if s.get("tool")}
    return {t: _tool_param_contract(t) for t in tools if t}


def _detect_tool_from_message(message: str) -> str | None:
    """Return the function name that best matches the user message, or None."""
    msg_lower = message.lower()
    for tool_name, keywords in _TOOL_KEYWORDS.items():
        if any(kw.lower() in msg_lower for kw in keywords):
            return tool_name
    return None


_DIRECT_TOOL_ALIASES: dict[str, tuple[str, ...]] = {
    "run_model_selection_ols": (
        "ols",
        "run_ols",
        "run ols",
        "ordinary least squares",
        "ols model",
    ),
    "run_factor_analysis_mixed_data": ("famd", "run_famd", "factor analysis mixed data"),
    "run_co2_emissions": ("run_co2", "co2 emissions", "carbon dioxide emissions"),
    "run_cost_benefit_analysis": (
        "run_cba",
        "cost-benefit analysis",
        "cost benefit analysis",
        "cost-benefit function",
        "cost benefit function",
    ),
    "run_population_count_density": ("population count density", "population density"),
    "run_draw_radial_flows": ("draw radial flows", "radial flow"),
    "run_commodity_trade": ("commodity trade",),
    "run_add_agents_interactively": ("add agents",),
    "run_draw_agents_from_table": ("draw agents from table",),
    "run_add_causes_interactively": ("add causes",),
    "run_add_systems_interactively": ("add systems",),
    "run_draw_systems_from_table": ("draw systems from table",),
    "run_add_media_flows": ("add media flows",),
    "run_food_security": ("food security",),
    "run_nutrition_metrics": ("nutrition metrics",),
    "run_geographical_detector": ("geographical detector", "geographic detector"),
    "run_spatial_autocorrelation_moran": (
        "spatial autocorrelation",
        "moran's i",
        "morans i",
    ),
}

_DIRECT_COMPLETION_EXCLUDED_TOOLS = {
    "propose_workflow_plan",
    "execute_workflow_plan",
    "render_spatial_file",
    "render_telecoupling_scene",
    "read_file_content",
}

_DIRECT_COMPLETION_WORKFLOW_MARKERS = (
    "workflow",
    "pipeline",
    "multi-step",
    "multistep",
    "end-to-end",
    "多步",
    "工作流",
)

_RESULT_INTERPRETATION_MARKERS = (
    "interpret",
    "interpretation",
    "explain",
    "explanation",
    "summarize",
    "summarise",
    "summary",
    "analysis of the result",
    "discussion of the result",
    "description of the result",
    "review of the result",
    "overview of the result",
    "describe the result",
    "analyze the result",
    "analyse the result",
    "discuss the result",
    "what do the results mean",
    "what does the result mean",
    "解读",
    "解释",
    "总结",
)

_RESULT_RENDER_RE = re.compile(
    r"\b(render|visuali[sz]e|display|plot|map)\b|可视化|渲染|绘图",
    re.IGNORECASE,
)


def _message_contains_tool_alias(message: str, alias: str) -> bool:
    """Match aliases as tokens so one function name cannot prefix-match another."""
    start = r"(?<!\w)" if alias and (alias[0].isalnum() or alias[0] == "_") else ""
    end = r"(?!\w)" if alias and (alias[-1].isalnum() or alias[-1] == "_") else ""
    return re.search(f"{start}{re.escape(alias)}{end}", message) is not None


def _detect_unambiguous_direct_tool(message: str) -> str | None:
    """Return one explicitly requested tool, or None when intent is ambiguous."""
    msg_lower = (message or "").lower()
    matches: set[str] = set()
    for tool_name in _TOOL_BY_NAME:
        aliases = {
            tool_name.lower(),
            tool_name.removeprefix("run_").replace("_", " ").lower(),
        }
        aliases.update(alias.lower() for alias in _DIRECT_TOOL_ALIASES.get(tool_name, ()))
        aliases.update(keyword.lower() for keyword in _TOOL_KEYWORDS.get(tool_name, ()))
        if any(_message_contains_tool_alias(msg_lower, alias) for alias in aliases):
            matches.add(tool_name)
    if len(matches) == 1:
        return matches.pop()
    return None


def _direct_completion_tool_for_message(message: str) -> str | None:
    """Return the only tool eligible for deterministic post-tool completion."""
    msg_lower = (message or "").lower()
    if any(marker in msg_lower for marker in _DIRECT_COMPLETION_WORKFLOW_MARKERS):
        return None
    if any(marker in msg_lower for marker in _RESULT_INTERPRETATION_MARKERS):
        return None
    if _RESULT_RENDER_RE.search(message or ""):
        return None
    tool_name = _detect_unambiguous_direct_tool(message)
    if tool_name in _DIRECT_COMPLETION_EXCLUDED_TOOLS:
        return None
    return tool_name


def _format_direct_tool_completion(tool_result_event: dict) -> str:
    """Build the deterministic completion text shown after one successful tool."""
    file_count = len(tool_result_event.get("files") or [])
    if file_count == 0:
        output_text = "No output files were generated."
    elif file_count == 1:
        output_text = "1 output file was generated."
    else:
        output_text = f"{file_count} output files were generated."
    return (
        f"Analysis completed successfully. {output_text}\n\n"
        "To get an AI explanation, type: **Please interpret the results.**"
    )


# High-level analysis goals (use-case level, usually multi-tool) — when one of
# these is asked WITHOUT a specific single tool, Gemini Flash tends to narrate a
# plan in prose instead of calling propose_workflow_plan. We detect that intent
# and FORCE the function call (tool_config mode=ANY) so the plan card renders.
# Kept BROAD on purpose (any "analyze / assess / impact / case / study ..." request),
# because users phrase use-cases in open-ended ways (e.g. "分析航线对环境的影响").
_WORKFLOW_GOAL_KEYWORDS = [
    "telecoupling", "telecouple", "工作流", "workflow", "pipeline", "端到端", "end-to-end",
    "整套", "完整", "多步", "multi-step",
    "分析", "analyze", "analysis", "评估", "assess", "影响", "impact",
    "案例", "case study", "use case", "use-case", "研究", "量化", "模拟", "simulate",
    "情景", "scenario", "做一个", "做个", "帮我做",
]

# Exclusions — messages that look like an analysis word but must NOT spawn a NEW
# plan card: workflow confirmations / executions, references to existing results,
# and chit-chat / capability questions.
_WORKFLOW_GOAL_EXCLUSIONS = [
    "execute_workflow_plan", "selected_steps", "我确认", "确认运行", "确认并运行", "运行选中",
    "刚才的结果", "上一步", "这个结果", "这个输出", "之前的结果", "上面的结果",
    "你是谁", "你能做什么", "你好", "怎么用", "帮助",
    # Compositing telecoupling layers into ONE map is a single tool
    # (render_telecoupling_scene), NOT a workflow — don't spawn a plan card.
    "telecoupling map", "telecoupling scene", "combined telecoupling",
    "combine the flows", "combine flows", "into one map", "into a single map",
    "one combined map", "overlay the", "合成图", "合成一张", "叠成一张",
    "叠加成一张", "组合成一张", "一张总图", "叠在一起",
]


def _looks_like_workflow_goal(message: str) -> bool:
    """True if the message reads like a high-level, use-case analysis goal that
    should propose a workflow (and not a confirmation / result-reference / chit-chat)."""
    m = message.lower().replace(" ", "")
    if any(x.replace(" ", "") in m for x in _WORKFLOW_GOAL_EXCLUSIONS):
        return False
    return any(kw.replace(" ", "") in m for kw in _WORKFLOW_GOAL_KEYWORDS)


# Markers the plan card puts in its "confirm & run" message — used to FORCE
# execute_workflow_plan so a confirmation deterministically runs (instead of the
# model narrating "running it…" without calling the function).
_WORKFLOW_CONFIRM_MARKERS = ["execute_workflow_plan", "selected_steps", "确认并运行"]


def _looks_like_workflow_confirm(message: str) -> bool:
    m = message.lower()
    return any(x.lower() in m for x in _WORKFLOW_CONFIRM_MARKERS)


# Markers the plan card's "Add & re-plan" button puts in its message — used to FORCE
# add_workflow_steps so a re-plan deterministically generates ONLY the new step(s) and
# the backend merges them into the kept steps. (User-initiated refinement, not a submit.)
_WORKFLOW_REPLAN_MARKERS = ["add_workflow_steps", "[[replan_keep="]


def _looks_like_workflow_replan(message: str) -> bool:
    m = message.lower()
    return any(x.lower() in m for x in _WORKFLOW_REPLAN_MARKERS)


# A direct "render / visualize THIS spatial file" request. Requires BOTH a render
# verb AND a spatial-file reference (.shp/.tif/…), so a plain "visualize the
# output.shp" routes straight to render_spatial_file (single tool), while an
# open-ended "visualize the impact of X" analysis goal (no file ref) is NOT
# hijacked. Fixes Flash ALSO proposing a bogus workflow plan card (that
# references render_spatial_file, which is not a workflow tool) for a render.
_SPATIAL_FILE_RE = re.compile(r"\.(shp|tif|tiff|geojson|gpkg)\b", re.IGNORECASE)
_RENDER_VERBS = ("render", "visualize", "可视化", "渲染", "display", "plot", "show", "map")


def _looks_like_render_request(message: str) -> bool:
    if not _SPATIAL_FILE_RE.search(message):
        return False
    m = message.lower()
    return any(v in m for v in _RENDER_VERBS)


# Marker the frontend appends when the user's send carries freshly-attached files.
# Used (only when a workflow plan is already stored) to deterministically RUN the
# workflow on the "upload files + send" turn of the confirm→upload→run flow.
_FILES_ATTACHED_MARKER = "[[files_attached]]"


def _looks_like_files_attached(message: str) -> bool:
    return _FILES_ATTACHED_MARKER in (message or "").lower()


# A plain "run it" intent — used as a SECOND trigger so the run can be a TEXT-ONLY send
# (no files attached) when the files are already in the session. This decouples RUNNING
# from the fragile file-attached send (browser's "upload then open SSE" handoff sometimes
# fails to fire the chat). User: upload folder (files land server-side) → then just type
# "run the workflow" and send → this fires execute against the already-uploaded files.
_RUN_INTENT_KEYWORDS = [
    "run the workflow", "run the full workflow", "run the plan", "run all the steps",
    "run it", "run my", "run all", "execute the workflow", "execute the plan",
    "start the workflow", "go ahead and run", "运行", "执行", "开始跑", "跑起来", "跑工作流",
]


def _looks_like_run_intent(message: str) -> bool:
    m = (message or "").lower()
    return any(k in m for k in _RUN_INTENT_KEYWORDS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _maybe_await(result: Any) -> None:
    if asyncio.iscoroutine(result):
        await result


async def _dispatch_tool_and_relay(
    task_dispatcher: Any,
    *,
    tool_name: str,
    tool_input: dict,
    session_id: str,
    queue: str,
    event_callback: Callable[[dict], Any],
) -> tuple[str, dict]:
    """Subscribe before dispatch so fast worker results cannot be lost."""
    task_id = str(uuid.uuid4())
    channel = f"progress:{session_id}:{task_id}"
    r_sub = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r_sub.pubsub()
    subscribed = False

    try:
        await pubsub.subscribe(channel)
        subscribed = True
        try:
            async with asyncio.timeout(_PUBSUB_SUBSCRIBE_TIMEOUT):
                while True:
                    confirmation = await pubsub.get_message(
                        ignore_subscribe_messages=False,
                        timeout=1,
                    )
                    if (
                        confirmation
                        and confirmation.get("type") == "subscribe"
                        and confirmation.get("channel") == channel
                    ):
                        break
        except TimeoutError as exc:
            raise TimeoutError(
                f"Redis subscription for tool {task_id} was not confirmed"
            ) from exc

        celery_result = task_dispatcher.apply_async(
            args=[tool_name, tool_input, session_id],
            queue=queue,
            task_id=task_id,
        )
        if celery_result.id != task_id:
            raise RuntimeError(
                f"Celery returned unexpected task id {celery_result.id}"
            )
        logger.info(
            "[agent] Celery task dispatched: %s session=%s tool=%s",
            task_id,
            session_id,
            tool_name,
        )

        await _maybe_await(event_callback({
            "type": "tool_start",
            "tool": tool_name,
            "message": f"Starting {tool_name}...",
            "task_id": task_id,
        }))

        tool_result_event: dict = {}
        try:
            async with asyncio.timeout(_TOOL_EVENT_TIMEOUT):
                async for raw_msg in pubsub.listen():
                    if raw_msg["type"] != "message":
                        continue
                    try:
                        event = json.loads(raw_msg["data"])
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")
                    if event_type == "tool_start":
                        continue

                    await _maybe_await(event_callback(event))

                    if event_type == "tool_result":
                        tool_result_event = event
                    elif event_type == "done":
                        break
                    elif event_type == "error":
                        tool_error = RuntimeError(
                            event.get("message", "Tool execution failed")
                        )
                        tool_error.error_id = event.get("error_id")
                        raise tool_error
        except TimeoutError as exc:
            raise TimeoutError(
                f"Tool {task_id} timed out after {_TOOL_EVENT_TIMEOUT}s"
            ) from exc

        return task_id, tool_result_event
    finally:
        try:
            if subscribed:
                await pubsub.unsubscribe(channel)
        finally:
            await r_sub.aclose()


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
    session_manager: Any | None = None,
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
    if session_manager is None:
        raise ValueError("run_agent requires the application session manager")
    _sm = session_manager

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
        "render_telecoupling_scene":            "q_render",
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
    model_name = resolve_model_name(model)

    # Phase 1: build system instruction with PRE_EXECUTION skill sections
    pre_execution_context = _build_pre_execution_context()
    system_instruction = (
        "## Language (IMPORTANT)\n"
        "Always respond in ENGLISH — all explanations, summaries, and plan descriptions — "
        "regardless of the language the user writes in. Switch to another language ONLY if "
        "the user explicitly asks you to (for example, \"reply in Chinese\").\n"
        "Visible thought summaries shown in the Thought process UI must ALWAYS be English only. "
        "Never use Chinese, Japanese, or Korean characters in visible thought summaries, even when "
        "the user writes in another language.\n\n"
        + _BASE_SYSTEM_INSTRUCTION
        + "\n\n" + WORKFLOW_PROMPT
        + "\n\n" + CAPABILITY_CATALOG
        + pre_execution_context
    )

    # Build initial user message (uploaded + previous output file paths prepended)
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
        f for f in await _sm.get_uploaded_files(session_id)
        if f.get('path', '') not in current_paths
    ]
    if prev_uploaded:
        context_lines += [
            f"Previously uploaded file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in prev_uploaded
        ]
    output_files = await _sm.get_output_files(session_id)
    if output_files:
        context_lines += [
            f"Previous output file: {f.get('filename', 'unknown')} at {f.get('path', '')}"
            for f in output_files
        ]
    user_text = "\n".join(context_lines) + "\n\n" + message if context_lines else message
    # Deterministic routing is correctness behavior, independent of whether the
    # optional one-call completion response is enabled.
    requested_direct_tool = _direct_completion_tool_for_message(message)
    direct_completion_tool = (
        requested_direct_tool
        if settings.DIRECT_TOOL_COMPLETION_ENABLED
        else None
    )

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
    detected_tool_name = _detect_tool_from_message(user_text) or requested_direct_tool
    # Direct render request (render/visualize a specific .shp/.tif) → route to
    # render_spatial_file as the single iteration-0 tool, so Flash can't ALSO
    # emit a workflow plan card referencing render_spatial_file. Only when no
    # run_* tool was already keyword-detected.
    if detected_tool_name is None and _looks_like_render_request(user_text):
        detected_tool_name = "render_spatial_file"
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

    # Workflow forcing (Flash won't reliably call these functions in AUTO mode):
    #  * a card "confirm & run" message  -> force execute_workflow_plan
    #  * a high-level analysis goal       -> force propose_workflow_plan (renders the card)
    # Confirm takes precedence; single-tool keyword hits opt out of both.
    _force_confirm = _looks_like_workflow_confirm(user_text)
    # Only FORCE a brand-new plan card for the FIRST analysis goal in a session.
    # Once a plan has already been proposed this session, follow-up turns (uploading
    # files, "run any analysis you can", "complete the workflow") must NOT spawn a
    # fresh card. That was the "plan card keeps popping up every turn" bug: generic
    # words like "analysis"/"workflow" in normal follow-ups re-triggered propose on
    # every message. With a plan present we drop to AUTO so the model executes or
    # answers; the supplement/"change the plan" box still re-proposes (its message
    # names a tool / explicitly asks to re-propose), and WORKFLOW_PROMPT tells the
    # model to call execute (not re-propose) on follow-ups.
    _has_plan = await _sm.get_workflow_plan(session_id) is not None
    # The "Add & re-plan" button explicitly asks for a new plan card. Force propose
    # regardless of _has_plan / single-tool detection (it's a deliberate refinement).
    _force_replan = (not _force_confirm) and _looks_like_workflow_replan(user_text)
    _force_workflow = (not _force_confirm and not _force_replan and detected_tool_name is None
                       and not _has_plan
                       and _looks_like_workflow_goal(user_text))
    # Run flow: confirm the plan -> AI lists the files to upload -> the user uploads
    # files (+ states any column/param values) and sends. The frontend tags a send that
    # carries freshly-attached files with a marker; with a plan already stored (and not a
    # confirm / re-plan) that turn deterministically RUNS the workflow — Flash otherwise
    # narrates "running it…" without calling execute. field_overrides from the user's text
    # still apply. (A marker, not "session has any upload", so later follow-up questions
    # after a run don't re-trigger the whole workflow.)
    # Trigger execute when EITHER: the send carried fresh files (marker), OR it's a
    # plain "run it" with files already uploaded this session (text-only run — lets the
    # run sidestep the file-attached send entirely if that handoff flaked).
    _has_uploads = bool(await _sm.get_uploaded_files(session_id))
    _force_execute_on_upload = (_has_plan and not _force_confirm and not _force_replan
                                and (_looks_like_files_attached(user_text)
                                     or (_has_uploads and _looks_like_run_intent(user_text))))
    _forced_fn = ("execute_workflow_plan" if (_force_confirm or _force_execute_on_upload)
                  else "add_workflow_steps" if _force_replan
                  else "propose_workflow_plan" if _force_workflow else None)
    if _forced_fn:
        logger.info(f"[agent] forcing function call → {_forced_fn} "
                    f"(has_plan={_has_plan}, replan={_force_replan}, on_upload={_force_execute_on_upload})")

    # run_crop_pollination consistently returns empty content at temperature=0.
    # Start at 0.9 directly so it passes on the first call without retries.
    # (run_Sediment_Delivery_Ratio_SDR behaves inconsistently at 0.9 and recovers faster via retries at 0.)
    _HIGH_TEMP_TOOLS = {"run_crop_pollination"}
    base_temperature = 0.9 if detected_tool_name in _HIGH_TEMP_TOOLS else 0

    # Agentic loop
    max_iterations = 10
    # Supported Gemini reasoning models can stream summaries for the UI's
    # collapsible "Thinking…" block.
    thinking_cfg = (
        types.ThinkingConfig(include_thoughts=True)
        if _supports_thinking(model_name)
        else None
    )

    # After a plan card is proposed, run ONE more turn (functions disabled) to write
    # a short plain-language intro shown ABOVE the card (方案A layout). See below.
    explain_only_next = False
    workflow_execution_completed = False
    workflow_summary_only_next = False
    workflow_output_reads = 0

    for iteration in range(max_iterations):
        logger.info(f"[agent] iteration={iteration} session={session_id} model={model_name}")
        buffered_direct_text: list[dict] = []

        async def iteration_event_callback(event: dict) -> None:
            if (
                iteration == 0
                and direct_completion_tool is not None
                and event.get("type") == "text_chunk"
            ):
                buffered_direct_text.append(event)
                return
            await _maybe_await(event_callback(event))

        # Use the single-tool list on iteration 0 (when we know which tool to call),
        # then switch to full TOOLS list for follow-up iterations. A FORCED workflow
        # function must be in scope, so never narrow to a single tool when forcing
        # (e.g. a re-plan message that also mentions "cost-benefit" must still be able
        # to call propose_workflow_plan).
        if iteration == 0 and _forced_fn:
            active_tools = TOOLS
        elif iteration == 0 and _single_tool is not None:
            active_tools = _single_tool
        elif workflow_execution_completed:
            active_tools = [_TOOL_BY_NAME["read_file_content"]]
        else:
            active_tools = TOOLS

        # On iteration 0, force the relevant workflow function (propose or execute)
        # via mode=ANY restricted to that one function. Later iterations stay AUTO so
        # the model can summarize / answer normally. The post-plan "explain" turn
        # disables functions (mode=NONE) so it only writes the intro text.
        _tool_config = None
        if explain_only_next or workflow_summary_only_next:
            _tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="NONE")
            )
        elif iteration == 0 and _forced_fn:
            _tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=[_forced_fn],
                )
            )

        # Disable thinking when we FORCE a function call (mode=ANY): with thinking on,
        # reasoning models may stream only "thinking" parts and never emit the forced
        # function_call → an answer-less turn that retries fruitlessly (the workflow
        # "卡住 / only Thinking" symptom). No thinking on those turns = the call lands.
        _forcing_now = (iteration == 0 and _forced_fn is not None)
        gen_cfg = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=active_tools,
            temperature=base_temperature,
            # The post-plan explain turn (and any forced-call turn) shouldn't think.
            thinking_config=(
                None
                if (explain_only_next or workflow_summary_only_next or _forcing_now)
                else thinking_cfg
            ),
            tool_config=_tool_config,
        )

        response = await _generate_streaming(
            client,
            model_name,
            contents,
            gen_cfg,
            iteration_event_callback,
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
                resp2 = await _generate_streaming(
                    client,
                    model_name,
                    retry_contents,
                    retry_cfg,
                    iteration_event_callback,
                )
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

        direct_call_candidate = (
            iteration == 0
            and direct_completion_tool is not None
            and len(function_calls) == 1
            and function_calls[0].name == direct_completion_tool
        )
        if not direct_call_candidate:
            for buffered_event in buffered_direct_text:
                await _maybe_await(event_callback(buffered_event))

        if not function_calls:
            break

        function_response_parts: list[types.Part] = []
        workflow_proposed = False        # propose_workflow_plan is terminal for the turn
        direct_completion_result: dict | None = None
        plan_summary_fallback = ""

        for fc in function_calls:
            tool_name = fc.name
            tool_input = dict(fc.args)
            logger.info(f"[agent] function_call: {tool_name}")

            if workflow_execution_completed and tool_name != "read_file_content":
                logger.warning(
                    "[agent] blocked post-workflow function call: %s",
                    tool_name,
                )
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={
                            "error": (
                                "The workflow is complete. Do not run or render more tools; "
                                "summarize the completed results now."
                            )
                        },
                    )
                )
                workflow_summary_only_next = True
                continue

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
                # Enrich with the tools' real param contracts + complete the DAG
                # (depends_on ∪ source=step edges) so the card can show structure +
                # authoritative per-tool files/params.
                try:
                    tool_specs = _enrich_plan_for_ui(plan_dict)
                except Exception:
                    logger.exception("[agent] plan UI enrich failed")
                    tool_specs = {}
                await _maybe_await(event_callback({
                    "type": "workflow_plan",
                    "plan": plan_dict,
                    "valid": not plan_errors,
                    "errors": plan_errors,
                    "tool_specs": tool_specs,
                }))
                if plan_errors:
                    fr = {"status": "invalid_plan", "errors": plan_errors,
                          "instruction": "Fix these issues and call propose_workflow_plan again."}
                else:
                    # Stash the valid plan so a later confirm turn can execute it.
                    try:
                        await _sm.set_workflow_plan(session_id, plan_dict)
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

            # ── Deterministic re-plan: keep the user's chosen steps EXACTLY, take only
            # the LLM's NEW step(s), and merge. The model cannot re-add deselected steps.
            if tool_name == "add_workflow_steps":
                stored = await _sm.get_workflow_plan(session_id)
                keep_ids = _parse_replan_keep(user_text)   # None = token absent → keep all
                try:
                    added = plan_from_llm_args(tool_input)  # new steps + new required_inputs
                    if stored:
                        if keep_ids is None:
                            base = dict(stored)                                  # safe default: keep all
                        elif keep_ids:
                            base = _replan_base_subset(stored, keep_ids)         # keep the ticked ones
                        else:
                            base = {**stored, "steps": [], "required_inputs": []}  # kept none
                        plan_dict = _merge_added_steps(base, added)
                    else:
                        plan_dict = added                                        # no prior plan → fresh
                    plan = plan_from_dict(plan_dict)
                    plan_errors = validate_plan(plan, available_tools=set(TOOL_FILE_SPECS))
                except Exception as pe:
                    plan_dict = tool_input
                    plan_errors = [f"could not build updated plan: {pe}"]
                try:
                    tool_specs = _enrich_plan_for_ui(plan_dict)
                except Exception:
                    logger.exception("[agent] plan UI enrich failed")
                    tool_specs = {}
                await _maybe_await(event_callback({
                    "type": "workflow_plan", "plan": plan_dict,
                    "valid": not plan_errors, "errors": plan_errors, "tool_specs": tool_specs,
                }))
                if plan_errors:
                    fr = {"status": "invalid_plan", "errors": plan_errors,
                          "instruction": "Fix these issues and call add_workflow_steps again with corrected new step(s)."}
                else:
                    try:
                        await _sm.set_workflow_plan(session_id, plan_dict)
                    except Exception:
                        logger.exception("[agent] failed to stash merged workflow plan")
                    workflow_proposed = True
                    plan_summary_fallback = _format_plan_summary(plan_dict)
                    fr = {"status": "plan_updated", "n_steps": len(plan_dict.get("steps", [])),
                          "instruction": ("Updated plan saved. Briefly tell the user you ADDED the new "
                                          "step(s) to their kept steps (do not re-describe the kept steps "
                                          "in detail), and ask them to review the new card and confirm. "
                                          "Do NOT claim it has run.")}
                function_response_parts.append(
                    types.Part.from_function_response(name=tool_name, response={"result": fr})
                )
                continue

            # ── Workflow execution: run the confirmed plan (reconcile + stream each step).
            if tool_name == "execute_workflow_plan":
                stored = await _sm.get_workflow_plan(session_id)
                if not stored:
                    function_response_parts.append(types.Part.from_function_response(
                        name=tool_name, response={"result": {
                            "status": "no_plan",
                            "instruction": "No saved plan; call propose_workflow_plan first."}}))
                    continue
                # Plan-card multi-select: run only the steps the user ticked.
                selected_steps = [s for s in (tool_input.get("selected_steps") or []) if s]
                if selected_steps:
                    stored = _subset_plan_dict(stored, selected_steps)
                # Apply user-stated overrides so the run matches the user's ACTUAL data:
                #   * field_overrides — real column names / numeric params per step
                #   * file_overrides  — point a step at its own uploaded file (e.g. CO2's
                #                       route/trip CSV instead of the flows file)
                overrides = field_overrides_from_llm_args(tool_input)
                file_ovr = file_overrides_from_llm_args(tool_input)
                if overrides:
                    stored = _apply_field_overrides(stored, overrides)
                extra_inputs = _apply_file_overrides(stored, file_ovr)
                if overrides or file_ovr:
                    try:
                        await _sm.set_workflow_plan(session_id, stored)  # persist so a retry keeps them
                    except Exception:
                        logger.exception("[agent] failed to persist overrides")
                wf_plan = plan_from_dict(stored)
                if selected_steps:
                    dep_err = _subset_dep_error(wf_plan)
                    if dep_err:
                        function_response_parts.append(types.Part.from_function_response(
                            name=tool_name, response={"result": {
                                "status": "bad_subset", "error": dep_err,
                                "instruction": "Tell the user this dependency and ask them to adjust the selection."}}))
                        continue
                # File binding is DETERMINISTIC, not LLM-driven: the model's `inputs`
                # mapping has been unreliable (wrong/missing/hallucinated paths that also
                # poison auto-map's "already used" set). So we seed only with the user's
                # explicit file_overrides, then auto-map the rest from the session's real
                # uploads by kind + name overlap (validated 7/7 on the tourism set). The
                # LLM's `inputs` arg is used only as a last-resort fallback for any input
                # auto-map still couldn't fill.
                llm_inputs = input_map_from_llm_args(tool_input)
                inputs_map = dict(extra_inputs)   # file_overrides (explicit) win
                # Files attached to THIS run message = the current workflow's batch; prefer
                # them over leftovers from an earlier workflow in the same session.
                _cur_batch = {f.get("path") for f in files
                              if isinstance(f, dict) and f.get("current_batch")}
                try:
                    uploaded_files = await _sm.get_uploaded_files(session_id)
                    inputs_map = _auto_map_inputs(wf_plan, inputs_map,
                                                  uploaded_files,
                                                  prefer_paths=_cur_batch)
                except Exception:
                    logger.exception("[agent] auto-map inputs failed")
                for k, v in llm_inputs.items():   # fallback only where still unmapped
                    if k not in inputs_map and v and os.path.exists(v):
                        inputs_map[k] = v
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
                    await _sm.add_output_files(session_id, wf_ctx.get("files", []))
                except Exception:
                    pass

                workflow_execution_completed = wf_ctx.get("status") == "done"
                output_file_refs = [
                    {
                        "filename": f.get("filename"),
                        "internal_path": f.get("path"),
                    }
                    for f in wf_ctx.get("files", [])
                    if f.get("filename") and f.get("path")
                ]
                fr = {"status": wf_ctx.get("status"),
                      "steps": {sid: s.get("status") for sid, s in wf_ctx.get("steps", {}).items()},
                      "n_files": len(wf_ctx.get("files", [])),
                      "output_files": [f.get("filename") for f in wf_ctx.get("files", [])],
                      "output_file_refs": output_file_refs,
                      "warnings": wf_ctx.get("warnings", []),
                      "mismatches": wf_ctx.get("mismatches", []),
                      "instruction": (
                          "Summarize for the user which steps ran, key outputs, and any warnings. "
                          "You may use read_file_content for relevant CSV or text outputs. Do not "
                          "rerun the workflow or render spatial files. Output files are already shown "
                          "as cards above; do not re-list raw paths."
                      )}
                function_response_parts.append(types.Part.from_function_response(
                    name=tool_name, response={"result": fr}))
                continue

            # ── Step 0: generic pre-flight — catch missing input files before
            # dispatching, so the user gets a friendly "file not found / not
            # uploaded" message instead of a cryptic crash inside the worker.
            if tool_name in {
                "render_spatial_file",
                "render_telecoupling_scene",
                "read_file_content",
            }:
                from shared.file_reference_resolver import resolve_tool_file_references

                prior_files = (
                    await _sm.get_output_files(session_id)
                    + await _sm.get_uploaded_files(session_id)
                )
                tool_input = resolve_tool_file_references(
                    tool_name,
                    tool_input,
                    prior_files,
                )
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

            queue = _TOOL_QUEUES.get(tool_name, "q_default")
            try:
                task_id, tool_result_event = await _dispatch_tool_and_relay(
                    run_tool_task,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    session_id=session_id,
                    queue=queue,
                    event_callback=event_callback,
                )
                result_summary, post_skill_text = _build_function_response(
                    tool_name, tool_result_event
                )
                if (
                    direct_completion_tool == tool_name
                    and len(function_calls) == 1
                    and tool_result_event.get("type") == "tool_result"
                ):
                    direct_completion_result = tool_result_event
                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": result_summary},
                    )
                )
                if workflow_execution_completed and tool_name == "read_file_content":
                    workflow_output_reads += 1
                    if workflow_output_reads >= 8:
                        workflow_summary_only_next = True
                if post_skill_text:
                    function_response_parts.append(
                        types.Part.from_text(text=post_skill_text)
                    )

            except Exception as exc:
                logger.exception(f"[agent] Tool {tool_name} failed: {exc}")
                safe_msg = sanitize_error_message(str(exc))
                if not getattr(exc, "error_id", None):
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

        if direct_completion_result is not None:
            await _maybe_await(event_callback({
                "type": "text_chunk",
                "content": _format_direct_tool_completion(direct_completion_result),
            }))
            break

        # A proposed plan is terminal for this turn: stop now so we don't run a
        # second LLM turn (which would re-think and re-summarize -> duplicate plans).
        # The user confirms in the next message, which triggers execute_workflow_plan.
        if workflow_proposed:
            has_answer_text = any(
                getattr(p, "text", None) and not getattr(p, "thought", False)
                for p in candidate.content.parts
            )
            if has_answer_text:
                # Model already wrote an intro alongside the call — done.
                break
            # 方案A: the forced propose call emitted no text. Run ONE more turn with
            # functions DISABLED to write a short plain-language intro, which streams
            # in ABOVE the card (the frontend pins the plan card to the bottom of the
            # message). mode=NONE makes it impossible to re-propose / duplicate.
            # (candidate.content — the model's function_call turn — was already
            # appended above at line ~1671, so only the function response + nudge here.)
            contents.append(types.Content(role="user", parts=function_response_parts))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(
                text=("Write a clear, fairly detailed explanation (4–6 sentences) in ENGLISH "
                      "(unless the user explicitly asked for another language): first the overall idea and goal of this "
                      "analysis plan, then walk through each step in order — what it does and why "
                      "it's needed (organized around the telecoupling components: systems / flows / "
                      "effects / causes) — and note whether the steps run in parallel or have a "
                      "sequential dependency. Write for a non-technical user: clear and logical. "
                      "End by asking the user to tick the steps to run in the plan card below, "
                      "upload the needed files, and click Confirm. Do NOT list tool function names "
                      "or file parameter names (the card already has them). Do NOT call any function."))]))
            explain_only_next = True
            continue
        explain_only_next = False

        # Feed all function responses back to Gemini for final reply
        contents.append(
            types.Content(role="user", parts=function_response_parts)
        )

    await _maybe_await(event_callback({"type": "done"}))
