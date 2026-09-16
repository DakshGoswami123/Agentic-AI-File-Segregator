"""
Low-level, safe filesystem operations: waiting for a download to
finish, generating a non-colliding destination path, and moving a
file without ever overwriting something that already exists.
"""

import logging
import shutil
import time
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger("file_segregator")


def wait_until_file_is_ready(file_path: Path) -> bool:
    """
    Poll the file's size until it stops changing for
    STABLE_CHECKS_REQUIRED consecutive checks, treating that as
    "download finished". Returns False if the file vanishes, if it
    becomes briefly inaccessible, or if it never stabilizes in time.
    """
    stable_count = 0
    previous_size = -1
    deadline = time.monotonic() + config.MAX_READINESS_WAIT_SECONDS

    while time.monotonic() < deadline:
        try:
            current_size = file_path.stat().st_size
        except OSError:
            # File disappeared, or is briefly inaccessible mid-write.
            return False

        if current_size == previous_size:
            stable_count += 1
            if stable_count >= config.STABLE_CHECKS_REQUIRED:
                return True
        else:
            stable_count = 0

        previous_size = current_size
        time.sleep(config.STABLE_CHECK_INTERVAL_SECONDS)

    return False


def get_unique_path(folder: Path, filename: str) -> Path:
    """
    Return a path in `folder` that does not already exist, appending
    " 2", " 3", ... before the extension as needed. Never overwrites.
    """
    candidate = folder / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = folder / f"{stem} {counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def safe_move(source: Path, destination_folder: Path, filename: str) -> Optional[Path]:
    """
    Create destination_folder if needed and move `source` into it
    under a unique version of `filename`. Returns the final path on
    success, or None if the move failed (the reason is already logged).
    """
    try:
        destination_folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        logger.error("Could not create category folder %s: %s", destination_folder, error)
        return None

    if not source.exists():
        logger.warning("File disappeared before it could be moved: %s", source)
        return None

    destination = get_unique_path(destination_folder, filename)

    try:
        # shutil.move (rather than Path.rename) also handles the case
        # where the destination ends up on a different drive on Windows.
        shutil.move(str(source), str(destination))
        return destination
    except (OSError, shutil.Error) as error:
        logger.error("Could not move %s -> %s: %s", source, destination, error)
        return None
