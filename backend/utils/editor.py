"""
utils/editor.py
---------------
Open a file in the user's preferred text editor and block until closed.

Editor resolution order:
  1. $VISUAL
  2. $EDITOR
  3. Platform default (notepad / TextEdit / nano)
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def open_in_editor(path: Path) -> None:
    """Open path in user's editor and wait for them to close it."""
    editor_cmd = (
        os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or _platform_default()
    )

    parts = shlex.split(editor_cmd)
    cmd = parts + [str(path)]

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        for fallback in ("nano", "vi"):
            if _which(fallback):
                subprocess.run([fallback, str(path)], check=False)
                return
        raise RuntimeError(
            f"Could not open editor '{editor_cmd}'. "
            "Set the VISUAL or EDITOR environment variable to your preferred editor."
        )


def _platform_default() -> str:
    if sys.platform == "win32":
        return "notepad"
    if sys.platform == "darwin":
        return "open -e"
    return "nano"


def _which(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None
