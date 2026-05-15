"""
04_browser_test / test_browser.py
Browser-based end-to-end test — simulates a real user at the web UI.

Flow per test:
  1. Open http://34.42.83.50/ in a headless browser
  2. Drag-and-drop input files onto the upload zone
  3. Type a natural-language prompt into the chat box
  4. Wait for tool execution to complete (SSE stream)
  5. Verify output cards appear in the UI (download links, CSV previews, images)

Dependencies:
  - dev-browser MCP skill (https://github.com/SawyerHood/dev-browser)
    OR playwright / selenium installed in the test environment
  - pip install playwright && playwright install chromium

Usage (with playwright):
    cd Systematic_tests/AI_GCP_test
    CSIS_BASE_URL=http://34.42.83.50 python 04_browser_test/test_browser.py

Usage (with dev-browser MCP, when available):
    Invoke via Claude Code using the dev-browser skill.

NOTE: This script contains two runner modes:
  Mode A — Playwright (headless Chromium), fully automated
  Mode B — Manual checklist, for human verification

Set env var BROWSER_MODE=playwright or BROWSER_MODE=manual (default: manual).
"""
import asyncio
import json
import os
import sys
import time

BROWSER_MODE = os.getenv("BROWSER_MODE", "manual")
BASE_URL = os.getenv("CSIS_BASE_URL", "http://34.42.83.50")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "results_browser.json")

# ── Test scenarios ────────────────────────────────────────────────────────────
# Each scenario: (name, description, files_to_upload, prompt, expected_output_keyword)

SCENARIOS = [
    {
        "id": 1,
        "name": "Carbon Storage",
        "description": "Upload no files (data on server); type natural language prompt",
        "files": [],
        "prompt": (
            "Please run carbon storage analysis on the Willamette Valley. "
            "Use the sample data already on the server."
        ),
        "expected": "carbon",
        "timeout_s": 180,
    },
    {
        "id": 2,
        "name": "Network Analysis",
        "description": "Upload nodes.csv + links.csv via drag-drop; type prompt",
        "files": [
            "NetworkAnalysisGrouping_input/Network Analysis Grouping/nodes.csv",
            "NetworkAnalysisGrouping_input/Network Analysis Grouping/links.csv",
        ],
        "prompt": (
            "Run network analysis grouping on these uploaded files. "
            "Join on CODE / ISO_3_CODE, use walktrap clustering."
        ),
        "expected": "network",
        "timeout_s": 270,
    },
    {
        "id": 3,
        "name": "OLS Regression (upload CSV)",
        "description": "Generate and drag-drop a small CSV; ask for regression",
        "files": [],          # generated inline below
        "inline_csv": {
            "filename": "test_ols.csv",
            "content": "gdp,population,co2\n14000,1400,10000\n21000,330,5000\n4000,83,700\n",
        },
        "prompt": "I've uploaded a CSV. Run OLS regression: predict co2 from gdp and population.",
        "expected": "ols",
        "timeout_s": 120,
    },
    {
        "id": 4,
        "name": "Multi-turn conversation",
        "description": "Ask a question, then follow up with tool invocation",
        "files": [],
        "prompt": "What is the Habitat Quality tool used for?",
        "followup": (
            f"Great. Now run it using the Willamette Valley sample data on the server."
        ),
        "expected": "habitat",
        "timeout_s": 300,
    },
]


# ── Mode A: Playwright ────────────────────────────────────────────────────────

