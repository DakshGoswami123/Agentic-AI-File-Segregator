"""
Orchestration: scans the watch folder and runs each new file through
the full pipeline (extract -> analyze -> validate -> move).
"""

import logging
import time
from pathlib import Path
from typing import Dict

import config
from extractors import extract_text
from llm_analyzer import analyze_file_with_llm
from validator import validate_result, build_safe_destination_folder
from file_manager import wait_until_file_is_ready, safe_move

logger = logging.getLogger("file_segregator")

# path -> timestamp of last failed attempt. Lets us skip retrying a
# broken file on every single scan without needing a database.
_recently_failed: Dict[Path, float] = {}


def _recently_failed_and_still_cooling_down(file_path: Path) -> bool:
    failed_at = _recently_failed.get(file_path)
    if failed_at is None:
        return False
    return (time.monotonic() - failed_at) < config.FAILED_FILE_RETRY_COOLDOWN_SECONDS


def process_file(file_path: Path) -> None:
    """Run the full pipeline for a single file. Never raises."""
    filename = file_path.name

    try:
        if not file_path.is_file():
            return

        if file_path.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
            return

        if _recently_failed_and_still_cooling_down(file_path):
            return

        logger.info("New file detected: %s", filename)

        logger.info("Waiting for file to finish downloading...")
        if not wait_until_file_is_ready(file_path):
            logger.info("Skipping %s (not finished downloading, or it vanished)", filename)
            return

        logger.info("Extracting content...")
        content = extract_text(file_path)
        if not content.strip():
            logger.info("No readable text found in %s — deciding from filename alone.", filename)

        logger.info("Sending content to LLM...")
        raw_result = analyze_file_with_llm(filename, content)

        new_name, category = validate_result(raw_result)
        logger.info("Generated name: %s", new_name)
        logger.info("Category: %s", category)

        destination_folder = build_safe_destination_folder(config.WATCH_FOLDER, category)
        new_filename = new_name + file_path.suffix.lower()

        logger.info("Renaming and moving file...")
        final_path = safe_move(file_path, destination_folder, new_filename)

        if final_path is not None:
            logger.info("File organized successfully -> %s", final_path)
            _recently_failed.pop(file_path, None)
        else:
            _recently_failed[file_path] = time.monotonic()

    except Exception as error:
        # Last-resort safety net: one bad file must never kill the agent.
        logger.error("Unexpected error processing %s: %s", filename, error, exc_info=True)
        _recently_failed[file_path] = time.monotonic()


def scan_folder() -> None:
    """List the watch folder and process any supported top-level files."""
    try:
        entries = list(config.WATCH_FOLDER.iterdir())
    except OSError as error:
        logger.error("Cannot access watch folder %s: %s", config.WATCH_FOLDER, error)
        return

    for entry in entries:
        if entry.is_dir():
            # Category folders (Finance/, Work/, ...) and any other
            # subfolders are never recursed into.
            continue
        if entry.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
            continue
        process_file(entry)
