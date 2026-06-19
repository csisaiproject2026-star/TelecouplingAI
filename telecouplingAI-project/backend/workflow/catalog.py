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

## Few-shot: Wolong tourism telecoupling
Goal "analyze the Wolong tourism telecoupling" → 5 steps:
  1) run_draw_systems_from_table  (systems table; x_field=LON, y_field=LAT)
  2) run_network_analysis_grouping(nodes, links, world-countries shp;
       nodes_join_attri=CODE, layer_join_attri=ISO_3_CODE, clustering_algorithm=walktrap)
  3) run_draw_radial_flows        (flows table; from_x_field=FROM_X, from_y_field=FROM_Y,
       to_x_field=TO_X, to_y_field=TO_Y)
  4) run_co2_emissions            (flows-with-distance table; animal_count_field=Quantity,
       length_km_field=length_km, capacity_per_trip=1, co2_per_km_per_trip=29)
  5) run_factor_analysis_mixed_data (survey table; quantitative_variables="affin,gdplog,dist")
"""


# ---------------------------------------------------------------------------
# Routing rules — keep single-tool requests on the existing path.
# ---------------------------------------------------------------------------
WORKFLOW_PROMPT = """\
## Multi-step analysis (workflow planning)
If the user asks for a high-level ANALYSIS GOAL that needs **two or more tools chained**
(e.g. "analyze the Wolong tourism telecoupling", "do the full panda-loan analysis"),
do NOT call the tools one by one. Instead call `propose_workflow_plan` ONCE with the full
plan, then STOP and let the user confirm and upload the listed files.

Rules:
- If the request maps to a single tool, just call that tool directly (do NOT propose a plan).
- List EVERY file the whole analysis needs in `required_inputs` (the data manifest) so the
  user can upload them up front; you may also ask for them as you go if something is missing.
- Each step's `inputs` is an array; every item has a `param` and a `source`:
  source=input (ref = a required_inputs id), source=literal (value = column name or number),
  or source=step (ref = an earlier step id whose output feeds this input).
- After proposing the plan, summarize it for the user in plain language and ask them to
  confirm and provide the files. Do not claim it has run — it runs only after confirmation.

## Running the plan (only after the user confirms)
Once the user confirms AND the needed files are uploaded (their paths are listed at the top
of the message), call `execute_workflow_plan`. For EVERY required_inputs id, provide the
uploaded file path that fills it (match by filename / file kind). Do NOT call it before the
user confirms or before all needed files are present. After it runs, summarize the results.
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
        "id to the uploaded file path that fills it."
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
        },
        required=["inputs"],
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
