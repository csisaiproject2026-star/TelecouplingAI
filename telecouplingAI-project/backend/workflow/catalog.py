"""
LLM planning layer for use-case workflows.

Provides three things agent.py wires in:
  * CAPABILITY_CATALOG  — text describing the workflow-relevant tools by telecoupling
                          component (+ a tourism few-shot), injected into the prompt.
  * WORKFLOW_PROMPT     — routing rules: when to propose a workflow vs. call one tool.
  * PROPOSE_WORKFLOW_PLAN_DECLARATION — the Gemini function the model calls to emit a plan.
  * plan_from_llm_args() — converts the function args (inputs as an array) to the
                           canonical plan dict consumed by workflow.schema.plan_from_dict.
"""
from __future__ import annotations

from google.genai import types


# ---------------------------------------------------------------------------
# Capability catalog — what the planner is allowed to chain, by component.
# Field-name params let a tool read arbitrary column names, so the planner maps
# the user's columns via `literal` inputs (no data rewriting needed).
# ---------------------------------------------------------------------------
CAPABILITY_CATALOG = """\
# Workflow capability catalog (telecoupling 5 components)

When composing a multi-step analysis, pick tools from this catalog. For each tool,
file inputs come from the user (source=input) and column/numeric settings are
source=literal. Wire one tool's output into another only when noted (source=step).

## How to decide each step's files / columns / params (READ THIS)
Drive every step from (a) the TOOL's contract below and (b) the USER's ACTUAL data —
NOT from any single example dataset. Concretely:
- Each tool reads column names from PARAMETERS (e.g. `animal_count_field`, `x_field`), so a
  tool works with ANY column names. The right value is the column that exists in the USER's
  uploaded file — never assume a column name just because an example used it.
- Give each tool the file IT needs (by role); two tools only share a file if it genuinely
  holds what both need. Don't reuse one file for a tool that needs different columns.
- If the user states column names / params (e.g. "x_field=longitude", "length_km_field=
  distance_km"), use exactly those (they flow through `field_overrides` at run time). If they
  don't, use the column actually present in their file (ask if unsure); only fall back to a
  tool's documented default when that default column is present.
- The tourism/Wolong example below is ONE dataset; treat its column names as placeholders.

## Systems (map the sending/receiving/spillover systems)
- run_draw_systems_from_table — point layer from a coordinate table.
  inputs: input_csv(file); x_field, y_field (literal: longitude/latitude column names).
- run_network_analysis_grouping — community-group entities by a flow network (R/igraph).
  inputs: nodes_table(file), links_table(file), shapefile_path(file/vector);
  nodes_join_attri, layer_join_attri (literal: the code column in nodes vs in the shapefile),
  clustering_algorithm (literal: 'walktrap' or 'spin_glass').

## Agents (map the people/orgs enabling a flow)
- run_draw_agents_from_table — point layer from an agent coordinate table.
  inputs: input_csv(file); x_field, y_field (literal).

## Flows (map flows between systems)
- run_draw_radial_flows — geodesic flow lines from origin/destination XY pairs.
  inputs: input_csv(file); from_x_field, from_y_field, to_x_field, to_y_field (literal).
- run_add_media_flows — flow lines from country mentions in an HTML report. inputs: input_html(file).

## Causes (factors behind a flow)
- run_factor_analysis_mixed_data — PCA/MCA/FAMD on survey-like variables (R/FactoMineR).
  inputs: input_csv(file); quantitative_variables and/or qualitative_variables
  (literal: comma-separated column names). Give at least one of the two.
- run_model_selection_ols — OLS model selection over candidate explanatory variables.

## Effects (quantify socioeconomic/environmental effects)
- run_co2_emissions — CO2 per transport route. NOTE: needs a distance column; the flow
  table must already have length_km (compute it if absent).
  inputs: input_csv(file); animal_count_field, length_km_field (literal: column names);
  capacity_per_trip, co2_per_km_per_trip (literal: numbers, e.g. 1 and 29).
- run_cost_benefit_analysis — net returns per system from cost/revenue data.
- run_habitat_quality — InVEST habitat degradation from LULC + threats (needs rasters).

## Few-shot: tourism telecoupling — STRUCTURE + column EXAMPLES (Wolong dataset)
This shows the typical STEP STRUCTURE with the column names from the Wolong tourism sample
data as a CONCRETE EXAMPLE. Use these exact names ONLY if the user's columns match; otherwise
replace each with the ACTUAL column in the user's uploaded file (or the name the user states).
Goal "analyze a tourism telecoupling" (however phrased — e.g. "旅游生态分析") → up to 5 steps:
  1) run_draw_systems_from_table  (systems coordinate table; x_field=LON, y_field=LAT)
  2) run_network_analysis_grouping(nodes, links, a country-polygon shapefile;
       nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap)
  3) run_draw_radial_flows        (flows table; from_x_field=FROM_X, from_y_field=FROM_Y,
       to_x_field=TO_X, to_y_field=TO_Y)
  4) run_co2_emissions            (a route/trip table with per-route counts + a distance column —
       the flows table already carrying a length_km column works; if the user has a SEPARATE
       co2/route file, use file_overrides to point this step at it; animal_count_field=Quantity,
       length_km_field=length_km, capacity_per_trip=1, co2_per_km_per_trip=29)
  5) run_factor_analysis_mixed_data (causes/survey table; quantitative_variables="affin,gdplog,dist")
(These column names are the Wolong example — adapt them to the user's actual data. Add or drop
steps to fit the user's goal and the files they actually have.)
"""


