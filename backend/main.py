#!/usr/bin/env python3
"""
main.py — BookRevive CLI
------------------------
Turn phone photos of old book pages into polished EPUB files.

Commands:
  bookrevive process <images/folder>  — Full OCR → Markdown → EPUB pipeline
  bookrevive watch   <folder>         — Watched-folder automation mode
  bookrevive test                     — Environment self-check

Usage examples:
  python main.py process scans/ --title "My Book" --author "Jane Doe"
  python main.py process p1.jpg p2.jpg --title "Story" --edit
  python main.py watch inbox/ --output epubs/
  python main.py test
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from core.epub import convert_to_epub, _find_ebook_convert
from core.merger import PageData, merge_pages
from core.ocr import OCRResult, ocr_image
from utils.editor import open_in_editor
from utils.image_prep import assess_image_quality, preprocess_image
from utils.watcher import watch_folder

app = typer.Typer(
    name="bookrevive",
    help="BookRevive — digitise old books from phone photos to polished EPUBs.",
    add_completion=False,
    pretty_exceptions_enable=False,
)
console = Console(stderr=False)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bookrevive")

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"})


def _set_verbosity(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.getLogger().setLevel(level)
    logging.getLogger("bookrevive").setLevel(level)


def _collect_images(paths: list[Path]) -> list[Path]:
    images: list[Path] = []
    for p in paths:
        if p.is_dir():
            found = [f for f in sorted(p.iterdir()) if f.suffix.lower() in IMAGE_EXTENSIONS]
            images.extend(found)
        elif p.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(p)
        else:
            console.print(f"[yellow]Skipping (not an image): {p}[/yellow]")
    seen: set[Path] = set()
    unique: list[Path] = []
    for img in images:
        if img not in seen:
            seen.add(img)
            unique.append(img)
    return unique


def _get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import anthropic  # type: ignore[import]
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        console.print(
            "[yellow]Warning: anthropic package not installed; "
            "Claude vision fallback is disabled.[/yellow]"
        )
        return None


def _title_to_slug(title: str) -> str:
    import re
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "book"


def run_pipeline(
    images: list[Path],
    output_dir: Path,
    title: str,
    author: str,
    language: str,
    edit: bool,
    fix_spelling: bool,
    cover: Optional[Path],
    verbose: bool = False,
) -> Path:
    """
    Full BookRevive pipeline:
      1. Quality-check and preprocess each image
      2. OCR (Tesseract primary, Claude vision fallback)
      3. Merge pages into structured Markdown
      4. Optionally open Markdown in editor
      5. Convert Markdown → EPUB via Calibre

    Returns the path to the generated EPUB.
    """
    _set_verbosity(verbose)
    output_dir.mkdir(parents=True, exist_ok=True)

    anthropic_client = _get_anthropic_client()
    if not anthropic_client:
        console.print("[dim]ℹ ANTHROPIC_API_KEY not set — Claude vision fallback disabled.[/dim]")

    pages: list[PageData] = []
    all_warnings: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        ocr_task = progress.add_task("OCR …", total=len(images))

        for i, img_path in enumerate(images, start=1):
            progress.update(ocr_task, description=f"[cyan]OCR[/cyan] {img_path.name}")
            try:
                from PIL import Image  # type: ignore[import]
                pil_img = Image.open(img_path)

                report = assess_image_quality(pil_img)
                if report["warnings"]:
                    for w in report["warnings"]:
                        all_warnings.append(f"[{img_path.name}] {w}")
                    for s in report["suggestions"]:
                        all_warnings.append(f"    → {s}")
                if report["score"] < 30:
                    console.print(
                        f"[red]Warning: {img_path.name} has very low quality "
                        f"(score {report['score']}/100). Results may be poor.[/red]"
                    )

                preprocessed = preprocess_image(pil_img)
                result: OCRResult = ocr_image(
                    preprocessed,
                    page_num=i,
                    use_claude=True,
                    anthropic_client=anthropic_client,
                )
                all_warnings.extend(result.warnings)

                pages.append(
                    PageData(
                        page=i,
                        text=result.text,
                        method=result.method,
                        confidence=result.confidence,
                        source=str(img_path),
                    )
                )

            except Exception as exc:
                msg = f"[{img_path.name}] ERROR: {exc}"
                all_warnings.append(msg)
                console.print(f"[red]{msg}[/red]")

            progress.advance(ocr_task)

    if all_warnings:
        console.print("\n[yellow bold]OCR Warnings:[/yellow bold]")
        for w in all_warnings:
            console.print(f"  [yellow]{w}[/yellow]")
        console.print()

    if not pages:
        raise typer.Exit(
            console.print("[red]No pages were successfully OCR'd. Aborting.[/red]") or 1
        )

    console.print("[bold]Merging pages into Markdown …[/bold]")
    markdown_body = merge_pages(pages, fix_spelling=fix_spelling)

    slug = _title_to_slug(title)
    md_path = output_dir / f"{slug}.md"

    front_matter = (
        "---\n"
        f"title: {title}\n"
        f"author: {author}\n"
        f"language: {language}\n"
        f"pages: {len(pages)}\n"
        "---\n\n"
    )
    md_path.write_text(front_matter + markdown_body, encoding="utf-8")
    console.print(f"[green]Markdown:[/green] {md_path}")

    if edit:
        console.print("\n[bold cyan]Opening Markdown in your editor …[/bold cyan]")
        console.print("[dim]Save and close the editor to continue EPUB conversion.[/dim]")
        open_in_editor(md_path)

    console.print("\n[bold]Converting to EPUB …[/bold]")
    epub_path = output_dir / f"{slug}.epub"

    try:
        convert_to_epub(
            markdown_path=md_path,
            output_path=epub_path,
            title=title,
            author=author,
            language=language,
            cover_path=cover,
        )
    except RuntimeError as exc:
        console.print(f"[red]EPUB conversion failed:[/red] {exc}")
        console.print(f"[yellow]Markdown is still available at {md_path}[/yellow]")
        raise typer.Exit(1)

    return epub_path


@app.command("process")
def process_command(
    sources: List[Path] = typer.Argument(..., help="Image files or folders of images.", exists=True),
    title: str = typer.Option("Untitled Book", "--title", "-t", help="Book title"),
    author: str = typer.Option("Unknown Author", "--author", "-a", help="Author name"),
    language: str = typer.Option("en", "--language", "-l", help="BCP-47 language code"),
    output: Path = typer.Option(Path("output"), "--output", "-o", help="Output folder"),
    edit: bool = typer.Option(False, "--edit/--no-edit", help="Open Markdown in editor before EPUB conversion."),
    fix_spelling: bool = typer.Option(False, "--fix-spelling/--no-fix-spelling", help="Conservative spell correction (experimental)."),
    cover: Optional[Path] = typer.Option(None, "--cover", "-c", help="Cover image (JPG or PNG)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs."),
):
    """Process one or more book-page images into a polished EPUB."""
    console.print(Panel.fit(
        f"[bold cyan]BookRevive[/bold cyan]\n"
        f"[white]{title}[/white]  [dim]by {author}[/dim]",
        border_style="cyan",
    ))

    images = _collect_images(list(sources))
    if not images:
        console.print("[red]No valid image files found in the provided paths.[/red]")
        raise typer.Exit(1)

    console.print(f"\nFound [bold]{len(images)}[/bold] image(s):\n")
    for img in images:
        console.print(f"  [dim]{img}[/dim]")
    console.print()

    if cover and not cover.is_file():
        console.print(f"[red]Cover image not found: {cover}[/red]")
        raise typer.Exit(1)

    epub_path = run_pipeline(
        images=images,
        output_dir=output,
        title=title,
        author=author,
        language=language,
        edit=edit,
        fix_spelling=fix_spelling,
        cover=cover,
        verbose=verbose,
    )

    console.print(Panel.fit(
        f"[bold green]Done![/bold green]\n"
        f"EPUB → [cyan]{epub_path}[/cyan]",
        border_style="green",
    ))


@app.command("watch")
def watch_command(
    folder: Path = typer.Argument(..., help="Folder to watch for incoming images.", exists=True),
    title: str = typer.Option("Untitled Book", "--title", "-t"),
    author: str = typer.Option("Unknown Author", "--author", "-a"),
    language: str = typer.Option("en", "--language", "-l"),
    output: Path = typer.Option(Path("output"), "--output", "-o"),
    batch_delay: float = typer.Option(5.0, "--delay", "-d", help="Seconds of silence before processing."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Watch a folder for new images and automatically create an EPUB."""
    _set_verbosity(verbose)
    console.print(Panel.fit(
        f"[bold cyan]BookRevive — Watch Mode[/bold cyan]\n"
        f"Watching: [white]{folder.resolve()}[/white]\n"
        f"[dim]Batch delay: {batch_delay}s  |  Press Ctrl-C to stop[/dim]",
        border_style="cyan",
    ))

    def on_batch(images: list[Path]) -> None:
        console.print(f"\n[bold]Detected {len(images)} new image(s) — processing …[/bold]")
        try:
            epub_path = run_pipeline(
                images=images, output_dir=output, title=title, author=author,
                language=language, edit=False, fix_spelling=False, cover=None, verbose=verbose,
            )
            console.print(f"[green]EPUB created:[/green] {epub_path}\n")
        except Exception as exc:
            console.print(f"[red]Pipeline error:[/red] {exc}\n")

    watch_folder(folder, on_batch, batch_delay=batch_delay)


