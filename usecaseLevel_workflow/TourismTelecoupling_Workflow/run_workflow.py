"""
Run the tourism WorkflowPlan through the deterministic engine (no LLM).

Usage:
    python run_workflow.py            # validate + execute
    python run_workflow.py --check    # validate only (no tool execution, no heavy deps)

Outputs go to ./_run_outputs/ (override via SHARED_DIR env). Network + FAMD steps
need R (Rscript + igraph/FactoMineR); the other four need only geopandas/pandas.
"""
import os
import sys
import json
import zipfile
import tempfile
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "SampleData_TourismTelecoupling")
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "telecouplingAI-project", "backend"))

# Point tool outputs/uploads at local folders BEFORE importing backend config.
os.environ.setdefault("SHARED_DIR", os.path.join(HERE, "_run_outputs"))
os.environ.setdefault("UPLOADS_DIR", os.path.join(HERE, "_run_uploads"))
os.makedirs(os.environ["SHARED_DIR"], exist_ok=True)
os.makedirs(os.environ["UPLOADS_DIR"], exist_ok=True)
sys.path.insert(0, BACKEND)


def unzip_shp(rel_zip: str) -> str:
    d = tempfile.mkdtemp(prefix="wf_")
    zipfile.ZipFile(os.path.join(SAMPLE, rel_zip)).extractall(d)
    shp = [f for f in os.listdir(d) if f.lower().endswith(".shp")][0]
    return os.path.join(d, shp)


def build_inputs() -> dict:
    return {
        "systems_table":      os.path.join(SAMPLE, "Systems-UploadSystems", "tourism_Systems.csv"),
        "agents_table":       os.path.join(HERE, "tourism_agents.csv"),
        "network_nodes":      os.path.join(SAMPLE, "Systems-NetworkGrouping", "nodes.csv"),
        "network_links":      os.path.join(SAMPLE, "Systems-NetworkGrouping", "links.csv"),
        "world_countries":    unzip_shp("Systems-NetworkGrouping/World_countries_2002.zip"),
        "flows_table":        os.path.join(SAMPLE, "Flows", "tourism_Flows.csv"),
        "flows_with_distance": os.path.join(HERE, "flows_with_distance.csv"),
        "famd_table":         os.path.join(HERE, "famd_input.csv"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only, no execution")
    args = ap.parse_args()

    from workflow import plan_from_dict, validate_plan
    from shared.tool_file_specs import TOOL_FILE_SPECS

    plan = plan_from_dict(json.load(open(os.path.join(HERE, "tourism_plan.json"), encoding="utf-8")))
    print(f"Plan: {plan.case_name}  ({len(plan.steps)} steps, {len(plan.required_inputs)} inputs)")

    errors = validate_plan(plan, available_tools=set(TOOL_FILE_SPECS))
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("VALIDATION: OK (all tools exist, all required inputs satisfied, order consistent)")

    if args.check:
        print("--check done (no execution).")
        return

    inputs = build_inputs()
    missing = {k: v for k, v in inputs.items() if not os.path.exists(v)}
    if missing:
        print("MISSING INPUT FILES:", missing)
        sys.exit(1)

    from workflow import run_plan

    def on_event(ev):
        t = ev.get("type")
        if t == "step_started":
            print(f"\n[{ev['index']}/{ev['total']}] >> {ev['step']}  ({ev['tool']}) -- {ev['rationale']}")
        elif t == "step_progress":
            print(f"    .. {ev['progress']}% {ev['message']}")
        elif t == "step_done":
            names = [f.get("filename") for f in ev["files"]]
            print(f"    [OK] {ev['step']} -> {names}" + (f"  WARNINGS={ev['warnings']}" if ev["warnings"] else ""))
        elif t == "step_error":
            print(f"    [ERR] {ev['step']}: {ev['error']}")
        elif t == "workflow_done":
            print(f"\n=== workflow {ev['status']} ===")

    ctx = run_plan(plan, inputs, session_id="tourism_selftest", event_cb=on_event)
    print("\nSUMMARY:")
    for sid, s in ctx["steps"].items():
        print(f"  {sid}: {s['status']}  ({len(s.get('outputs', []))} files)"
              + (f"  ERR={s['error']}" if s["status"] == "error" else ""))
    print(f"total files: {len(ctx['files'])}; status: {ctx.get('status')}")


if __name__ == "__main__":
    main()