# ---------------------------------------------------------------------------
# Routing rules — keep single-tool requests on the existing path.
# ---------------------------------------------------------------------------
WORKFLOW_PROMPT = """\
## Multi-step analysis (workflow planning)
If the user asks for a high-level ANALYSIS GOAL that needs **two or more tools chained**
(e.g. "analyze a/this tourism telecoupling", "do the full panda-loan analysis"),
do NOT call the tools one by one. Instead call `propose_workflow_plan` ONCE with the full
plan, then STOP and let the user confirm and upload the listed files.

Rules:
- If the request maps to a single tool, just call that tool directly (do NOT propose a plan).
- List EVERY file the whole analysis needs in `required_inputs` (the data manifest) so the
  user can upload them up front; you may also ask for them as you go if something is missing.
  Give EACH required input a clear `description` that says what the file is AND its expected
  columns/format — e.g. "CSV of tourism systems with 'Name', 'LON', 'LAT' columns", or "flows
  CSV with 'FROM_X','FROM_Y','TO_X','TO_Y','Quantity','length_km' columns".
- Each step's `inputs` is an array; every item has a `param` and a `source`:
  source=input (ref = a required_inputs id), source=literal (value = column name or number),
  or source=step (ref = an earlier step id whose output feeds this input).
- After proposing the plan, summarize it for the user in plain language. For EVERY step, name
  the exact tool it uses by its call name — e.g. "绘制旅游系统: 使用 run_draw_systems_from_table
  工具, …". Then list each required input file with its description (what it is + which columns).
  Finally ask the user to confirm and upload the files. Do not claim it has run — it runs only
  after confirmation.

## Once a plan ALREADY exists (do NOT re-propose)
If you have ALREADY proposed a workflow plan earlier in this conversation, do NOT call
`propose_workflow_plan` again just because the user keeps talking about the analysis. The
plan card is already shown. Treat follow-up turns like this:
- User uploads files / says "run it" / "use the uploaded files" / "run any analysis you can"
  / confirms → call `execute_workflow_plan` (NOT propose). The card and existing plan stand.
- User asks to ADD an analysis to the current plan ("also add a cost-benefit analysis") →
  call `add_workflow_steps` with ONLY the new step(s). Do NOT re-list the kept steps — the
  backend keeps the user's selected steps and merges your new step(s) in.
- User asks to start a DIFFERENT analysis from scratch → call `propose_workflow_plan` anew.
- User just asks a question or chats → answer normally; do not call any of these.
Re-proposing the whole plan on every message spams the user with duplicate cards — avoid it.

## Running the plan (only after the user confirms)
Once the user confirms AND the needed files are uploaded (their paths are listed at the top
of the message), call `execute_workflow_plan`. For EVERY required_inputs id, provide the
uploaded file path that fills it (match by filename / file kind). Do NOT call it before the
user confirms or before all needed files are present. After it runs, summarize the results.
If the user's confirmation names a SUBSET of steps to run (the plan card sends the chosen
step ids), pass them as `selected_steps` so only those steps run; omit it to run all steps.
If the user states column/field names or parameter values for any step (e.g.
"x_field=longitude", "from_x_field=from_lon", "key_field=project_id", "capacity_per_trip=50"),
you MUST pass ALL of them in `field_overrides` (one entry per value, with the step id, the
tool parameter, and the value). The plan's default column names are guesses and often do NOT
match the user's uploaded file; without these overrides the run is blocked on a column mismatch.
If a step needs its OWN data file (different from the file the plan wired it to — e.g. the user
uploaded a separate CO2/route file with the count+distance columns), pass `file_overrides`
to point that step's file parameter at the correct uploaded file. Match each uploaded file to
the step whose columns it actually contains.
"""


