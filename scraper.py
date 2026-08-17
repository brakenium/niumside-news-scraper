#!/usr/bin/env python3

import json
import logging
import sys
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


URL = "https://www.planetside2.com/home/patch-notes"

DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"

NEWS_FILE = DATA_DIR / "news.json"
PATCH_NOTES_FILE = DATA_DIR / "patch-notes.json"

NEWS_ARCHIVE_FILE = ARCHIVE_DIR / "news.json"
PATCH_NOTES_ARCHIVE_FILE = ARCHIVE_DIR / "patch-notes.json"


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


def extract_feed(
    page,
    feed_name: str,
) -> dict[str, Any]:
    """
    Return SOE.Feeds.<feed> after the website has executed its
    JavaScript.

    JSON.stringify intentionally removes JavaScript functions and
    other values that JSON cannot represent.
    """

    feed = page.evaluate(
        """
        (feedName) => {
            const feed = window.SOE?.Feeds?.[feedName];

            if (!feed) {
                throw new Error(
                    `SOE.Feeds.${feedName} does not exist`
                );
            }

            return JSON.parse(JSON.stringify(feed));
        }
        """,
        feed_name,
    )

    if not isinstance(feed, dict):
        raise RuntimeError(
            f"SOE.Feeds.{feed_name} is not an object"
        )

    logger.info(
        "%s properties: %s",
        feed_name,
        ", ".join(feed.keys()),
    )

    return feed


def entry_key(
    entry: dict[str, Any],
) -> str:
    page_name = entry.get("pageName")

    if page_name:
        return f"pageName:{page_name}"

    name = entry.get("name")

    if name:
        return f"name:{name}"

    return json.dumps(
        entry,
        sort_keys=True,
        ensure_ascii=False,
    )


def update_archive(
    current: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    """
    Add new entries from current.data.list to the archive.

    All other properties from the current feed are kept up to date.
    """

    if path.exists():
        archive = json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    else:
        archive = json.loads(
            json.dumps(current)
        )

        archive.setdefault(
            "data",
            {},
        )

        archive["data"]["list"] = []

    current_data = current.get("data")

    if not isinstance(current_data, dict):
        return current

    current_entries = current_data.get("list")

    if not isinstance(current_entries, list):
        return current

    archive_data = archive.setdefault(
        "data",
        {},
    )

    archived_entries = archive_data.setdefault(
        "list",
        [],
    )

    existing_keys = {
        entry_key(entry)
        for entry in archived_entries
        if isinstance(entry, dict)
    }

    added = 0

    for entry in current_entries:
        if not isinstance(entry, dict):
            continue

        key = entry_key(entry)

        if key in existing_keys:
            continue

        archived_entries.append(entry)
        existing_keys.add(key)
        added += 1

    # Keep everything except the cumulative data.list current.
    for key, value in current.items():
        if key != "data":
            archive[key] = value

    for key, value in current_data.items():
        if key != "list":
            archive_data[key] = value

    logger.info(
        "%s: added %d entries, %d total",
        path,
        added,
        len(archived_entries),
    )

    return archive


def write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    temporary_path.replace(path)


def main() -> int:
    try:
        with sync_playwright() as playwright:
            logger.info("Launching Chromium")

            browser = playwright.chromium.launch(
                headless=True,
                executable_path=os.environ["PLAYWRIGHT_CHROMIUM"],
            )

            try:
                page = browser.new_page()

                logger.info(
                    "Loading %s",
                    URL,
                )

                page.goto(
                    URL,
                    wait_until="networkidle",
                    timeout=60_000,
                )

                # Wait until the site's JavaScript has created
                # the feed objects.
                page.wait_for_function(
                    """
                    () =>
                        window.SOE?.Feeds?.news &&
                        window.SOE?.Feeds?.updateNotes
                    """,
                    timeout=60_000,
                )

                news = extract_feed(
                    page,
                    "news",
                )

                patch_notes = extract_feed(
                    page,
                    "updateNotes",
                )

            finally:
                browser.close()

        write_json(
            NEWS_FILE,
            news,
        )

        write_json(
            PATCH_NOTES_FILE,
            patch_notes,
        )

        news_archive = update_archive(
            news,
            NEWS_ARCHIVE_FILE,
        )

        patch_notes_archive = update_archive(
            patch_notes,
            PATCH_NOTES_ARCHIVE_FILE,
        )

        write_json(
            NEWS_ARCHIVE_FILE,
            news_archive,
        )

        write_json(
            PATCH_NOTES_ARCHIVE_FILE,
            patch_notes_archive,
        )

        logger.info(
            "Scraping completed successfully"
        )

        return 0

    except Exception as error:
        logger.error(
            "%s",
            error,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
