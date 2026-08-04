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
    """Extracts date, pronunciation, definition, and primary example."""
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

    # 3. Cut off text starting from "Did you know?" and remove "See the entry >"
    text = re.split(r"Did you know\?", text, flags=re.IGNORECASE)[0].strip()
    text = re.sub(r"See the entry\s*>", "", text, flags=re.IGNORECASE)

    # 4. Remove secondary newspaper quotes section (anything after "Examples:")
    if "Examples:" in text:
        text = re.split(r"Examples:", text, flags=re.IGNORECASE, maxsplit=1)[0].strip()

    # 5. Separate Definition and Primary Example using '//'
    definition = ""
    example = ""

    if "//" in text:
        def_part, ex_part = text.split("//", 1)

        # Clean definition lines (remove header/pronunciation lines)
        def_lines = [
            line.strip()
            for line in def_part.split("\n")
            if line.strip() and "Word of the Day" not in line and "•" not in line
        ]
        definition = " ".join(def_lines)

        # Clean primary example sentence
        example = " ".join(
            [line.strip() for line in ex_part.split("\n") if line.strip()]
        )
    else:
        # Fallback if '//' separator is missing
        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip() and "Word of the Day" not in line and "•" not in line
        ]
        definition = lines[0] if lines else "Definition available online."
        example = " ".join(lines[1:]) if len(lines) > 1 else ""

    return iso_date, pronunciation, definition, example


def accumulate_words():
    existing_words = []
    existing_word_names = set()

    try:
        with open("words.json", "r", encoding="utf-8") as f:
            existing_words = json.load(f)
            existing_word_names = {
                item["word"].lower() for item in existing_words if "word" in item
            }
        print(f"Loaded {len(existing_words)} existing words from words.json.")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Starting fresh words.json file!")

    print("Connecting to Merriam-Webster RSS feed...")
    req = urllib.request.Request(
        MW_RSS_URL, headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req) as response:
        xml_data = response.read()

    root = ET.fromstring(xml_data)
    new_words_added = 0

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        description_elem = item.find("description")
        pub_date_elem = item.find("pubDate")

        if title_elem is None or description_elem is None:
            continue

        raw_title = title_elem.text or ""
        word = raw_title.split(":")[-1].strip().lower()

        if word in existing_word_names:
            continue

        raw_desc = description_elem.text or ""
        pub_date_str = pub_date_elem.text if pub_date_elem is not None else ""

        # Detect Part of Speech
        part_of_speech = "noun"
        pos_match = re.search(
            r"\b(noun|verb|adjective|adverb)\b", clean_html_tags(raw_desc), re.IGNORECASE
        )
        if pos_match:
            part_of_speech = pos_match.group(1).lower()

        # Parse extracted fields
        iso_date, pronunciation, definition, example = parse_entry_details(
            raw_desc, pub_date_str
        )

        existing_words.append(
            {
                "date": iso_date,
                "word": word,
                "pronunciation": pronunciation,
                "partOfSpeech": part_of_speech,
                "definition": definition,
                "example": example,
            }
        )
        existing_word_names.add(word)
        new_words_added += 1

    # Save to words.json without ascii escaping
    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(existing_words, f, indent=2, ensure_ascii=False)

    print(f"Done! Added {new_words_added} new words. Total dataset size: {len(existing_words)} words.")


if __name__ == "__main__":
    accumulate_words()