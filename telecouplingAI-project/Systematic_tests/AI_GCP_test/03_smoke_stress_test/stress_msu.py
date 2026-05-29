"""
MSU capacity-ladder wrapper around test_stress_50.py.

The original tool pool references an OLD GCP data layout (SampleData/,
NetworkAnalysisGrouping_input/) that does NOT exist on the current numbered-dir
Test_data. This wrapper trims the pool to tools that actually resolve now, so the
success rate reflects server capacity rather than missing-file errors.

  --pool fast   : 4 inline-CSV tools (OLS/CO2/CBA/Food) — fast compute, isolates
                  the backend (single uvicorn worker) + Gemini concurrency path.
  --pool mixed  : fast + 3 InVEST tools (urban_cooling/scenario_gen/forest_carbon)
                  — adds real Celery worker compute load.

Run (inside backend container, against the backend directly):
  cd /tmp/stress/03_smoke_stress_test
  CSIS_BASE_URL=http://localhost:8000 python stress_msu.py --users 50 --pool fast
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import test_stress_50 as S  # noqa: E402

FAST = {"T28_OLS", "T30_CO2", "T31_CBA", "T41_FoodSecurity"}
HEAVY = {"T15_UrbanCooling", "T23_ScenarioGen", "T27_ForestCarbon"}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=10)
    ap.add_argument("--pool", choices=["fast", "mixed"], default="fast")
    ap.add_argument("--window", type=int, default=30,
                    help="arrival window seconds (smaller = more simultaneous)")
    ap.add_argument("--tools-per-user", type=int, default=2)
    args = ap.parse_args()

    keep = FAST if args.pool == "fast" else (FAST | HEAVY)
    S.ALL_TOOLS = [t for t in S.ALL_TOOLS if t[0] in keep]
    S.NUM_USERS = args.users
    S.ARRIVAL_WINDOW = args.window
    S.TOOLS_PER_USER = args.tools_per_user

    print(f"POOL={args.pool}  tools={[t[0] for t in S.ALL_TOOLS]}  "
          f"users={args.users}  window={args.window}s  tools/user={args.tools_per_user}")
    asyncio.run(S.main(num_users=args.users))
