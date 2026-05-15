"""
Shared utilities for CSIS GCP test suite.

Usage:
  export CSIS_BASE_URL=http://34.42.83.50   # default; set http://localhost when running ON GCP
  export CSIS_DOCKER_EXEC=tele-backend      # container name for docker exec output checks
"""
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import requests

BASE_URL       = os.getenv("CSIS_BASE_URL", "http://34.42.83.50")
DOCKER_EXEC    = os.getenv("CSIS_DOCKER_EXEC", "tele-backend")
DEMO           = "/data/datainput"   # container-internal data path
OUTPUTS        = "/data/outputs"     # container-internal output path
SD             = f"{DEMO}/SampleData"
DEFAULT_MODEL  = os.getenv("CSIS_MODEL", "gemini-2.5-flash")


def new_sid(prefix: str = "gcp") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_bytes(sid: str, files: list, timeout: int = 60) -> dict:
    """
    files: list of (filename, content_bytes, mimetype)
    Returns {filename: container_path}.
    """
    r = requests.post(
        f"{BASE_URL}/api/upload",
        files=[("files", (fname, content, mime)) for fname, content, mime in files],
        headers={"X-Session-ID": sid},
        timeout=timeout,
    )
    assert r.status_code == 200, f"Upload failed ({r.status_code}): {r.text[:200]}"
    return {f["filename"]: f["path"] for f in r.json()["uploaded"]}


def upload_local_paths(sid: str, paths: list, timeout: int = 60) -> dict:
    """Upload files from local filesystem paths."""
    open_files = []
    multipart = []
    for path in paths:
        fname = os.path.basename(path)
        mime = "image/tiff" if fname.endswith((".tif", ".tiff")) else "text/csv"
        fh = open(path, "rb")
        open_files.append(fh)
        multipart.append(("files", (fname, fh, mime)))
    try:
        r = requests.post(
            f"{BASE_URL}/api/upload",
            files=multipart,
            headers={"X-Session-ID": sid},
            timeout=timeout,
        )
        assert r.status_code == 200, f"Upload failed ({r.status_code}): {r.text[:200]}"
        return {f["filename"]: f["path"] for f in r.json()["uploaded"]}
    finally:
        for fh in open_files:
            fh.close()


# ── Chat / SSE ────────────────────────────────────────────────────────────────

def stream_chat(sid: str, message: str, timeout: int = 300,
                verbose: bool = True) -> list:
    """POST /api/chat, stream SSE until 'done' or 'error'. Returns all event dicts."""
    events = []
    t0 = time.time()
    try:
        with requests.post(
            f"{BASE_URL}/api/chat",
            data={"message": message, "model": DEFAULT_MODEL},
            headers={"X-Session-ID": sid},
            timeout=timeout,
            stream=True,
        ) as r:
            assert r.status_code == 200, f"Chat {r.status_code}: {r.text[:200]}"
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    payload = json.loads(raw[5:].strip())
                except json.JSONDecodeError:
                    continue
                elapsed = time.time() - t0
                etype = payload.get("type", "?")
                if verbose:
                    if etype == "tool_start":
                        print(f"  [{elapsed:.1f}s] tool_start: {payload.get('tool_name','')}")
                    elif etype == "tool_result":
                        fcount = len(payload.get("files", []))
                        print(f"  [{elapsed:.1f}s] tool_result: success={payload.get('success')} files={fcount}")
                    elif etype == "error":
                        print(f"  [{elapsed:.1f}s] ERROR: {str(payload.get('message',''))[:100]}")
                events.append(payload)
                if etype in ("done", "error"):
                    break
    except requests.exceptions.ChunkedEncodingError:
        pass  # SSE dropped by nginx timeout — task may still be running
    return events


def events_success(events: list) -> bool:
    """True if a tool_result event exists with files OR success=True. False on error."""
    for e in events:
        if e.get("type") == "error":
            return False
        if e.get("type") == "tool_result":
            # success may be None/True/False — treat as pass if files were produced
            if e.get("success") or len(e.get("files", [])) > 0:
                return True
    return False


def events_output_files(events: list) -> list:
    for e in events:
        if e.get("type") == "tool_result":
            return [f["filename"] for f in e.get("files", [])]
    return []


def events_error_msg(events: list) -> Optional[str]:
    for e in events:
        if e.get("type") == "error":
            return str(e.get("message", "unknown"))
    return None


# ── Output file count via docker exec ────────────────────────────────────────

