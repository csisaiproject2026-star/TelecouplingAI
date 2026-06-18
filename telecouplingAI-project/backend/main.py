"""
CSIS Ecosystem Intelligence Platform — FastAPI backend.

Endpoints:
  POST   /api/chat                          SSE streaming chat (X-Session-ID header)
  POST   /api/upload                        File upload (supports folder uploads w/ relative paths)
  POST   /api/render/zoom                   QGIS zoom/pan re-render
  GET    /download/{session_id}/{path}      File download
  POST   /api/download_zip/{session_id}     Bundle a specific set of result files into one ZIP
  DELETE /api/sessions/{session_id}         Delete session and outputs
  GET    /health                            Health check
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import tempfile
import uuid
import zipfile
from pathlib import Path

from starlette.background import BackgroundTask

# Catch LLM-hallucinated inline base64 image data so it never gets persisted
# into chat history (the frontend already blocks rendering, but we don't want
# multi-KB junk haunting future turns or session JSON dumps).
_INLINE_BASE64_IMG_RE = re.compile(
    r'!?\[[^\]]*\]\(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]{50,}\)'
    r'|data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]{50,}',
    re.IGNORECASE,
)

# Strip absolute filesystem paths (Linux container paths like /data/outputs/...,
# /app/..., /tmp/...) from anything the AI writes back to the user — only the
# filename should survive. The system prompt already forbids this but Gemini
# leaks paths anyway, so we enforce it on the wire.
_LEAK_PATH_RE = re.compile(
    r'(?:/(?:data|app|tmp|home|opt|var|root|mnt)/)[\w./\-]+?/([\w\-.]+\.[A-Za-z0-9]{1,6})'
)

import aiofiles
from fastapi import FastAPI, Form, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
import uvicorn

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CSIS Ecosystem Intelligence Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Lazy init — session_manager created after startup check passes
_session_manager = None


def get_session_manager():
    global _session_manager
    if _session_manager is None:
        from shared.session_manager import SessionManager
        _session_manager = SessionManager()
    return _session_manager


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_check() -> None:
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set. Check your .env file.")
    os.makedirs(settings.SHARED_DIR, exist_ok=True)
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    logger.info("CSIS backend started ✅")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/chat — SSE streaming
# ---------------------------------------------------------------------------

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(""),
    model: str = Form(None),
    files: list[UploadFile] = File(default=[]),
    x_session_id: str | None = Header(default=None),
):
    sm = get_session_manager()

    # Resolve or create session
    session_id = x_session_id or f"csis_{uuid.uuid4().hex}"
    session = sm.get_session(session_id)
    if not session:
        sm.create_session(session_id)
    else:
        sm.touch_session(session_id)

    # If no message but files were uploaded, generate a sensible default prompt
    if not message or not message.strip():
        if files:
            message = "I have uploaded these files. Please analyze them and suggest which InVEST models I can run, or describe what they contain."
        else:
            async def empty_prompt_stream():
                yield ServerSentEvent(
                    data=json.dumps(
                        {'type': 'error', 'message': 'Please input prompt to let me know how to process it', 'error_code': 'EMPTY_PROMPT'},
                        ensure_ascii=False,
                    ),
                    id="0",
                )
            return EventSourceResponse(
                empty_prompt_stream(),
                headers={"X-Session-ID": session_id, "X-Accel-Buffering": "no"},
            )

    # Save any uploaded files and build file context list
    uploaded = []
    unsupported_files = []
    supported_extensions = {'.tif', '.tiff', '.shp', '.geojson', '.gpkg', '.csv', '.dbf', '.prj', '.shx', '.cpg', '.qpj', '.sbx', '.sbn', '.xml', '.html', '.htm'}

    if files:
        upload_dir = os.path.join(settings.UPLOADS_DIR, session_id)
        os.makedirs(upload_dir, exist_ok=True)
        for uf in files:
            if not uf.filename:
                continue

            # Check file extension
            file_ext = Path(uf.filename).suffix.lower()
            if file_ext not in supported_extensions:
                unsupported_files.append(uf.filename)
                logger.info(f"[upload] Skipped unsupported file: {uf.filename}")
                continue

            dest = os.path.join(upload_dir, uf.filename)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(await uf.read())
            sm.add_uploaded_file(session_id, dest)
            uploaded.append({"filename": uf.filename, "path": dest})
            logger.info(f"[upload] {uf.filename} → {dest}")

    # Include files previously uploaded via /api/upload in this session
    session_data = sm.get_session(session_id)
    if session_data:
        existing_paths = {f["path"] for f in uploaded}
        for f in sm.get_uploaded_files(session_id):
            if f["path"] not in existing_paths:
                uploaded.append(f)

    # Retrieve prior conversation history and save the current user turn
    chat_history = sm.get_chat_history(session_id)
    sm.add_chat_turn(session_id, "user", message)

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def callback(event: dict):
            await queue.put(event)

        async def run():
            try:
                # Send warning for unsupported files
                if unsupported_files:
                    await queue.put({
                        "type": "warning",
                        "message": f"Unsupported file types skipped: {', '.join(unsupported_files)}. Supported formats: .tif, .tiff, .shp, .geojson, .gpkg, .csv, .html",
                        "skipped_files": unsupported_files,
                    })

                from agent import run_agent
                await run_agent(
                    message=message,
                    session_id=session_id,
                    files=uploaded,
                    event_callback=callback,
                    model=model,
                    chat_history=chat_history,
                )
            except Exception as exc:
                import traceback as _tb
                err_msg = str(exc) or f"{type(exc).__name__}: (no message)"
                logger.exception(f"[chat] agent error [{type(exc).__name__}]: {err_msg}\n{_tb.format_exc()}")
                await queue.put({
                    "type": "error",
                    "message": err_msg,
                    "error_code": "AGENT_FAILED",
                })
            finally:
                await queue.put(None)  # sentinel

        agent_task = asyncio.create_task(run())

        ai_text_parts: list[str] = []
        event_seq = 0  # monotonic id per event — enables Last-Event-ID resume in Tier 3
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break

                if event.get("type") == "text_chunk":
                    content = event.get("content", "")
                    # Defensive sanitization: strip absolute paths and
                    # hallucinated inline base64 images before the chunk goes
                    # to the user or into chat history.
                    content = _LEAK_PATH_RE.sub(r'\1', content)
                    content = _INLINE_BASE64_IMG_RE.sub('[inline image suppressed]', content)
                    event = {**event, "content": content}
                    ai_text_parts.append(content)

                if event.get("type") == "tool_result":
                    event = _enrich_file_urls(event, session_id)
                    # Store output file paths in session for multi-turn context
                    output_files = event.get("files", [])
                    if output_files:
                        sm.add_output_files(session_id, [
                            {"filename": f["filename"], "path": f.get("path", "")}
                            for f in output_files if f.get("path")
                        ])

                yield ServerSentEvent(
                    data=json.dumps(event, ensure_ascii=False),
                    id=str(event_seq),
                )
                event_seq += 1

            # Save the model's reply so future turns can reference this exchange.
            # Strip any hallucinated inline base64 image data first so it doesn't
            # bloat the session JSON or leak into subsequent prompts.
            ai_text = "".join(ai_text_parts)
            if ai_text:
                ai_text = _INLINE_BASE64_IMG_RE.sub('[inline image suppressed]', ai_text)
                sm.add_chat_turn(session_id, "model", ai_text)
        finally:
            # Client disconnected or stream ended — cancel the agent task to
            # prevent zombie coroutines and "Task was destroyed but pending" errors.
            # Note: the Celery worker task keeps running independently in the
            # background regardless of this cancellation.
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except (asyncio.CancelledError, Exception):
                    pass

    # EventSourceResponse(ping=15) emits a comment frame ": ping\n\n" every 15s
    # whenever the generator is idle. That defeats MSU WAF idle timeouts (which
    # otherwise sever the connection during long tool runs and surface as a
    # "Failed to fetch" in the browser).
    return EventSourceResponse(
        event_stream(),
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-ID": session_id,
        },
    )


def _enrich_file_urls(event: dict, session_id: str) -> dict:
    """Add download URLs to files in a tool_result event."""
    files = event.get("files", [])
    if not files:
        return event
    enriched = []
    base = settings.FILE_SERVER_URL.rstrip("/")
    for f in files:
        full_path = f.get("path", "")
        try:
            rel = Path(full_path).relative_to(settings.SHARED_DIR)
            url = f"{base}/{rel.as_posix()}"
        except ValueError:
            url = f"{base}/{session_id}/{f.get('filename', '')}"
        enriched.append({**f, "url": url})
    return {**event, "files": enriched}


# ---------------------------------------------------------------------------
# POST /api/upload — standalone file upload (without chat)
# ---------------------------------------------------------------------------

def _safe_relpath(rel: str, fallback: str) -> str:
    """Turn a browser webkitRelativePath into a safe relative path.

    Folder uploads (``<input webkitdirectory>``) send each file's path relative
    to the chosen folder (e.g. ``Input/habitat_layers/eelgrass.tif``). We keep
    that structure so CSV files that reference sibling files by relative path
    still resolve — but we strip anything that could escape the upload dir
    (leading slashes, ``..`` segments, a Windows drive prefix).
    """
    rel = (rel or "").replace("\\", "/").strip()
    parts = [seg for seg in rel.split("/") if seg not in ("", ".", "..")]
    if parts and len(parts[0]) == 2 and parts[0][1] == ":":   # drop "C:" etc.
        parts = parts[1:]
    if not parts:
        return os.path.basename(fallback) or "file"
    return "/".join(parts)


@app.post("/api/upload")
async def upload_endpoint(
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(default=[]),
    x_session_id: str | None = Header(default=None),
):
    sm = get_session_manager()
    session_id = x_session_id or f"csis_{uuid.uuid4().hex}"
    if not sm.get_session(session_id):
        sm.create_session(session_id)

    upload_dir = os.path.join(settings.UPLOADS_DIR, session_id)
    os.makedirs(upload_dir, exist_ok=True)
    upload_root = Path(upload_dir).resolve()

    saved = []
    for i, uf in enumerate(files):
        if not uf.filename:
            continue
        # When a whole folder is uploaded, the parallel `paths` field carries
        # each file's relative path so we can recreate the sub-directory layout.
        rel = _safe_relpath(paths[i] if i < len(paths) else "", uf.filename)
        dest = os.path.join(upload_dir, *rel.split("/"))
        # Defence-in-depth: never let a crafted path escape the session dir.
        if not str(Path(dest).resolve()).startswith(str(upload_root)):
            rel = os.path.basename(uf.filename)
            dest = os.path.join(upload_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await uf.read())
        sm.add_uploaded_file(session_id, dest)
        saved.append({"filename": rel, "path": dest})
        logger.info(f"[upload] {rel} → {dest}")

    return {"session_id": session_id, "uploaded": saved}


# ---------------------------------------------------------------------------
# POST /api/render/zoom — QGIS zoom/pan re-render
# ---------------------------------------------------------------------------

@app.post("/api/render/zoom")
async def render_zoom(
    file_path: str = Form(...),
    output_path: str = Form(...),
    extent: str = Form(None),       # JSON array [xmin, ymin, xmax, ymax]
    width: int = Form(1920),
    height: int = Form(1080),
    x_session_id: str | None = Header(default=None),
):
    """Re-render a spatial file with a specific extent (zoom/pan)."""
    from renderers.qgis_renderer import render_with_extent, render_file

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"Source file not found: {file_path}")

    try:
        if extent:
            extent_list = json.loads(extent)
            result_path = await render_with_extent(file_path, output_path, extent_list, width, height)
        else:
            result_path = await render_file(file_path, output_path, width, height)
    except Exception as exc:
        logger.exception(f"[render/zoom] failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    session_id = x_session_id or ""
    base = settings.FILE_SERVER_URL.rstrip("/")
    try:
        rel = Path(result_path).relative_to(settings.SHARED_DIR)
        url = f"{base}/{rel.as_posix()}"
    except ValueError:
        url = f"{base}/{session_id}/{Path(result_path).name}"

    return {"output_path": result_path, "url": url}


# ---------------------------------------------------------------------------
# GET /download/{session_id}/{path} — file download
# ---------------------------------------------------------------------------

@app.get("/download/{session_id}/{file_path:path}")
async def download_file(session_id: str, file_path: str):
    shared_root = Path(settings.SHARED_DIR).resolve()
    full_path = Path(settings.SHARED_DIR, session_id, file_path).resolve()
    if not str(full_path).startswith(str(shared_root)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(full_path), filename=full_path.name)


# ---------------------------------------------------------------------------
# POST /api/download_zip/{session_id} — bundle a SPECIFIC set of result files
# ---------------------------------------------------------------------------

class ZipRequest(BaseModel):
    paths: list[str] = []   # internal paths of the files to bundle (one tool run)


@app.post("/api/download_zip/{session_id}")
def download_zip(session_id: str, req: ZipRequest):
    """Stream a ZIP of exactly the files the caller lists — scoped to one result
    card (one tool run), NOT the whole session.

    Each requested path is re-validated to live under this session's output dir
    (blocks traversal / grabbing another session). Sync def → FastAPI runs it in
    a threadpool so zipping big rasters never blocks the event loop; the temp zip
    is removed after the response via a BackgroundTask.
    """
    shared_root = Path(settings.SHARED_DIR).resolve()
    session_root = (shared_root / session_id).resolve()

    seen: set[str] = set()
    members: list[tuple[str, str]] = []   # (abs_path, name_inside_zip)
    for p in req.paths:
        if not p or p in seen:
            continue
        seen.add(p)
        abs_p = Path(p).resolve()
        try:                              # must live under THIS session's dir
            abs_p.relative_to(session_root)
        except ValueError:
            continue
        if not abs_p.is_file():           # skip anything cleaned up / expired
            continue
        members.append((str(abs_p), abs_p.relative_to(session_root).as_posix()))

    if not members:
        raise HTTPException(
            status_code=404,
            detail="No result files available to download (they may have expired).",
        )

    tmp = tempfile.NamedTemporaryFile(prefix="csis_results_", suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_p, arc in members:
            zf.write(abs_p, arcname=arc)

    logger.info(f"[download_zip] {len(members)} files → {tmp_path} ({session_id})")
    return FileResponse(
        tmp_path,
        media_type="application/zip",
        filename=f"csis_results_{session_id[:12]}.zip",
        background=BackgroundTask(os.unlink, tmp_path),
    )


# ---------------------------------------------------------------------------
# DELETE /api/sessions/{session_id}
# ---------------------------------------------------------------------------

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    get_session_manager().delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
