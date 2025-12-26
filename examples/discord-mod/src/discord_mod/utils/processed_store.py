"""Simple file-based store for tracking processed message IDs.

Prevents reprocessing the same messages across restarts.
Uses a JSON file that can be persisted on a Fly.io volume.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)

DEFAULT_TTL_DAYS = 7


def _get_default_path() -> str:
    """Get default path, preferring /data (Fly.io volume) if available."""
    fly_path = Path("/data")
    if fly_path.exists() and fly_path.is_dir():
        return "/data/processed_messages.json"
    return "processed_messages.json"


class ProcessedMessageStore:
    """Track processed message IDs with automatic cleanup of old entries.
    
    Uses debounced saving to avoid excessive disk writes when processing
    many messages in sequence.
    """

    def __init__(
        self,
        path: str | None = None,
        ttl_days: int = DEFAULT_TTL_DAYS,
        save_interval: float = 5.0,
        cleanup_interval: float = 3600.0,  # 1 hour
    ):
        self.path = Path(path or os.environ.get("PROCESSED_MESSAGES_PATH") or _get_default_path())
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self.save_interval = save_interval
        self.cleanup_interval = cleanup_interval
        self._data: dict[str, float] = {}  # message_id -> timestamp
        self._dirty = False
        self._last_save: float = 0
        self._last_cleanup: float = time.time()
        self._load()

    def _load(self) -> None:
        """Load existing data from file."""
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
                logger.info(f"Loaded {len(self._data)} processed message IDs from {self.path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load processed messages: {e}")
                self._data = {}
        else:
            logger.info(f"No existing processed messages file at {self.path}")

    def _save(self, force: bool = False) -> None:
        """Save data to file if dirty and interval elapsed (or forced)."""
        if not self._dirty:
            return
        
        now = time.time()
        if not force and (now - self._last_save) < self.save_interval:
            return
        
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                json.dump(self._data, f)
            os.replace(tmp_path, self.path)
            self._dirty = False
            self._last_save = now
        except IOError as e:
            logger.error(f"Failed to save processed messages: {e}")

    def _cleanup_old(self, force: bool = False) -> None:
        """Remove entries older than TTL (debounced unless forced)."""
        now = time.time()
        if not force and (now - self._last_cleanup) < self.cleanup_interval:
            return
        
        cutoff = now - self.ttl_seconds
        old_count = len(self._data)
        self._data = {k: v for k, v in self._data.items() if v > cutoff}
        removed = old_count - len(self._data)
        self._last_cleanup = now
        if removed > 0:
            self._dirty = True
            logger.info(f"Cleaned up {removed} old processed message IDs")

    def is_processed(self, message_id: str) -> bool:
        """Check if a message has already been processed."""
        return message_id in self._data

    def mark_processed(self, message_id: str) -> None:
        """Mark a message as processed (debounced save and cleanup)."""
        self._data[message_id] = time.time()
        self._dirty = True
        self._cleanup_old()
        self._save()

    def mark_batch_processed(self, message_ids: Set[str]) -> None:
        """Mark multiple messages as processed (immediate save)."""
        now = time.time()
        for mid in message_ids:
            self._data[mid] = now
        self._dirty = True
        self._cleanup_old(force=True)
        self._save(force=True)

    def flush(self) -> None:
        """Force save any pending changes and cleanup old entries."""
        self._cleanup_old(force=True)
        self._save(force=True)

    def get_unprocessed(self, message_ids: Set[str]) -> Set[str]:
        """Filter to only unprocessed message IDs."""
        return message_ids - set(self._data.keys())
