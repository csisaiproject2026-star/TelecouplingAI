"""Measure the per-call INPUT token footprint of the agent, using count_tokens
(does NOT consume the generate_content paid-tier token quota).

Run inside the backend container with cwd=/app:
  cd /app && python /tmp/measure_tokens.py
"""
import json
import os
import sys

sys.path.insert(0, "/app")
import agent  # noqa: E402
from google.genai import types  # noqa: E402

client = agent._get_client()
MODEL = os.getenv("CSIS_MODEL", "gemini-2.5-flash")


def count(contents, config=None):
    r = client.models.count_tokens(model=MODEL, contents=contents, config=config)
    return r.total_tokens


base = agent._BASE_SYSTEM_INSTRUCTION
pre = agent._build_pre_execution_context()
full_sys = base + pre
TOOLS = agent.TOOLS

out = {"model": MODEL, "n_tools": len(TOOLS)}

# ── component text counts (always work) ─────────────────────────────
out["base_system_tokens"] = count(base)
out["full_system_instruction_tokens"] = count(full_sys)
out["pre_execution_skills_tokens"] = out["full_system_instruction_tokens"] - out["base_system_tokens"]

# Tier A: lazy single-tool skill loading (only the detected tool's skill)
try:
    one_pre = agent._build_pre_execution_context(only_tool="run_model_selection_ols")
    one_sys = base + one_pre
    out["single_tool_system_instruction_tokens"] = count(one_sys)
    out["single_tool_skill_tokens"] = out["single_tool_system_instruction_tokens"] - out["base_system_tokens"]
except Exception as e:
    out["single_tool_error"] = repr(e)[:160]

sample_user = ("Run OLS on uploaded ols.csv: dependent_variable=co2, "
               "independent_variables=gdp,pop,forest. Run immediately.")
out["sample_user_tokens"] = count(sample_user)

# ── tools schema tokens (try config; fallback to JSON-string estimate) ──
try:
    out["all_tools_schema_tokens"] = count(sample_user, config=types.CountTokensConfig(tools=TOOLS))
    out["all_tools_schema_method"] = "count_tokens(config.tools) minus user"
    out["all_tools_schema_tokens"] -= out["sample_user_tokens"]
except Exception as e:
    out["all_tools_schema_error"] = repr(e)[:160]
    try:
        decls = []
        for t in TOOLS:
            for fd in (t.function_declarations or []):
                decls.append(fd.to_json_dict() if hasattr(fd, "to_json_dict") else str(fd))
        out["all_tools_schema_tokens_jsonstr_estimate"] = count(json.dumps(decls))
    except Exception as e2:
        out["all_tools_schema_fallback_error"] = repr(e2)[:160]

# ── realistic per-call input (system + all tools + a user turn) ──────
try:
    cfg = types.CountTokensConfig(system_instruction=full_sys, tools=TOOLS)
    out["full_followup_call_input_tokens"] = count(sample_user, config=cfg)
    out["full_call_method"] = "count_tokens(system_instruction + tools + user)"
except Exception as e:
    out["full_call_error"] = repr(e)[:160]

print(json.dumps(out, indent=2))
