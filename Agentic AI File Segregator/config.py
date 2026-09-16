"""
Configuration for the AI File Segregator.

Edit the values below to customize behavior. Nothing else in the
codebase should need to change for basic reconfiguration (different
folder, different model, different categories, etc).
"""

from pathlib import Path

# --------------------------------------------------------------------
# Folder to monitor
# --------------------------------------------------------------------
WATCH_FOLDER = Path.home() / "Downloads"

# --------------------------------------------------------------------
# LLM settings
# --------------------------------------------------------------------
LLM_MODEL = "llama3"

# Maximum characters of extracted content sent to the LLM. Keeps
# prompts fast and avoids blowing past the model's context window.
MAX_CONTENT_CHARS = 6000

# --------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------
SCAN_INTERVAL_SECONDS = 5

# A file is considered "finished downloading" once its size hasn't
# changed for this many consecutive checks.
STABLE_CHECKS_REQUIRED = 3
STABLE_CHECK_INTERVAL_SECONDS = 1
MAX_READINESS_WAIT_SECONDS = 30

# If a file fails processing (LLM error, permission error, etc.),
# wait this long before trying it again instead of retrying every
# single scan.
FAILED_FILE_RETRY_COOLDOWN_SECONDS = 60

# --------------------------------------------------------------------
# Categories the AI is allowed to choose from
# --------------------------------------------------------------------
CATEGORIES = [
    "Finance",
    "Personal",
    "Education",
    "Work",
    "Bills",
    "Images",
    "Code",
    "Other",
]

FALLBACK_CATEGORY = "Other"
FALLBACK_NAME = "Unclassified File"

# --------------------------------------------------------------------
# Supported file extensions
# --------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".bmp",
}

# Browser partial-download extensions (.crdownload, .part, etc.) are
# NOT in SUPPORTED_EXTENSIONS above, so they're already ignored by the
# extension whitelist. Listed here only to document that this is
# intentional, in case someone is tempted to "helpfully" add them.
PARTIAL_DOWNLOAD_EXTENSIONS = {".crdownload", ".part", ".partial", ".download", ".tmp"}
