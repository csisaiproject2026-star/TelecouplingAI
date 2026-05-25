"""
UX regression test for the 2026-05-25 frontend changes on http://34.42.83.50/:

  Test A — On load the app opens a fresh empty "New Chat"; prior conversations
           stay in the sidebar (they are NOT auto-restored as the active chat).
  Test B — When an old conversation is reopened, download links whose server
           file is gone render an "expired" hint (HEAD->404), live links stay
           clickable, and a dead preview image shows a "Preview expired" card.

Runs headless Chromium. No backend/LLM calls — state is injected via localStorage.
"""
import json
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL = "http://34.42.83.50/"
LIVE = ("http://34.42.83.50/download/csis_8113a750-33cb-4d2e-869d-620cce65bb29/"
        "20260516_025738_scenic_quality/intermediate/visibility_11.tif")
DEAD = "http://34.42.83.50/download/__nonexistent__/ghost.tif"
DEAD_IMG = "http://34.42.83.50/download/__nonexistent__/preview.png"

results = []
def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def seed(page, chats):
    """Overwrite csis_chats in localStorage then reload."""
    page.evaluate("c => localStorage.setItem('csis_chats', JSON.stringify(c))", chats)
    page.reload(wait_until="networkidle")


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")

        # ---- Test A: fresh chat on load -----------------------------------
        print("\nTest A — fresh New Chat on load, history preserved")
        seed(page, [{
            "id": "old1", "title": "My Old Conversation",
            "messages": [
                {"role": "user", "content": "hello", "file": None},
                {"role": "assistant", "blocks": [{"type": "text", "content": "hi there"}]},
            ],
        }])
        body = page.inner_text("body")
        # Active (main) area should be the empty-state welcome, not the old text.
        check("welcome screen shown (active chat is empty)",
              "How can I help you today?" in body)
        check("old text 'hi there' NOT in active view",
              "hi there" not in body)
        # Sidebar keeps the prior conversation + a fresh New Chat entry.
        check("sidebar still lists 'My Old Conversation'",
              "My Old Conversation" in body)
        check("a fresh 'New Chat' entry exists", "New Chat" in body)

        # ---- Test B: expired link marking ---------------------------------
        print("\nTest B — expired download link / image marking")
        seed(page, [{
            "id": "res1", "title": "Result Chat",
            "messages": [
                {"role": "user", "content": "run scenic quality", "file": None},
                {"role": "assistant", "blocks": [
                    {"type": "text", "content": "Here are your results."},
                    {"type": "file_download", "files": [
                        {"filename": "ghost.tif", "url": DEAD, "render_type": "download"},
                        {"filename": "visibility_11.tif", "url": LIVE, "render_type": "download"},
                    ]},
                    {"type": "image", "url": DEAD_IMG, "filename": "preview.png"},
                ]},
            ],
        }])
        # Fresh chat is active; click the old conversation in the sidebar.
        page.get_by_text("Result Chat", exact=True).first.click()
        page.wait_for_timeout(2500)  # let HEAD probes + img onError resolve

        view = page.inner_text("body")
        check("dead download shows 'expired — re-run to regenerate'",
              "expired — re-run to regenerate" in view)
        check("dead image shows 'Preview expired'",
              "Preview expired" in view)
        # Live file remains a clickable download link (anchor with href=LIVE).
        live_links = page.locator(f"a[href='{LIVE}']").count()
        check("live file still a clickable link", live_links >= 1,
              f"{live_links} anchor(s)")
        # The live filename must NOT be struck through as expired: ensure the
        # expired hint count equals the number of dead files (1), not 2.
        expired_hits = view.count("expired — re-run to regenerate")
        check("only the dead file is marked expired (not the live one)",
              expired_hits == 1, f"{expired_hits} expired hint(s)")

        browser.close()


if __name__ == "__main__":
    try:
        run()
    except PWTimeout as e:
        print(f"TIMEOUT: {e}")
        sys.exit(2)
    passed = sum(1 for _, c, _ in results if c)
    total = len(results)
    print(f"\n==== {passed}/{total} checks passed ====")
    sys.exit(0 if passed == total else 1)
