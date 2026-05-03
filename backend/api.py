"""
backend/api.py — BookRevive FastAPI Backend (Memory Optimised + Streaming)
--------------------------------------------------------------------------
Streams progress back to the frontend so users see real-time updates.
Processes images one at a time and clears memory between pages.
"""

from __future__ import annotations

import gc
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import anthropic
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

from core.epub import convert_to_epub
from core.merger import PageData, merge_pages
from core.ocr import ocr_image
from utils.image_prep import assess_image_quality, preprocess_image

app = FastAPI(
    title="BookRevive API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_ROOT = Path(tempfile.gettempdir()) / "bookrevive"
SESSION_ROOT.mkdir(parents=True, exist_ok=True)


def _session_dir(session_id: str) -> Path:
    d = SESSION_ROOT / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cleanup_session(session_id: str) -> None:
    d = SESSION_ROOT / session_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _verify_clerk_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        return f"anon_{uuid.uuid4().hex[:16]}"
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return f"anon_{uuid.uuid4().hex[:16]}"
    session_id = token[:32].replace(".", "_").replace("-", "_")
    return session_id


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "bookrevive-api"}


@app.post("/process")
async def process_images(
    files: list[UploadFile] = File(...),
    title: str = Form(default="Untitled Book"),
    author: str = Form(default="Unknown Author"),
    language: str = Form(default="en"),
    fix_spelling: bool = Form(default=False),
    authorization: Optional[str] = Header(default=None),
    x_anthropic_key: Optional[str] = Header(default=None),
):
    session_id = _verify_clerk_token(authorization)
    session_dir = _session_dir(session_id)

    anthropic_client = None
    if x_anthropic_key and x_anthropic_key.strip():
        try:
            anthropic_client = anthropic.Anthropic(api_key=x_anthropic_key.strip())
        except Exception:
            pass

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}

    saved_paths: list[Path] = []
    for upload in files:
        suffix = Path(upload.filename or "page.jpg").suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            continue
        dest = session_dir / f"{uuid.uuid4().hex}{suffix}"
        content = await upload.read()
        dest.write_bytes(content)
        saved_paths.append(dest)

    if not saved_paths:
        _cleanup_session(session_id)
        raise HTTPException(status_code=400, detail="No valid image files received.")

    saved_paths.sort(key=lambda p: p.name)

    async def stream_progress():
        pages: list[PageData] = []
        total = len(saved_paths)

        for i, img_path in enumerate(saved_paths, start=1):
            # Send progress update
            yield f"data: {json.dumps({'type': 'progress', 'page': i, 'total': total, 'status': f'Processing page {i} of {total}...'})}\n\n"

            try:
                pil_img = Image.open(img_path)
                preprocessed = preprocess_image(pil_img)

                # Free original image from memory immediately
                del pil_img
                gc.collect()

                result = ocr_image(
                    preprocessed,
                    page_num=i,
                    use_claude=anthropic_client is not None,
                    anthropic_client=anthropic_client,
                )

                # Free preprocessed image from memory immediately
                del preprocessed
                gc.collect()

                pages.append(PageData(
                    page=i,
                    text=result.text,
                    method=result.method,
                    confidence=result.confidence,
                    source=str(img_path),
                ))

                yield f"data: {json.dumps({'type': 'page_done', 'page': i, 'method': result.method, 'confidence': round(result.confidence)})}\n\n"

            except Exception as exc:
                yield f"data: {json.dumps({'type': 'warning', 'page': i, 'message': f'Page {i} had issues: {str(exc)[:100]}'})}\n\n"

        if not pages:
            yield f"data: {json.dumps({'type': 'error', 'message': 'OCR failed on all pages. Try retaking photos in better light.'})}\n\n"
            _cleanup_session(session_id)
            return

        yield f"data: {json.dumps({'type': 'progress', 'page': total, 'total': total, 'status': 'Building EPUB...'})}\n\n"

        import re
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[\s_-]+", "-", slug).strip("-") or "book"

        markdown_body = merge_pages(pages, fix_spelling=fix_spelling)
        del pages
        gc.collect()

        front_matter = f"---\ntitle: {title}\nauthor: {author}\nlanguage: {language}\n---\n\n"
        md_path = session_dir / f"{slug}.md"
        md_path.write_text(front_matter + markdown_body, encoding="utf-8")
        del markdown_body
        gc.collect()

        epub_path = session_dir / f"{slug}.epub"

        try:
            convert_to_epub(
                markdown_path=md_path,
                output_path=epub_path,
                title=title,
                author=author,
                language=language,
                cover_path=None,
            )
        except RuntimeError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': f'EPUB conversion failed: {str(exc)[:200]}'})}\n\n"
            _cleanup_session(session_id)
            return

        # Send done event with download path
        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'slug': slug, 'filename': f'{slug}.epub'})}\n\n"

    return StreamingResponse(
        stream_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/download/{session_id}/{filename}")
async def download_epub(session_id: str, filename: str):
    """Serve the generated EPUB file for download."""
    # Sanitize inputs
    if "/" in session_id or ".." in session_id:
        raise HTTPException(status_code=400, detail="Invalid session.")
    if "/" in filename or ".." in filename or not filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    epub_path = SESSION_ROOT / session_id / filename
    if not epub_path.exists():
        raise HTTPException(status_code=404, detail="File not found or already cleaned up.")

    return FileResponse(
        path=str(epub_path),
        media_type="application/epub+zip",
        filename=filename,
    )


@app.delete("/session")
def delete_session(authorization: Optional[str] = Header(default=None)):
    session_id = _verify_clerk_token(authorization)
    _cleanup_session(session_id)
    return {"status": "cleaned", "session": session_id}
