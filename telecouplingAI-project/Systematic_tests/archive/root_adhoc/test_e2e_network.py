"""
End-to-end API test for Tool 1: Network Analysis
Uses /api/chat with files attached (multipart), reads SSE stream.
"""
import json
import requests
import uuid

BASE = "http://localhost:8000"
SESSION_ID = f"test_{uuid.uuid4().hex[:8]}"

DATA_DIR = (
    r"C:\YPHOME\Jianan_Projects\Telecoupling_AI_Project\fulldev"
    r"\telecouplingAI-project\datainput_for_demo"
    r"\NetworkAnalysisGrouping_input\Network Analysis Grouping"
)

PROMPT = (
    "I have uploaded nodes.csv and links.csv for a network analysis. "
    "The nodes table has a CODE column. "
    "The links table has sender and receiver columns. "
    "The shapefile files (World_countries_2002) form the geographic basemap "
    "with an ISO_3_CODE column for spatial joining. "
    "Please run the Network Analysis using the walktrap clustering algorithm, "
    "joining nodes to the shapefile on the CODE column."
)

files_to_upload = [
    ("nodes.csv",                "text/csv"),
    ("links.csv",                "text/csv"),
    ("World_countries_2002.shp", "application/octet-stream"),
    ("World_countries_2002.dbf", "application/octet-stream"),
    ("World_countries_2002.prj", "application/octet-stream"),
    ("World_countries_2002.shx", "application/octet-stream"),
]

print(f"Session: {SESSION_ID}")
print("Uploading files + sending prompt via /api/chat SSE ...\n")

multipart = [
    ("message", (None, PROMPT)),
    ("model",   (None, "gemini-2.5-flash")),
]
for fname, mime in files_to_upload:
    path = f"{DATA_DIR}\\{fname}"
    multipart.append(("files", (fname, open(path, "rb"), mime)))

resp = requests.post(
    f"{BASE}/api/chat",
    files=multipart,
    headers={"X-Session-ID": SESSION_ID},
    stream=True,
    timeout=300,
)
resp.raise_for_status()

print(f"HTTP {resp.status_code}  (streaming SSE)\n{'='*60}")
for raw_line in resp.iter_lines():
    if not raw_line:
        continue
    line = raw_line.decode("utf-8")
    if not line.startswith("data: "):
        continue
    payload = line[6:]
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        print(f"[raw] {payload}")
        continue

    t = event.get("type", "?")
    if t == "text":
        print(f"[text]  {event.get('content','')[:200]}")
    elif t == "tool_start":
        print(f"[tool_start] {event.get('tool_name')}  task_id={event.get('task_id')}")
    elif t == "tool_progress":
        pct = event.get("progress", "?")
        msg = event.get("message", "")
        print(f"[progress] {pct}%  {msg}")
    elif t == "tool_result":
        files = event.get("files", [])
        print(f"[tool_result] success={event.get('success')}  files={[f['filename'] for f in files]}")
    elif t == "error":
        print(f"[ERROR] {event.get('message')}")
    elif t == "done":
        print("[done]")
        break
    else:
        print(f"[{t}] {str(event)[:200]}")
