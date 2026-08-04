import datetime
import email.utils
import html
import json
import re
import time
import urllib.request

# Target Date Range: August 12, 2021 up to Today (August 4, 2026)
START_DATE = datetime.date(2026, 7, 12)
END_DATE = datetime.date(2026, 8, 4)

# Browser headers to prevent 403 Forbidden blocking
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def strip_script_tags(html_code):
    """Deletes entire <script>...</script> and <style>...</style> blocks."""
    if not html_code:
        return ""
    clean = re.sub(
        r"<script\b[^>]*>.*?</script>", "", html_code, flags=re.DOTALL | re.IGNORECASE
    )
    clean = re.sub(
        r"<style\b[^>]*>.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE
    )
    return clean


def clean_html_tags(raw_html):
    """Strips HTML formatting tags like <i> or <p> and converts HTML entities."""
    if not raw_html:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(clean_text).strip()


def parse_webpage_entry(html_content, date_str):
    """Extracts clean word, pronunciation, partOfSpeech, definition, and example from web page."""

    # 1. Remove JavaScript tracking code and CSS stylesheets
    clean_html = strip_script_tags(html_content)

    # 2. Extract Word Title
    word_match = re.search(
        r'<h2 class="word-header-txt[^"]*">\s*([^<]+)\s*</h2>',
        clean_html,
        re.IGNORECASE,
    )
    if not word_match:
        word_match = re.search(
            r"<title>Word of the Day:\s*([^|]+)\|", clean_html, re.IGNORECASE
        )

    if not word_match:
        return None

    word = word_match.group(1).strip().lower()

    # 3. Extract Pronunciation (\loh-KWAY-shus\) from header tags or backslashes
    pronunciation = ""
    pron_match = re.search(
        r'<span class="word-syllables">\s*([^<]+)\s*</span>', clean_html
    )
    if pron_match:
        pronunciation = f"\\{pron_match.group(1).strip()}\\"
    else:
        slash_match = re.search(r"\\([a-zA-Z\s\-]+)\\", clean_html)
        if slash_match:
            pronunciation = f"\\{slash_match.group(1).strip()}\\"

    # 4. Extract Part of Speech (noun, verb, adjective, adverb) from header tag
    part_of_speech = "noun"
    pos_match = re.search(
        r'<span class="main-attr">\s*([^<]+)\s*</span>', clean_html, re.IGNORECASE
    )
    if pos_match:
        part_of_speech = pos_match.group(1).strip().lower()
    else:
        pos_fallback = re.search(
            r"\b(noun|verb|adjective|adverb)\b", clean_html, re.IGNORECASE
        )
        if pos_fallback:
            part_of_speech = pos_fallback.group(1).lower()

    # 5. Extract Full "What It Means" Section
    definition = "Definition available online."
    example = ""

    wim_match = re.search(
        r"<h2>What It Means</h2>\s*(.*?)\s*(?:<h2>|</article>|Did You Know)",
        clean_html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if wim_match:
        raw_wim_text = clean_html_tags(wim_match.group(1))

        # Split at '//' to isolate definition and primary example
        parts = [p.strip() for p in raw_wim_text.split("//") if p.strip()]

        if len(parts) > 0:
            definition = parts[0]
        if len(parts) > 1:
            example = parts[1]

    # Clean up trailing buttons
    definition = re.sub(r"See the entry\s*>", "", definition, flags=re.IGNORECASE).strip()
    example = re.sub(r"See the entry\s*>", "", example, flags=re.IGNORECASE).strip()

    return {
        "date": date_str,
        "word": word,
        "pronunciation": pronunciation,
        "partOfSpeech": part_of_speech,
        "definition": definition,
        "example": example,
    }


def accumulate_words():
    existing_words = []
    existing_word_dates = set()

    # Load existing words from words.json
    try:
        with open("words.json", "r", encoding="utf-8") as f:
            existing_words = json.load(f)
            existing_word_dates = {
                item["date"] for item in existing_words if "date" in item
            }
        print(f"Loaded {len(existing_words)} existing words from words.json.")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Starting fresh words.json file!")

    current_date = END_DATE
    total_days = (END_DATE - START_DATE).days + 1
    new_words_added = 0

    print(
        f"🚀 Fetching words from {END_DATE} down to {START_DATE} ({total_days} days)...\n"
    )

    while current_date >= START_DATE:
        date_str = current_date.strftime("%Y-%m-%d")

        # Skip date if already downloaded
        if date_str in existing_word_dates:
            current_date -= datetime.timedelta(days=1)
            continue

        url = f"https://www.merriam-webster.com/word-of-the-day/{date_str}"

        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req) as response:
                html_content = response.read().decode("utf-8")

            word_entry = parse_webpage_entry(html_content, date_str)

            if word_entry:
                existing_words.append(word_entry)
                existing_word_dates.add(date_str)
                new_words_added += 1

                print(
                    f"[{new_words_added}/{total_days}] Added '{word_entry['word']}' ({word_entry['partOfSpeech']}) for {date_str}"
                )

        except Exception as e:
            print(f"⚠️ Skipped {date_str}: {e}")

        current_date -= datetime.timedelta(days=1)
        time.sleep(0.2)

    # Sort dataset chronologically (newest dates first)
    existing_words.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Save to words.json
    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(existing_words, f, indent=2, ensure_ascii=False)

    print(
        f"\n🎉 Done! Added {new_words_added} new words. Total dataset size: {len(existing_words)} words."
    )


if __name__ == "__main__":
    accumulate_words()