def count_output_files(sid: str) -> list:
    """Returns list of output file paths for this session (requires docker on PATH)."""
    import subprocess
    result = subprocess.run(
        ["docker", "exec", DOCKER_EXEC, "find", f"{OUTPUTS}/{sid}", "-type", "f"],
        capture_output=True, text=True, timeout=10,
    )
    return [f for f in result.stdout.strip().splitlines() if f]


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class ToolTestResult:
    tool_id:      int
    tool_name:    str
    status:       str          # PASS / FAIL / SKIP / ERROR
    duration_s:   float = 0.0
    output_files: list = field(default_factory=list)
    error:        Optional[str] = None
    note:         str = ""

    def to_dict(self) -> dict:
        return {
            "tool_id":      self.tool_id,
            "tool_name":    self.tool_name,
            "status":       self.status,
            "duration_s":   round(self.duration_s, 1),
            "output_files": len(self.output_files),
            "error":        self.error,
            "note":         self.note,
        }


def print_results_table(results: list, title: str = "Results"):
    print(f"\n{'=' * 78}")
    print(f"  {title}")
    print(f"{'=' * 78}")
    print(f"  {'ID':>3}  {'Tool':<34}  {'Status':<6}  {'Sec':>6}  {'Files':>5}  Notes")
    print(f"  {'-'*3}  {'-'*34}  {'-'*6}  {'-'*6}  {'-'*5}  {'-'*20}")
    for r in results:
        err_note = f"  {r.error[:40]}" if r.error else (f"  {r.note}" if r.note else "")
        print(f"  {r.tool_id:>3}  {r.tool_name:<34}  {r.status:<6}  "
              f"{r.duration_s:>6.1f}  {len(r.output_files):>5}{err_note}")
    print()
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    errored = sum(1 for r in results if r.status == "ERROR")
    total = len(results)
    print(f"  Total: {total}  ✓ PASS: {passed}  ✗ FAIL: {failed}  "
          f"⊘ SKIP: {skipped}  ✕ ERROR: {errored}")
    print(f"{'=' * 78}\n")
    return passed, failed, skipped


def save_results_json(results: list, path: str):
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url":  BASE_URL,
        "summary": {
            "total":   len(results),
            "passed":  sum(1 for r in results if r.status == "PASS"),
            "failed":  sum(1 for r in results if r.status == "FAIL"),
            "skipped": sum(1 for r in results if r.status == "SKIP"),
            "errored": sum(1 for r in results if r.status == "ERROR"),
        },
        "results": [r.to_dict() for r in results],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  → Results saved to {path}")


# ── Metrics ───────────────────────────────────────────────────────────────────

@dataclass
class MetricSample:
    ts:           float
    cpu_pct:      float
    mem_used_mb:  float
    mem_total_mb: float
    net_rx_mb:    float
    net_tx_mb:    float


def _proc_stat():
    with open("/proc/stat") as f:
        line = f.readline()
    vals = [int(x) for x in line.split()[1:]]
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return idle, sum(vals)


def _meminfo_mb():
    info: dict = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":")
            info[k.strip()] = int(v.split()[0])
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return (total - avail) / 1024, total / 1024


def _net_mb(iface: str = "eth0"):
    try:
        with open("/proc/net/dev") as f:
            for line in f:
                if iface in line:
                    cols = line.split()
                    return int(cols[1]) / 1048576, int(cols[9]) / 1048576
    except Exception:
        pass
    return 0.0, 0.0


async def metrics_collector(samples: list, stop: asyncio.Event, interval: float = 5.0):
    try:
        prev_idle, prev_total = _proc_stat()
    except FileNotFoundError:
        return   # not on Linux — skip metrics
    await asyncio.sleep(interval)
    while not stop.is_set():
        try:
            idle, total = _proc_stat()
            d_idle = idle - prev_idle
            d_total = total - prev_total
            cpu_pct = 100.0 * (1 - d_idle / d_total) if d_total else 0.0
            prev_idle, prev_total = idle, total
            mu, mt = _meminfo_mb()
            rx, tx = _net_mb()
            samples.append(MetricSample(time.time(), cpu_pct, mu, mt, rx, tx))
        except Exception:
            pass
        await asyncio.sleep(interval)


def print_metrics(samples: list, wall_time: float):
    if not samples:
        print("  (no metrics — not running on Linux)\n")
        return
    import statistics
    cpu_vals = [s.cpu_pct for s in samples]
    mem_vals = [s.mem_used_mb for s in samples]
    mem_total = samples[0].mem_total_mb
    rx_delta = samples[-1].net_rx_mb - samples[0].net_rx_mb
    tx_delta = samples[-1].net_tx_mb - samples[0].net_tx_mb
    dur_min = wall_time / 60
    print(f"  CPU:  avg {statistics.mean(cpu_vals):.1f}%  peak {max(cpu_vals):.1f}%")
    print(f"  RAM:  avg {statistics.mean(mem_vals):.0f} MB  "
          f"peak {max(mem_vals):.0f} MB  / {mem_total:.0f} MB total")
    print(f"  Net:  RX {rx_delta:.2f} MB  TX {tx_delta:.2f} MB  "
          f"over {dur_min:.1f} min")


def percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = (len(s) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)
