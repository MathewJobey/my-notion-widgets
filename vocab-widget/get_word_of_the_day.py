import email.utils
from datetime import datetime
import html
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

# Force Windows Terminal to use UTF-8 encoding for prints
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Fallback for older Python versions

# Dynamically locate the directory where this script lives
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Build absolute paths for both JSON files
WORD_OF_THE_DAY_PATH = os.path.join(SCRIPT_DIR, "wordoftheday.json")
WORDS_ARCHIVE_PATH = os.path.join(SCRIPT_DIR, "words.json")

MW_RSS_URL = "https://www.merriam-webster.com/wotd/feed/rss2"


def clean_html_tags(raw_html):
    """Strips HTML formatting tags like <i> or <p> and converts HTML entities."""
    if not raw_html:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(clean_text).strip()


def parse_entry_details(raw_desc, pub_date_str):
    """Extracts date, pronunciation, definition, and a single clean example sentence."""
    text = clean_html_tags(raw_desc)

    # 1. Convert RSS publication date to ISO format (YYYY-MM-DD)
    iso_date = ""
    if pub_date_str:
        try:
            parsed_time = email.utils.parsedate_to_datetime(pub_date_str)
            iso_date = parsed_time.strftime("%Y-%m-%d")
        except Exception:
            iso_date = datetime.today().strftime("%Y-%m-%d")

    # 2. Extract Pronunciation (text inside backslashes)
    pronunciation = ""
    pron_match = re.search(r"\\(.*?)\\", text)
    if pron_match:
        pronunciation = f"\\{pron_match.group(1)}\\"

    # 3. Cut off 'Did you know?' essays and 'See the entry >' buttons
    text = re.split(r"Did you know\?", text, flags=re.IGNORECASE)[0].strip()
    text = re.sub(r"See the entry\s*>", "", text, flags=re.IGNORECASE)

    # 4. Remove secondary newspaper quotes section
    if "Examples:" in text:
        text = re.split(r"Examples:", text, flags=re.IGNORECASE, maxsplit=1)[0].strip()

    # 5. Split text by '//' to cleanly separate definition and example
    parts = [p.strip() for p in text.split("//") if p.strip()]

    definition = ""
    example = ""

    if len(parts) > 0:
        def_part = parts[0]
        def_lines = [
            line.strip()
            for line in def_part.split("\n")
            if line.strip() and "Word of the Day" not in line and "•" not in line
        ]
        definition = " ".join(def_lines)

    if len(parts) > 1:
        ex_part = parts[1]
        ex_lines = [line.strip() for line in ex_part.split("\n") if line.strip()]
        example = " ".join(ex_lines)

    return iso_date, pronunciation, definition, example


def process_daily_word():
    print("Connecting to Merriam-Webster RSS feed...")
    req = urllib.request.Request(
        MW_RSS_URL, headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)

    item = root.find(".//item")
    if item is None:
        print("Error: Could not find any word items in the RSS feed.")
        return

    title_elem = item.find("title")
    description_elem = item.find("description")
    pub_date_elem = item.find("pubDate")

    raw_title = title_elem.text or "" if title_elem is not None else ""
    word = raw_title.split(":")[-1].strip().lower()
    raw_desc = description_elem.text or "" if description_elem is not None else ""
    pub_date_str = pub_date_elem.text if pub_date_elem is not None else ""

    # Detect Part of Speech
    part_of_speech = "noun"
    pos_match = re.search(
        r"\b(noun|verb|adjective|adverb)\b", clean_html_tags(raw_desc), re.IGNORECASE
    )
    if pos_match:
        part_of_speech = pos_match.group(1).lower()

    # Parse formatted fields
    iso_date, pronunciation, definition, example = parse_entry_details(
        raw_desc, pub_date_str
    )

    today_word_obj = {
        "date": iso_date,
        "word": word,
        "pronunciation": pronunciation,
        "partOfSpeech": part_of_speech,
        "definition": definition,
        "example": example,
    }

    # 1. Save single object to wordoftheday.json
    with open(WORD_OF_THE_DAY_PATH, "w", encoding="utf-8") as f:
        json.dump(today_word_obj, f, indent=2, ensure_ascii=False)
    print(f"Updated wordoftheday.json with today's word: '{word}' ({iso_date})")

    # 2. Read archive from words.json
    existing_words = []
    try:
        with open(WORDS_ARCHIVE_PATH, "r", encoding="utf-8") as f:
            existing_words = json.load(f)
        print(f"Loaded {len(existing_words)} existing words from words.json.")
    except (FileNotFoundError, json.JSONDecodeError):
        print("words.json not found or empty. Starting a fresh list!")
        existing_words = []

    # 3. Check if word or date already exists
    is_already_present = any(
        item.get("word", "").lower() == word.lower() or item.get("date") == iso_date
        for item in existing_words
    )

    # 4. Append to words.json only if missing
    if not is_already_present:
        existing_words.insert(0, today_word_obj)
        existing_words.sort(key=lambda x: x.get("date", ""), reverse=True)

        with open(WORDS_ARCHIVE_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_words, f, indent=2, ensure_ascii=False)
        print(
            f"[SUCCESS] Appended '{word}' ({iso_date}) to words.json archive. Total words: {len(existing_words)}"
        )
    else:
        print(
            f"[INFO] '{word}' ({iso_date}) is already present in words.json. Archive left untouched."
        )


if __name__ == "__main__":
    process_daily_word()