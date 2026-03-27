"""
CSIS Ecosystem Intelligence Platform — FastAPI backend.

Endpoints:
  POST   /api/chat                          SSE streaming chat (X-Session-ID header)
  POST   /api/upload                        File upload
  POST   /api/render/zoom                   QGIS zoom/pan re-render
  GET    /download/{session_id}/{path}      File download
  DELETE /api/sessions/{session_id}         Delete session and outputs
  GET    /health                            Health check
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import FastAPI, Form, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
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
    message: str = Form(...),
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

    # Save any uploaded files and build file context list
    uploaded = []
    if files:
        upload_dir = os.path.join(settings.UPLOADS_DIR, session_id)
        os.makedirs(upload_dir, exist_ok=True)
        for uf in files:
            if not uf.filename:
                continue
            dest = os.path.join(upload_dir, uf.filename)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(await uf.read())
            sm.add_uploaded_file(session_id, dest)
            uploaded.append({"filename": uf.filename, "path": dest})
            logger.info(f"[upload] {uf.filename} → {dest}")

    async def event_stream():
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def callback(event: dict):
            await queue.put(event)

        async def run():
            try:
                from agent import run_agent
                await run_agent(
                    message=message,
                    session_id=session_id,
                    files=uploaded,
                    event_callback=callback,
                    model=model,
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

        asyncio.create_task(run())

        while True:
            event = await queue.get()
            if event is None:
                break

            if event.get("type") == "tool_result":
                event = _enrich_file_urls(event, session_id)
                # Store output file paths in session for multi-turn context
                output_files = event.get("files", [])
                if output_files:
                    sm.add_output_files(session_id, [
                        {"filename": f["filename"], "path": f.get("path", "")}
                        for f in output_files if f.get("path")
                    ])

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
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

@app.post("/api/upload")
async def upload_endpoint(
    files: list[UploadFile] = File(...),
    x_session_id: str | None = Header(default=None),
):
    sm = get_session_manager()
    session_id = x_session_id or f"csis_{uuid.uuid4().hex}"
    if not sm.get_session(session_id):
        sm.create_session(session_id)

    upload_dir = os.path.join(settings.UPLOADS_DIR, session_id)
    os.makedirs(upload_dir, exist_ok=True)

    saved = []
    for uf in files:
        if not uf.filename:
            continue
        dest = os.path.join(upload_dir, uf.filename)
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await uf.read())
        sm.add_uploaded_file(session_id, dest)
        saved.append({"filename": uf.filename, "path": dest})
        logger.info(f"[upload] {uf.filename} → {dest}")

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
