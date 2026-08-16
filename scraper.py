import json
import logging
import re
from pathlib import Path

import requests
from lxml import html


URL = "https://www.planetside2.com/home/patch-notes"

DATA_DIR = Path("data")
ARCHIVE_DIR = DATA_DIR / "archive"

NEWS_FILE = DATA_DIR / "news.json"
PATCH_NOTES_FILE = DATA_DIR / "patch-notes.json"

NEWS_ARCHIVE_FILE = ARCHIVE_DIR / "news.json"
PATCH_NOTES_ARCHIVE_FILE = ARCHIVE_DIR / "patch-notes.json"

USER_AGENT = "PlanetSide2Archive/1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

logger = logging.getLogger(__name__)


def fetch_page() -> str:
    logger.info("Fetching %s", URL)

    response = requests.get(
        URL,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()

    logger.info("Fetched %.1f KiB", len(response.content) / 1024)

    return response.text


def extract_json_object(text: str, start: int) -> str:
    """Extract a JSON object beginning at `start`.

    Handles nested objects and braces occurring inside JSON strings.
    """

    if start >= len(text) or text[start] != "{":
        raise ValueError("Expected '{' at start of JSON object")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        character = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False

            continue

        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1

            if depth == 0:
                return text[start : index + 1]

    raise ValueError("JSON object was not terminated")


def extract_feed(page: str, feed_name: str) -> dict:
    tree = html.fromstring(page)

    assignment = f"SOE.Feeds.{feed_name}.data"

    logger.info("Looking for %s", assignment)

    for script in tree.xpath("//script"):
        text = script.text or ""

        assignment_start = text.find(assignment)

        if assignment_start == -1:
            continue

        equals_position = text.find("=", assignment_start + len(assignment))

        if equals_position == -1:
            raise RuntimeError(
                f"Found {assignment}, but no assignment operator was found"
            )

        json_start = equals_position + 1

        while json_start < len(text) and text[json_start].isspace():
            json_start += 1

        if json_start >= len(text) or text[json_start] != "{":
            raise RuntimeError(
                f"Found {assignment}, but its value does not start with '{{'"
            )

        try:
            json_text = extract_json_object(text, json_start)
            data = json.loads(json_text)
        except (ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Could not parse {assignment}"
            ) from error

        if not isinstance(data, dict):
            raise RuntimeError(
                f"{assignment} is not a JSON object"
            )

        entries = data.get("list")

        if not isinstance(entries, list):
            raise RuntimeError(
                f"{assignment} does not contain a 'list' array"
            )

        if not entries:
            raise RuntimeError(
                f"{assignment} contains no entries"
            )

        logger.info(
            "Found %s with %d entries",
            assignment,
            len(entries),
        )

        return data

    raise RuntimeError(
        f"Could not find {assignment} in the page"
    )


def read_json(path: Path) -> dict:
    if not path.exists():
        return {"list": []}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Could not parse existing JSON file: {path}"
        ) from error

    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        raise RuntimeError(
            f"Invalid archive format in {path}"
        )

    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")


def archive_feed(current: dict, archive_path: Path) -> dict:
    archive = read_json(archive_path)

    archived_entries = archive["list"]
    current_entries = current["list"]

    existing_page_names = {
        entry.get("pageName")
        for entry in archived_entries
        if isinstance(entry, dict) and entry.get("pageName")
    }

    new_entries = []

    for entry in current_entries:
        if not isinstance(entry, dict):
            raise RuntimeError(
                f"Encountered a non-object entry in {archive_path}"
            )

        page_name = entry.get("pageName")

        if not page_name:
            raise RuntimeError(
                f"Encountered an entry without pageName in {archive_path}"
            )

        if page_name not in existing_page_names:
            archived_entries.append(entry)
            existing_page_names.add(page_name)
            new_entries.append(entry)

    logger.info(
        "%s: found %d new entries",
        archive_path,
        len(new_entries),
    )

    # Keep the archive ordered newest-first where possible.
    archived_entries.sort(
        key=lambda entry: entry.get("start_date_epoch", ""),
        reverse=True,
    )

    return archive


def main() -> None:
    page = fetch_page()

    news = extract_feed(page, "news")
    patch_notes = extract_feed(page, "updateNotes")

    news_archive = archive_feed(news, NEWS_ARCHIVE_FILE)
    patch_notes_archive = archive_feed(
        patch_notes,
        PATCH_NOTES_ARCHIVE_FILE,
    )

    write_json(NEWS_FILE, news)
    write_json(PATCH_NOTES_FILE, patch_notes)

    write_json(NEWS_ARCHIVE_FILE, news_archive)
    write_json(PATCH_NOTES_ARCHIVE_FILE, patch_notes_archive)

    logger.info(
        "News archive contains %d entries",
        len(news_archive["list"]),
    )

    logger.info(
        "Patch-note archive contains %d entries",
        len(patch_notes_archive["list"]),
    )

    logger.info("Scrape completed successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Scrape failed")
        raise

