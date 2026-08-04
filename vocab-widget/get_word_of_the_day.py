import email.utils
from datetime import datetime
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

# Force Windows Terminal to use UTF-8 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_OF_THE_DAY_PATH = os.path.join(SCRIPT_DIR, "wordoftheday.json")
WORDS_ARCHIVE_PATH = os.path.join(SCRIPT_DIR, "words.json")

MW_RSS_URL = "https://www.merriam-webster.com/wotd/feed/rss2"


def clean_html_tags(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(clean_text).strip()


def parse_entry_details(raw_desc, pub_date_str):
    text = clean_html_tags(raw_desc)

    iso_date = ""
    if pub_date_str:
        try:
            parsed_time = email.utils.parsedate_to_datetime(pub_date_str)
            iso_date = parsed_time.strftime("%Y-%m-%d")
        except Exception:
            iso_date = datetime.today().strftime("%Y-%m-%d")

    pronunciation = ""
    pron_match = re.search(r"\\(.*?)\\", text)
    if pron_match:
        pronunciation = f"\\{pron_match.group(1)}\\"

    text = re.split(r"Did you know\?", text, flags=re.IGNORECASE)[0].strip()
    text = re.sub(r"See the entry\s*>", "", text, flags=re.IGNORECASE)

    if "Examples:" in text:
        text = re.split(r"Examples:", text, flags=re.IGNORECASE, maxsplit=1)[0].strip()

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

    # 1. Retry network connection up to 3 times
    xml_data = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req) as response:
                xml_data = response.read()
            break
        except Exception as e:
            if attempt < 2:
                print(f"[RETRY] Network attempt {attempt + 1} failed ({e}). Retrying in 3s...")
                time.sleep(3)
            else:
                print(f"[ERROR] Failed to fetch RSS feed after 3 attempts: {e}")
                sys.exit(1)

    root = ET.fromstring(xml_data)
    items = root.findall(".//item")

    if not items:
        print("[ERROR] No word items found in RSS feed.")
        return

    # 2. Read existing archive
    existing_words = []
    try:
        with open(WORDS_ARCHIVE_PATH, "r", encoding="utf-8") as f:
            existing_words = json.load(f)
        print(f"Loaded {len(existing_words)} existing words from words.json.")
    except (FileNotFoundError, json.JSONDecodeError):
        existing_words = []

    existing_dates = {item.get("date") for item in existing_words if "date" in item}
    existing_word_names = {item.get("word", "").lower() for item in existing_words if "word" in item}

    new_words_added = 0
    latest_word_obj = None

    # 3. Loop through ALL items in the RSS feed (last ~7 days)
    for idx, item in enumerate(items):
        title_elem = item.find("title")
        description_elem = item.find("description")
        pub_date_elem = item.find("pubDate")

        raw_title = title_elem.text or "" if title_elem is not None else ""
        word = raw_title.split(":")[-1].strip().lower()
        raw_desc = description_elem.text or "" if description_elem is not None else ""
        pub_date_str = pub_date_elem.text if pub_date_elem is not None else ""

        part_of_speech = "noun"
        pos_match = re.search(
            r"\b(noun|verb|adjective|adverb)\b", clean_html_tags(raw_desc), re.IGNORECASE
        )
        if pos_match:
            part_of_speech = pos_match.group(1).lower()

        iso_date, pronunciation, definition, example = parse_entry_details(
            raw_desc, pub_date_str
        )

        word_obj = {
            "date": iso_date,
            "word": word,
            "pronunciation": pronunciation,
            "partOfSpeech": part_of_speech,
            "definition": definition,
            "example": example,
        }

        # Keep track of the top item (today's word) for wordoftheday.json
        if idx == 0:
            latest_word_obj = word_obj

        # Check if missing from archive
        if iso_date not in existing_dates and word.lower() not in existing_word_names:
            existing_words.append(word_obj)
            existing_dates.add(iso_date)
            existing_word_names.add(word.lower())
            new_words_added += 1
            print(f"[CATCH-UP] Added missing word: '{word}' ({iso_date})")

    # 4. Save today's word to wordoftheday.json
    if latest_word_obj:
        with open(WORD_OF_THE_DAY_PATH, "w", encoding="utf-8") as f:
            json.dump(latest_word_obj, f, indent=2, ensure_ascii=False)
        print(f"Updated wordoftheday.json with today's word: '{latest_word_obj['word']}' ({latest_word_obj['date']})")

    # 5. Save updated archive if new words were caught up
    if new_words_added > 0:
        existing_words.sort(key=lambda x: x.get("date", ""), reverse=True)
        with open(WORDS_ARCHIVE_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_words, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Appended {new_words_added} new/missed word(s) to words.json. Total words: {len(existing_words)}")
    else:
        print("[INFO] No missing words found in RSS feed. Archive is up to date.")


if __name__ == "__main__":
    process_daily_word()