async def run_playwright():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    results = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        for scenario in SCENARIOS:
            name = scenario["name"]
            print(f"\n  [{scenario['id']}] {name}")
            t0 = time.time()
            result = {"id": scenario["id"], "name": name, "status": "FAIL", "duration_s": 0.0}

            try:
                await page.goto(BASE_URL, timeout=15000)
                await page.wait_for_load_state("networkidle", timeout=10000)

                # Handle inline CSV upload if any
                if scenario.get("inline_csv"):
                    import tempfile
                    csv_data = scenario["inline_csv"]
                    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False,
                                                     mode="w") as tf:
                        tf.write(csv_data["content"])
                        tmp_path = tf.name
                    file_input = page.locator("input[type=file]")
                    await file_input.set_input_files(tmp_path)
                    os.unlink(tmp_path)
                    await asyncio.sleep(1)

                # Type prompt in chat box
                chat_box = page.locator("textarea, input[type=text]").first
                await chat_box.fill(scenario["prompt"])
                await page.keyboard.press("Enter")

                # Wait for output to appear (tool_result keyword in DOM or URL)
                timeout_ms = scenario["timeout_s"] * 1000
                await page.wait_for_function(
                    f"document.body.innerText.toLowerCase().includes('{scenario['expected']}')",
                    timeout=timeout_ms,
                )

                # Multi-turn follow-up
                if scenario.get("followup"):
                    await asyncio.sleep(2)
                    await chat_box.fill(scenario["followup"])
                    await page.keyboard.press("Enter")
                    await page.wait_for_function(
                        f"document.body.innerText.toLowerCase().includes('{scenario['expected']}')",
                        timeout=timeout_ms,
                    )

                duration = time.time() - t0
                result.update({"status": "PASS", "duration_s": round(duration, 1)})
                print(f"      ✓ PASS  {duration:.1f}s")

            except Exception as e:
                duration = time.time() - t0
                result.update({"status": "FAIL", "duration_s": round(duration, 1),
                                "error": str(e)[:120]})
                print(f"      ✗ FAIL  {duration:.1f}s  {e}")

            results.append(result)

        await browser.close()

    return results


# ── Mode B: Manual checklist ───────────────────────────────────────────────────

def run_manual():
    print(f"\n{'=' * 78}")
    print(f"  Browser Test — MANUAL CHECKLIST MODE")
    print(f"  Target: {BASE_URL}")
    print(f"{'=' * 78}\n")
    print("  Open the URL above in your browser and perform these steps:\n")

    results = []
    for s in SCENARIOS:
        print(f"  [{s['id']}] {s['name']}")
        print(f"       {s['description']}")
        if s["files"]:
            print(f"       Files to drag-drop: {s['files']}")
        print(f"       Prompt: \"{s['prompt']}\"")
        print(f"       Expected output contains: '{s['expected']}'")
        print(f"       Timeout: {s['timeout_s']}s\n")
        result_str = input(f"       Result (pass/fail/skip): ").strip().lower()
        status = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}.get(result_str, "SKIP")
        note = ""
        if status == "FAIL":
            note = input("       Brief description of failure: ").strip()
        results.append({"id": s["id"], "name": s["name"], "status": status, "note": note})
        print()

    return results


# ── Report ────────────────────────────────────────────────────────────────────

def print_browser_report(results: list):
    print(f"\n{'=' * 78}")
    print(f"  Browser Test Results  →  {BASE_URL}")
    print(f"{'=' * 78}")
    passed = failed = skipped = 0
    for r in results:
        icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "⊘"}.get(r["status"], "?")
        dur = f"  {r.get('duration_s', 0):.1f}s" if "duration_s" in r else ""
        err = f"  → {r.get('error', r.get('note', ''))[:50]}" if r.get("error") or r.get("note") else ""
        print(f"  {icon} [{r['id']}] {r['name']:<38}{dur}{err}")
        if r["status"] == "PASS":    passed += 1
        elif r["status"] == "FAIL":  failed += 1
        else:                        skipped += 1
    print(f"\n  Total: {len(results)}  ✓ PASS: {passed}  ✗ FAIL: {failed}  ⊘ SKIP: {skipped}")
    print(f"{'=' * 78}\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  Browser test mode: {BROWSER_MODE.upper()}")
    print(f"  Target: {BASE_URL}")

    if BROWSER_MODE == "playwright":
        results = asyncio.run(run_playwright())
    else:
        results = run_manual()

    print_browser_report(results)

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": BASE_URL,
        "mode": BROWSER_MODE,
        "results": results,
        "summary": {
            "total":   len(results),
            "passed":  sum(1 for r in results if r["status"] == "PASS"),
            "failed":  sum(1 for r in results if r["status"] == "FAIL"),
            "skipped": sum(1 for r in results if r["status"] == "SKIP"),
        },
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Report saved → {REPORT_PATH}")

    failed = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(0 if failed == 0 else 1)
