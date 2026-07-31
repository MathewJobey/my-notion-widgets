import json
import random
import wn

# Configuration: Adjust how many words to fetch each month
BATCH_SIZE = 500

# Map Wordnet single-letter codes to friendly display names
POS_MAP = {
    'n': 'noun',
    'v': 'verb',
    'a': 'adjective',
    's': 'adjective', # Satellite adjectives
    'r': 'adverb'
}

def generate_monthly_words():
    print("Downloading Open English Wordnet data...")
    # Automatically grabs the latest version available
    wn.download("oewn")
    oewn = wn.Wordnet("oewn")

    extracted_words = []
    seen_words = set()

    print("Extracting valid words with definitions and examples...")

    # Step 1: Loop through all synsets (meaning groups)
    for synset in oewn.synsets():
        definition = synset.definition()
        examples = synset.examples()

        # Step 2: Require both a definition and at least 1 example sentence
        if definition and len(examples) > 0:
            for sense in synset.senses():
                word_text = sense.word().lemma().lower()

                # Step 3: Filter for clean single words longer than 3 letters
                if "_" not in word_text and " " not in word_text and len(word_text) > 3:
                    if word_text not in seen_words:
                        seen_words.add(word_text)

                        # Convert single-letter POS to friendly word
                        raw_pos = synset.pos
                        friendly_pos = POS_MAP.get(raw_pos, raw_pos)

                        extracted_words.append({
                            "word": word_text,
                            "partOfSpeech": friendly_pos,
                            "phonetic": "",
                            "definition": definition,
                            "example": examples[0]
                        })

    print(f"Total valid candidate words found: {len(extracted_words)}")

    # Step 4: Shuffle the entire candidate list for randomness
    random.shuffle(extracted_words)

    # Step 5: Crop down to our monthly batch size
    monthly_batch = extracted_words[:BATCH_SIZE]

    # Step 6: Overwrite words.json with the new batch
    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(monthly_batch, f, indent=2)

    print(f"Successfully wrote {len(monthly_batch)} new words to words.json!")

if __name__ == "__main__":
    generate_monthly_words()