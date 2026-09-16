"""
Entry point: sets up logging and runs the scan loop.

Run with:  python main.py
Stop with: CTRL+C
"""

import logging
import time

import config
from organizer import scan_folder


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("file_segregator")

    config.WATCH_FOLDER.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 40)
    logger.info("AI FILE SEGREGATOR")
    logger.info("=" * 40)
    logger.info("Watching folder: %s", config.WATCH_FOLDER)
    logger.info("AI model: %s", config.LLM_MODEL)
    logger.info("Scan interval: %ss", config.SCAN_INTERVAL_SECONDS)
    logger.info("Categories: %s", ", ".join(config.CATEGORIES))
    logger.info("Agent is running. Press CTRL+C to stop.")

    try:
        while True:
            scan_folder()
            time.sleep(config.SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Stopping AI File Segregator. Goodbye!")


if __name__ == "__main__":
    main()
