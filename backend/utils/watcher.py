"""
utils/watcher.py
----------------
Folder-watching mode for BookRevive.

Uses watchdog to detect new image files dropped into a directory.
Batches events with a configurable debounce delay so that a multi-file
drop is treated as a single processing run.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"})


class _BatchImageHandler(FileSystemEventHandler):

    def __init__(self) -> None:
        super().__init__()
        self.pending: set[Path] = set()
        self.last_event_time: float = 0.0

    def _record(self, path: Path) -> None:
        if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file():
            logger.debug("Detected new image: %s", path)
            self.pending.add(path)
            self.last_event_time = time.monotonic()

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._record(Path(event.dest_path))


def watch_folder(
    folder: Path,
    callback: Callable[[list[Path]], None],
    batch_delay: float = 5.0,
) -> None:
    """
    Watch folder for new image files and call callback with sorted batches
    once no new files have arrived for batch_delay seconds.

    Blocks until KeyboardInterrupt (Ctrl-C).
    """
    handler = _BatchImageHandler()
    observer = Observer()
    observer.schedule(handler, str(folder), recursive=False)
    observer.start()

    logger.info("Watching %s (batch_delay=%.1fs) — press Ctrl-C to stop", folder, batch_delay)

    try:
        while True:
            time.sleep(0.5)
            now = time.monotonic()
            if handler.pending and (now - handler.last_event_time) >= batch_delay:
                batch = sorted(handler.pending)
                handler.pending.clear()
                logger.info("Processing batch of %d image(s)", len(batch))
                try:
                    callback(batch)
                except Exception as exc:
                    logger.error("Pipeline error for batch: %s", exc, exc_info=True)
    except KeyboardInterrupt:
        logger.info("Watch mode stopped by user.")
    finally:
        observer.stop()
        observer.join()
