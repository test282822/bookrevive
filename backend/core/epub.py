"""
core/epub.py
------------
Convert a Markdown file to a polished EPUB using Calibre's ebook-convert CLI.

Why Calibre? Standards-compliant EPUB 3, auto TOC, custom CSS, no Python EPUB lib needed.

Calibre flags used:
  --chapter / --page-breaks-before   split at H1/H2 headings
  --level1-toc / --level2-toc        auto TOC
  --extra-css                        inject our stylesheet
  --output-profile tablet            sane default for reflowable EPUBs
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_CSS = """\
/* BookRevive default stylesheet */
body {
    font-family: Georgia, "Times New Roman", Times, serif;
    font-size: 1em;
    line-height: 1.65;
    margin: 0 auto;
    max-width: 38em;
    text-align: justify;
    -webkit-hyphens: auto;
    hyphens: auto;
}
h1, h2, h3 {
    font-family: "Palatino Linotype", Palatino, "Book Antiqua", serif;
    text-align: center;
    font-weight: bold;
    page-break-before: always;
    margin-top: 3em;
    margin-bottom: 1.5em;
    line-height: 1.3;
}
h1 {
    font-size: 1.9em;
    border-bottom: 2px solid #333;
    padding-bottom: 0.4em;
    letter-spacing: 0.05em;
}
h2 {
    font-size: 1.4em;
    border-bottom: 1px solid #888;
    padding-bottom: 0.2em;
}
h3 { font-size: 1.15em; font-style: italic; border: none; }
p { margin: 0; text-indent: 1.5em; }
h1 + p, h2 + p, h3 + p, blockquote + p, div + p, p:first-of-type { text-indent: 0; }
blockquote {
    margin: 1.2em 2em;
    font-style: italic;
    border-left: 3px solid #aaa;
    padding-left: 1em;
    color: #444;
}
pre, code {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.9em;
    background: #f4f4f4;
    padding: 0.1em 0.3em;
    border-radius: 3px;
}
.page-marker { display: none; }
"""


def convert_to_epub(
    markdown_path: Path,
    output_path: Path,
    title: str = "Untitled Book",
    author: str = "Unknown Author",
    language: str = "en",
    cover_path: Optional[Path] = None,
    extra_calibre_args: Optional[list[str]] = None,
    style_css: Optional[str] = None,
) -> Path:
    """
    Convert markdown_path to an EPUB at output_path using Calibre.

    Args:
        markdown_path:       Path to the source .md file.
        output_path:         Desired output .epub path.
        title:               Book title (written into EPUB metadata).
        author:              Author name.
        language:            BCP-47 language tag (e.g. "en", "fr", "de").
        cover_path:          Optional cover image (JPG or PNG).
        extra_calibre_args:  Additional raw args forwarded to ebook-convert.
        style_css:           Override CSS string (None = use _DEFAULT_CSS).

    Returns:
        output_path on success.

    Raises:
        RuntimeError: If Calibre is not installed or conversion fails.
    """
    ebook_convert_bin = _require_calibre()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        css_file = tmp / "bookrevive.css"
        css_file.write_text(
            style_css if style_css is not None else _DEFAULT_CSS,
            encoding="utf-8",
        )

        cmd: list[str] = [
            ebook_convert_bin,
            str(markdown_path),
            str(output_path),
            "--title", title,
            "--authors", author,
            "--language", language,
            "--pubdate", date.today().isoformat(),
            "--chapter", r"//*[name()='h1' or name()='h2']",
            "--chapter-mark", "pagebreak",
            "--page-breaks-before", r"//*[name()='h1' or name()='h2']",
            "--toc-title", "Table of Contents",
            "--use-auto-toc",
            "--level1-toc", r"//h:h1",
            "--level2-toc", r"//h:h2",
            "--level3-toc", r"//h:h3",
            "--extra-css", str(css_file),
            "--output-profile", "tablet",
            "--preserve-cover-aspect-ratio",
        ]

        if cover_path and cover_path.is_file():
            cmd.extend(["--cover", str(cover_path)])

        if extra_calibre_args:
            cmd.extend(extra_calibre_args)

        logger.info("Running ebook-convert: %s", " ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        logger.error("ebook-convert stderr:\n%s", result.stderr)
        raise RuntimeError(
            f"Calibre conversion failed (exit code {result.returncode}):\n"
            f"{result.stderr[-2000:]}"
        )

    logger.info("EPUB written to %s", output_path)
    return output_path


def _find_ebook_convert() -> Optional[str]:
    """
    Search for the ebook-convert binary in all common locations.

    Resolution order:
      1. $CALIBRE_BIN env var
      2. PATH lookup
      3. ~/calibre-bin/
      4. ~/.local/bin/
      5. /opt/calibre/
      6. /usr/local/bin/
      7. /Applications/calibre.app/Contents/MacOS/  (macOS)
    """
    env_bin = os.environ.get("CALIBRE_BIN", "").strip()
    if env_bin and Path(env_bin).is_file() and os.access(env_bin, os.X_OK):
        return env_bin

    found = shutil.which("ebook-convert")
    if found:
        return found

    home = Path.home()
    candidates: list[Path] = [
        home / "calibre-bin" / "ebook-convert",
        home / ".local" / "bin" / "ebook-convert",
        Path("/opt/calibre/ebook-convert"),
        Path("/usr/local/bin/ebook-convert"),
        Path("/Applications/calibre.app/Contents/MacOS/ebook-convert"),
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(str(candidate), os.X_OK):
            return str(candidate)

    return None


def _require_calibre() -> str:
    path = _find_ebook_convert()
    if path:
        return path

    raise RuntimeError(
        "ebook-convert (Calibre) was not found.\n\n"
        "Install Calibre:\n"
        "  Linux (user-level):  wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh | sh /dev/stdin\n"
        "  Linux (apt):         sudo apt-get install calibre\n"
        "  macOS:               brew install --cask calibre\n"
        "  Windows:             https://calibre-ebook.com/download_windows\n\n"
        "Tip: set CALIBRE_BIN=/path/to/ebook-convert to override."
    )
