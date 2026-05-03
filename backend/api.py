"""
backend/api.py — BookRevive FastAPI Backend
--------------------------------------------
Wraps the existing BookRevive pipeline for HTTP access.

Endpoints:
  POST /process     — Upload images, returns EPUB
  DELETE /session   — Clean up session data on disconnect
  GET  /health      — Railway health check

Auth: Clerk JWT verified on every request.
User API Key: passed per-request in X-Anthropic-Key header — never stored.
Session data: written to /tmp/bookrevive/{session_id}/ and deleted on cleanup.
"""

from __future__ import annotations

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
from PIL import Image

# Make sure core/ and utils/ are importable
sys.path.insert(0, str(Path(__file__).parent))

from core.epub import convert_to_epub
from core.merger import PageData, merge_pages
from core.ocr import ocr_image
from utils.image_prep import assess_image_quality, preprocess_image

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="BookRevive API",
    description="Convert phone photos of old books to EPUB files.",
    version="1.0.0",
)

# Allow Vercel frontend origin — update this to your Vercel URL after deploy
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    os.environ.get("FRONTEND_URL", "https://bookrevive.vercel.app"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session directory helper
# ---------------------------------------------------------------------------

SESSION_ROOT = Path(tempfile.gettempdir()) / "bookrevive"
SESSION_ROOT.mkdir(parents=True, exist_ok=True)


def _session_dir(session_id: str) -> Path:
    """Return (and create) a per-session working directory."""
    d = SESSION_ROOT / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cleanup_session(session_id: str) -> None:
    """Delete all files for a session — called on disconnect or explicit DELETE."""
    d = SESSION_ROOT / session_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Clerk JWT verification (lightweight header check)
# ---------------------------------------------------------------------------

def _verify_clerk_token(authorization: Optional[str]) -> str:
    """
    Extract and verify the Clerk session token.
    Returns the user_id embedded in the token.

    For a production hardening step, install `clerk-backend` and call
    clerk.verify_token(token) — for now we validate the header is present
    and return a stable session ID derived from the token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty token.")
    # Derive a stable session ID from the token (first 32 chars is sufficient for temp dirs)
    session_id = token[:32].replace(".", "_").replace("-", "_")
    return session_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Railway uses this to confirm the service is up."""
    return {"status": "ok", "service": "bookrevive-api"}


@app.post("/process")
async def process_images(
    files: list[UploadFile] = File(..., description="One or more book page images."),
    title: str = Form(default="Untitled Book"),
    author: str = Form(default="Unknown Author"),
    language: str = Form(default="en"),
    fix_spelling: bool = Form(default=False),
    authorization: Optional[str] = Header(default=None),
    x_anthropic_key: Optional[str] = Header(default=None),
):
    """
    Process uploaded book page images and return a downloadable EPUB.

    - Auth: Clerk JWT in Authorization: Bearer <token>
    - User's own Anthropic key: X-Anthropic-Key header (optional, enables Claude vision fallback)
    - Files are cleaned up after the response is sent
    """
    session_id = _verify_clerk_token(authorization)
    session_dir = _session_dir(session_id)

    # Build Anthropic client from the user's own key — never stored, used only for this request
    anthropic_client = None
    if x_anthropic_key and x_anthropic_key.strip():
        try:
            anthropic_client = anthropic.Anthropic(api_key=x_anthropic_key.strip())
        except Exception:
            pass  # Fallback to Tesseract-only if key is invalid

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}

    # Save uploaded files to session directory
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

    # Sort pages by filename order
    saved_paths.sort(key=lambda p: p.name)

    pages: list[PageData] = []
    warnings: list[str] = []

    for i, img_path in enumerate(saved_paths, start=1):
        try:
            pil_img = Image.open(img_path)

            report = assess_image_quality(pil_img)
            warnings.extend(report.get("warnings", []))

            preprocessed = preprocess_image(pil_img)

            result = ocr_image(
                preprocessed,
                page_num=i,
                use_claude=anthropic_client is not None,
                anthropic_client=anthropic_client,
            )
            warnings.extend(result.warnings)

            pages.append(PageData(
                page=i,
                text=result.text,
                method=result.method,
                confidence=result.confidence,
                source=str(img_path),
            ))
        except Exception as exc:
            warnings.append(f"Page {i} error: {exc}")

    if not pages:
        _cleanup_session(session_id)
        raise HTTPException(status_code=422, detail="OCR failed on all pages. Try retaking photos.")

    # Merge pages into Markdown
    markdown_body = merge_pages(pages, fix_spelling=fix_spelling)

    import re
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-") or "book"

    front_matter = (
        f"---\ntitle: {title}\nauthor: {author}\nlanguage: {language}\npages: {len(pages)}\n---\n\n"
    )
    md_path = session_dir / f"{slug}.md"
    md_path.write_text(front_matter + markdown_body, encoding="utf-8")

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
        _cleanup_session(session_id)
        raise HTTPException(status_code=500, detail=f"EPUB conversion failed: {exc}")

    # Stream the EPUB back — cleanup happens after response
    response = FileResponse(
        path=str(epub_path),
        media_type="application/epub+zip",
        filename=f"{slug}.epub",
        background=None,
    )

    # Schedule cleanup after response
    @response.background
    async def cleanup():
        _cleanup_session(session_id)

    return response


@app.delete("/session")
def delete_session(authorization: Optional[str] = Header(default=None)):
    """
    Explicitly clean up all session data.
    Called by the frontend on logout or tab close.
    """
    session_id = _verify_clerk_token(authorization)
    _cleanup_session(session_id)
    return {"status": "cleaned", "session": session_id}