# ---------------------------------------------------------------------------
# The function the model calls to emit a structured plan.
# inputs are modeled as an ARRAY (Gemini schemas don't support free-form maps).
# ---------------------------------------------------------------------------
_INPUT_ITEM = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "param":  types.Schema(type=types.Type.STRING, description="The tool parameter name."),
        "source": types.Schema(type=types.Type.STRING, description="'input', 'literal', or 'step'."),
        "ref":    types.Schema(type=types.Type.STRING, description="required_inputs id (source=input) or step id (source=step)."),
        "value":  types.Schema(type=types.Type.STRING, description="The literal value: a column name or a number-as-string (source=literal)."),
        "file":   types.Schema(type=types.Type.STRING, description="Optional: which produced file to take (source=step)."),
    },
    required=["param", "source"],
)

PROPOSE_WORKFLOW_PLAN_DECLARATION = types.FunctionDeclaration(
    name="propose_workflow_plan",
    description=(
        "Propose a multi-step telecoupling analysis plan (a chain of existing tools) for the "
        "user to confirm. Call this ONCE for high-level analysis goals needing >=2 tools. Do "
        "NOT call it for single-tool requests. The plan is NOT executed until the user confirms."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "case_name":   types.Schema(type=types.Type.STRING, description="Short slug for the case, e.g. 'wolong_tourism_telecoupling'."),
            "description": types.Schema(type=types.Type.STRING, description="One or two sentences describing the analysis."),
            "required_inputs": types.Schema(
                type=types.Type.ARRAY,
                description="The full data manifest: every file the whole analysis needs.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id":          types.Schema(type=types.Type.STRING, description="Short id referenced by step inputs."),
                        "label":       types.Schema(type=types.Type.STRING, description="Human label shown to the user."),
                        "file_kind":   types.Schema(type=types.Type.STRING, description="table | vector | raster | html."),
                        "description": types.Schema(type=types.Type.STRING, description="What this file is / required columns."),
                    },
                    required=["id", "label"],
                ),
            ),
            "steps": types.Schema(
                type=types.Type.ARRAY,
                description="Ordered steps; each runs one tool.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id":         types.Schema(type=types.Type.STRING, description="Step id, e.g. 's1_systems'."),
                        "tool":       types.Schema(type=types.Type.STRING, description="Exact tool call name, e.g. 'run_draw_radial_flows'."),
                        "component":  types.Schema(type=types.Type.STRING, description="systems | agents | flows | causes | effects."),
                        "rationale":  types.Schema(type=types.Type.STRING, description="Why this step."),
                        "depends_on": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Upstream step ids."),
                        "produces":   types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Expected output filenames."),
                        "inputs":     types.Schema(type=types.Type.ARRAY, items=_INPUT_ITEM, description="Parameter bindings."),
                    },
                    required=["id", "tool", "inputs"],
                ),
            ),
        },
        required=["case_name", "steps"],
    ),
)


