"""
Locust load test for CSIS Platform — 30-50 concurrent users.

Install:
    pip install locust

Run (headless, 40 users, ramp 5/s, 2 minutes):
    locust -f tests/locustfile.py --headless -u 40 -r 5 -t 2m --host http://localhost

Run (web UI at http://localhost:8089):
    locust -f tests/locustfile.py --host http://localhost
"""
import io
import json
import uuid

from locust import HttpUser, between, task


def new_sid():
    return f"load_{uuid.uuid4().hex[:8]}"


class CSISUser(HttpUser):
    """
    Simulates a typical user session:
      - health check (lightest, high frequency)
      - file upload (medium)
      - delete session (lightweight cleanup)
      - chat greeting (heaviest — real Gemini call, low frequency)
    """
    wait_time = between(1, 3)   # realistic pause between requests
    host = "http://localhost"

    def on_start(self):
        """Assign a unique session ID per simulated user."""
        self.sid = new_sid()

    # ── weight=5 → runs ~5× more often than weight=1 ────────────────────────

    @task(10)
    def health_check(self):
        with self.client.get("/health", name="GET /health",
                             catch_response=True) as r:
            if r.status_code != 200 or r.json().get("status") != "ok":
                r.failure(f"Unexpected: {r.status_code} {r.text[:80]}")

    @task(5)
    def upload_file(self):
        content = b"col1,col2\n" + b"1,2\n" * 50   # ~500 bytes
        with self.client.post(
            "/api/upload",
            files=[("files", (f"{uuid.uuid4().hex}.csv",
                               io.BytesIO(content), "text/csv"))],
            headers={"X-Session-ID": self.sid},
            name="POST /api/upload",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Upload failed: {r.status_code} {r.text[:80]}")

    @task(3)
    def delete_session(self):
        """Create a throwaway session and delete it — tests Redis round-trip."""
        sid = new_sid()
        with self.client.delete(
            f"/api/sessions/{sid}",
            name="DELETE /api/sessions/{sid}",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Delete failed: {r.status_code}")

    @task(2)
    def chat_greeting(self):
        """
        Lightweight chat: a plain greeting that should NOT trigger any tool.
        Reads the full SSE stream and checks for at least one event.
        """
        with self.client.post(
            "/api/chat",
            data={"message": "Hi, just say hello back."},
            headers={"X-Session-ID": self.sid},
            name="POST /api/chat (greeting)",
            catch_response=True,
            timeout=90,
            stream=False,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Chat returned {r.status_code}")
                return
            # Verify SSE stream has at least one data line
            has_event = any(
                line.startswith("data:")
                for line in r.text.splitlines()
            )
            if not has_event:
                r.failure("SSE stream contained no data events")

    @task(1)
    def download_missing(self):
        """
        Intentionally request a non-existent file — expects 404.
        Tests that the download path doesn't crash under load.
        """
        with self.client.get(
            f"/download/{self.sid}/no_such_file.csv",
            name="GET /download (missing)",
            catch_response=True,
        ) as r:
            if r.status_code == 404:
                r.success()
            else:
                r.failure(f"Expected 404, got {r.status_code}")