@app.command("test")
def test_command():
    """Run a quick environment self-check and print a status table."""
    console.print("[bold]BookRevive — Environment Check[/bold]\n")

    rows = [
        ("Python 3.11+",            _chk_python()),
        ("Pillow",                  _chk_import("PIL", "Pillow")),
        ("OpenCV",                  _chk_import("cv2", "opencv-python-headless")),
        ("NumPy",                   _chk_import("numpy", "numpy")),
        ("pytesseract",             _chk_import("pytesseract", "pytesseract")),
        ("Tesseract binary",        _chk_tesseract_binary()),
        ("Calibre (ebook-convert)", _chk_calibre()),
        ("anthropic SDK",           _chk_import("anthropic", "anthropic  [optional]")),
        ("ANTHROPIC_API_KEY",       _chk_env("ANTHROPIC_API_KEY")),
        ("watchdog",                _chk_import("watchdog", "watchdog")),
        ("pyspellchecker",          _chk_import("spellchecker", "pyspellchecker  [optional]")),
        ("typer + rich",            _chk_import("typer", "typer[all]")),
    ]

    table = Table(show_header=True, header_style="bold")
    table.add_column("Component", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    all_critical_ok = True
    critical = {
        "Python 3.11+", "Pillow", "OpenCV", "NumPy",
        "pytesseract", "Calibre (ebook-convert)", "watchdog", "typer + rich",
    }

    for name, (ok, detail) in rows:
        status = "[green]OK[/green]" if ok else "[red]MISSING[/red]"
        if not ok and name in critical:
            all_critical_ok = False
        table.add_row(name, status, detail)

    console.print(table)
    console.print()

    if all_critical_ok:
        console.print("[bold green]All critical components are present. Ready to run![/bold green]\n")
    else:
        console.print("[yellow]Some components are missing. Fix steps:[/yellow]")
        console.print("  1. [cyan]pip install -r requirements.txt[/cyan]")
        console.print("  2. Install Tesseract: https://github.com/tesseract-ocr/tesseract")
        console.print("  3. Install Calibre: https://calibre-ebook.com/download")
        console.print("  4. (Optional) Set ANTHROPIC_API_KEY for Claude vision fallback.")


def _chk_python() -> tuple[bool, str]:
    v = sys.version_info
    ok = v >= (3, 11)
    return ok, f"{v.major}.{v.minor}.{v.micro}"

def _chk_import(module: str, label: str) -> tuple[bool, str]:
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", "installed")
        return True, version
    except ImportError:
        return False, f"pip install {label}"

def _chk_tesseract_binary() -> tuple[bool, str]:
    try:
        import pytesseract
        v = pytesseract.get_tesseract_version()
        return True, str(v)
    except Exception as exc:
        return False, str(exc)[:80]

def _chk_calibre() -> tuple[bool, str]:
    path = _find_ebook_convert()
    if path:
        return True, path
    return False, "not found — install from https://calibre-ebook.com/download"

def _chk_env(name: str) -> tuple[bool, str]:
    val = os.environ.get(name, "")
    if val:
        return True, f"set ({val[:8]}…)"
    return False, f"{name} not set (optional)"


if __name__ == "__main__":
    app()
