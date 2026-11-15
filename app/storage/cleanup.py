"""Storage cleanup utilities for DocMorph.

Handles periodic maintenance, cache purging, and orphaned temporary file removal.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from app.core.config import settings
from app.core.logging import logger


def cleanup_storage_cache(max_age_hours: int = 24) -> int:
    """Removes cached S3 files and temporary probe files older than max_age_hours."""
    deleted_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    # 1. Clean S3 temp cache
    s3_cache = Path(tempfile.gettempdir()) / "docmorph_s3_cache"
    if s3_cache.is_dir():
        for file in s3_cache.iterdir():
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    try:
                        file.unlink()
                        deleted_count += 1
                    except OSError as e:
                        logger.warning("Failed to delete cache file %s: %s", file, e)

    # 2. Clean health probe artifacts
    for sub in ["uploads", "personalized"]:
        probe = settings.STORAGE_DIR / sub / ".health_probe"
        if probe.is_file():
            probe.unlink(missing_ok=True)
            deleted_count += 1

    logger.info("Storage cleanup completed: %d files removed.", deleted_count)
    return deleted_count

