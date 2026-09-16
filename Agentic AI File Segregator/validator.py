"""
Validation and sanitization of whatever the LLM returns.

Nothing from the LLM is trusted as-is: the filename is stripped down
to safe characters and checked for exactly three words, the category
is checked against a fixed allowlist, and the final destination folder
is verified to actually be inside the watch folder before anything is
written to disk. This module is the program's security boundary.
"""

import re
from pathlib import Path
from typing import Tuple

import config

# Characters that are unsafe/reserved across Windows, macOS and Linux
# filesystems.
_UNSAFE_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_name(raw_name: str) -> str:
    """
    Turn whatever the LLM produced into a safe, exactly-three-word,
    Title Case filename stem. Falls back to the configured default
    name if the input doesn't yield exactly three usable words.
    """
    if not isinstance(raw_name, str):
        return config.FALLBACK_NAME

    # Strip ".." and path separators before anything else — this blocks
    # path-traversal-style payloads even if they'd otherwise happen to
    # collapse into something that looks like three words.
    candidate = raw_name.replace("..", "").strip()
    candidate = _UNSAFE_CHARS_PATTERN.sub("", candidate)

    words = [w for w in re.split(r"\s+", candidate.strip()) if w]
    if len(words) != 3:
        return config.FALLBACK_NAME

    # Keep only alphanumerics within each word.
    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in words]
    if not all(words):
        return config.FALLBACK_NAME

    return " ".join(_title_case_word(w) for w in words)


def _title_case_word(word: str) -> str:
    """
    Title-case a word, but preserve short all-caps acronyms (HDFC, GST,
    PDF, ...) instead of collapsing them to "Hdfc" / "Gst" / "Pdf".
    """
    if word.isupper() and len(word) > 1:
        return word
    return word[:1].upper() + word[1:].lower()


def sanitize_category(raw_category: str) -> str:
    """Return raw_category if it's an exact allowlist match, else the fallback."""
    if raw_category in config.CATEGORIES:
        return raw_category
    return config.FALLBACK_CATEGORY


def validate_result(result: dict) -> Tuple[str, str]:
    """Validate an LLM result dict, returning (safe_name, safe_category)."""
    name = sanitize_name(result.get("name", ""))
    category = sanitize_category(result.get("category", ""))
    return name, category


def build_safe_destination_folder(watch_folder: Path, category: str) -> Path:
    """
    Resolve the destination category folder and assert it is actually
    inside watch_folder. Defense in depth: `category` already comes
    from a fixed allowlist, so this should never actually trigger —
    but it guarantees the final path can never escape the watch folder
    even if that assumption is ever broken by a future code change.
    """
    watch_folder = watch_folder.resolve()
    destination = (watch_folder / category).resolve()

    if destination != watch_folder and watch_folder not in destination.parents:
        raise ValueError(f"Refusing unsafe destination outside watch folder: {destination}")

    return destination
