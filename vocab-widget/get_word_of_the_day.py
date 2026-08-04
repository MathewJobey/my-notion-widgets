import email.utils
from datetime import datetime
import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET

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

    # 1. Convert RSS publication date to ISO 8601 format (YYYY-MM-DD)
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

    # 5. Split text by '//' to cleanly separate definition and individual examples
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

    # Grab the first item from the RSS feed (today's word)
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

    # 1. Overwrite wordoftheday.json with today's single word object
    with open("vocab-widget\wordoftheday.json", "w", encoding="utf-8") as f:
        json.dump(today_word_obj, f, indent=2, ensure_ascii=False)
    print(f"Updated wordoftheday.json with today's word: '{word}' ({iso_date})")

    # 2. Append to words.json archive if not already present
    existing_words = []
    try:
        with open("words.json", "r", encoding="utf-8") as f:
            existing_words = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_words = []

    # Check if this date already exists in words.json
    date_exists = any(item.get("date") == iso_date for item in existing_words)

    if not date_exists:
        existing_words.insert(0, today_word_obj)  # Add to top of array
        existing_words.sort(key=lambda x: x.get("date", ""), reverse=True)

        with open("vocab-widget\words.json", "w", encoding="utf-8") as f:
            json.dump(existing_words, f, indent=2, ensure_ascii=False)
        print(f"Appended '{word}' to words.json archive.")
    else:
        print(f"'{word}' ({iso_date}) is already in words.json archive.")


if __name__ == "__main__":
    process_daily_word()