EXECUTE_WORKFLOW_PLAN_DECLARATION = types.FunctionDeclaration(
    name="execute_workflow_plan",
    description=(
        "Run the workflow plan that was just proposed and confirmed by the user. Call ONLY "
        "after the user confirms and the required files are uploaded. Map each required_inputs "
        "id to the uploaded file path that fills it. If the user confirmed only a SUBSET of the "
        "steps (e.g. they ticked some boxes on the plan card), pass those step ids in "
        "`selected_steps`; only those steps run and only their files are needed."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "inputs": types.Schema(
                type=types.Type.ARRAY,
                description="One entry per required input: which uploaded file fills which manifest id.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "input_id":  types.Schema(type=types.Type.STRING, description="required_inputs id from the plan."),
                        "file_path": types.Schema(type=types.Type.STRING, description="Path of the uploaded file for this input."),
                    },
                    required=["input_id", "file_path"],
                ),
            ),
            "selected_steps": types.Schema(
                type=types.Type.ARRAY,
                description=("Optional. The step ids the user chose to run (from the plan card). "
                             "Omit to run the whole plan; provide a subset to run only those steps."),
                items=types.Schema(type=types.Type.STRING),
            ),
            "field_overrides": types.Schema(
                type=types.Type.ARRAY,
                description=(
                    "Optional but IMPORTANT. When the user states column/field names or parameter "
                    "values for any step (e.g. 'x_field=longitude', 'from_x_field=from_lon', "
                    "'capacity_per_trip=50'), pass EVERY one here so the plan runs against the "
                    "user's ACTUAL data columns instead of the plan's default guesses. The plan's "
                    "default column names often do NOT match the uploaded file — these overrides fix that."),
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "step_id": types.Schema(type=types.Type.STRING, description="Plan step id, e.g. 's1_systems'."),
                        "param":   types.Schema(type=types.Type.STRING, description="Tool parameter name, e.g. 'x_field'."),
                        "value":   types.Schema(type=types.Type.STRING, description="Override value: the actual column name in the uploaded file, or a number."),
                    },
                    required=["step_id", "param", "value"],
                ),
            ),
            "file_overrides": types.Schema(
                type=types.Type.ARRAY,
                description=(
                    "Optional. Point a specific step's FILE input at a specific uploaded file. "
                    "Use when a tool needs its OWN data file rather than the file the plan wired "
                    "it to — e.g. the CO2 step needs its own route/trip CSV (with counts + "
                    "distance), not the flows file. One entry per (step, file param)."),
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "step_id":   types.Schema(type=types.Type.STRING, description="Plan step id, e.g. 's4_co2_emissions'."),
                        "param":     types.Schema(type=types.Type.STRING, description="The tool's file parameter, e.g. 'input_csv'."),
                        "file_path": types.Schema(type=types.Type.STRING, description="Path of the uploaded file this step should read."),
                    },
                    required=["step_id", "param", "file_path"],
                ),
            ),
        },
        required=["inputs"],
    ),
)


def field_overrides_from_llm_args(args: dict) -> list[dict]:
    """execute_workflow_plan args -> [{step_id, param, value}] column/param overrides."""
    out: list[dict] = []
    for it in (args.get("field_overrides") or []):
        sid, p, v = it.get("step_id"), it.get("param"), it.get("value")
        if sid and p and v is not None:
            out.append({"step_id": sid, "param": p, "value": v})
    return out


def file_overrides_from_llm_args(args: dict) -> list[dict]:
    """execute_workflow_plan args -> [{step_id, param, file_path}] per-step file wiring.
    Lets a step read a SPECIFIC uploaded file directly (e.g. CO2 should read its own
    route/trip CSV, not the flows file the plan happened to wire it to)."""
    out: list[dict] = []
    for it in (args.get("file_overrides") or []):
        sid, p, fp = it.get("step_id"), it.get("param"), it.get("file_path")
        if sid and p and fp:
            out.append({"step_id": sid, "param": p, "file_path": fp})
    return out


ADD_WORKFLOW_STEPS_DECLARATION = types.FunctionDeclaration(
    name="add_workflow_steps",
    description=(
        "Generate ONLY the NEW step(s) to ADD to an existing plan for the extra analysis the "
        "user asked for (e.g. 'also add a cost-benefit analysis'). Do NOT repeat or re-list the "
        "user's existing/kept steps — the backend keeps those deterministically and merges your "
        "new steps in. Return just the new step(s) and any NEW required_inputs they need. The "
        "merged plan is shown for the user to confirm; it is NOT executed yet."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "required_inputs": types.Schema(
                type=types.Type.ARRAY,
                description="Only the NEW files the added step(s) need (not files the kept steps already use).",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id":          types.Schema(type=types.Type.STRING, description="Short id referenced by the new step inputs."),
                        "label":       types.Schema(type=types.Type.STRING, description="Human label shown to the user."),
                        "file_kind":   types.Schema(type=types.Type.STRING, description="table | vector | raster | html."),
                        "description": types.Schema(type=types.Type.STRING, description="What this file is / required columns."),
                    },
                    required=["id", "label"],
                ),
            ),
            "steps": types.Schema(
                type=types.Type.ARRAY,
                description="ONLY the new step(s) to add (one tool each). Do not include the kept steps.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "id":         types.Schema(type=types.Type.STRING, description="Step id for the new step, e.g. 's6_cba'."),
                        "tool":       types.Schema(type=types.Type.STRING, description="Exact tool call name, e.g. 'run_cost_benefit_analysis'."),
                        "component":  types.Schema(type=types.Type.STRING, description="systems | agents | flows | causes | effects."),
                        "rationale":  types.Schema(type=types.Type.STRING, description="Why this step."),
                        "depends_on": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Upstream step ids (usually none for an added independent analysis)."),
                        "produces":   types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING), description="Expected output filenames."),
                        "inputs":     types.Schema(type=types.Type.ARRAY, items=_INPUT_ITEM, description="Parameter bindings."),
                    },
                    required=["id", "tool", "inputs"],
                ),
            ),
        },
        required=["steps"],
    ),
)


def input_map_from_llm_args(args: dict) -> dict[str, str]:
    """execute_workflow_plan args -> {required_input_id: file_path}."""
    out: dict[str, str] = {}
    for it in args.get("inputs", []):
        iid, fp = it.get("input_id"), it.get("file_path")
        if iid and fp:
            out[iid] = fp
    return out


def plan_from_llm_args(args: dict) -> dict:
    """Convert propose_workflow_plan args (inputs as array) -> canonical plan dict."""
    steps = []
    for s in args.get("steps", []):
        inputs = {}
        for item in s.get("inputs", []):
            param = item.get("param")
            if not param:
                continue
            src = {"source": item.get("source", "literal")}
            if item.get("ref") is not None:
                src["ref"] = item["ref"]
            if item.get("value") is not None:
                src["value"] = item["value"]
            if item.get("file") is not None:
                src["file"] = item["file"]
            inputs[param] = src
        steps.append({
            "id": s.get("id"), "tool": s.get("tool"), "component": s.get("component", ""),
            "rationale": s.get("rationale", ""),
            "depends_on": list(s.get("depends_on", [])),
            "produces": list(s.get("produces", [])),
            "inputs": inputs,
        })
    return {
        "case_name": args.get("case_name", "workflow"),
        "description": args.get("description", ""),
        "required_inputs": list(args.get("required_inputs", [])),
        "steps": steps,
    }
