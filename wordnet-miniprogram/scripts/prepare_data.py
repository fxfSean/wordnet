"""Build the mini-program catalog from the learner preview export.

The preview JSONL contains the NGSL WordNet definitions/examples that are safe
to ship.  This script adds the small amount of organisation the app needs:
book/unit/rank metadata, up to two examples per sense, optional Chinese
translations, and WordNet synonyms/antonyms/derivatives.

Extra open word lists (NAWL, TSL, BSL, NGSL-Spoken, New Dolch) are read from
``data/wordlists``.  Their words are matched against WordNet 3.0 and the most
frequent senses are used when a word is not already in the NGSL preview.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import sqlite3
from pathlib import Path

import extra_books
import exam_books
from roots_data import Roots
from wordnet_lookup import WordNet
from wordnet_relations import build_relations

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT.parent / "vocab-pipeline"
SOURCE = PIPELINE / "data/interim/learner-preview.jsonl"
OUTPUT = ROOT / "miniprogram/data/catalog.gz.js"
LEGACY_OUTPUTS = [ROOT / "miniprogram/data/catalog.js", ROOT / "miniprogram/data/books.js"]

BOOK_ID = "basic_ngsl_1_2"
BOOK_TITLE = "General English"
BOOK_SUBTITLE = "NGSL 1.2"
UNIT_SIZE = 50
MAX_EXAMPLES = 2
MAX_RELATIONS = 8
MAX_EXTRA_SENSES = 2
EXAM_NEW_WORD_BUDGET = 300


def load_jsonl(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            source = row.get("en") or row.get("source")
            target = row.get("zh") or row.get("target")
            if isinstance(source, str) and isinstance(target, str) and source and target:
                values[source] = target
    return values


def load_words() -> dict[str, dict]:
    db_path = PIPELINE / "data/state/pipeline.sqlite3"
    if not db_path.exists():
        return {}
    words: dict[str, dict] = {}
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as db:
            for _identifier, payload in db.execute("SELECT word_id, payload FROM p1_words"):
                word = json.loads(payload)
                words[word["lemma"]] = word
    except (sqlite3.Error, json.JSONDecodeError, KeyError):
        print("warning: could not read pipeline.sqlite3; ranks and synonyms will be omitted")
        return {}
    return words


def rank_for(word: dict, fallback: int) -> int:
    for link in word.get("links", []):
        if link.get("book_id") == BOOK_ID and isinstance(link.get("rank"), int):
            return link["rank"]
    return fallback


def source_for(word: dict) -> dict:
    for link in word.get("links", []):
        if link.get("book_id") == BOOK_ID:
            return link.get("source", {})
    return {}


def synonyms_for(word: dict, sense_id: str) -> list[str]:
    for candidate in word.get("candidates", []):
        if candidate.get("sense_id") != sense_id:
            continue
        own = word["lemma"].lower()
        values = []
        for synonym in candidate.get("synonyms", []):
            value = str(synonym).replace("_", " ").strip()
            if value and value.lower() != own and value not in values:
                values.append(value)
        return values[:MAX_RELATIONS]
    return []


def build_sense(sense: dict, word: dict, example_zh: dict[str, str],
                definition_zh: dict[str, str], relations: dict) -> dict:
    identifier = sense["sense_id"]
    examples = []
    for example in sense["examples_en"][:MAX_EXAMPLES]:
        item = {"en": example}
        translation = example_zh.get(example)
        if translation:
            item["zh"] = translation
        examples.append(item)
    item = {
        "id": identifier,
        "pos": sense["pos"],
        "definition": sense["definition_en"],
        "primary": sense["is_primary"],
    }
    translation = definition_zh.get(sense["definition_en"])
    if translation:
        item["definitionZh"] = translation
    if examples:
        item["examples"] = examples
    synonyms = synonyms_for(word, identifier)
    if synonyms:
        item["synonyms"] = synonyms
    relation = relations.get(identifier, {})
    if relation.get("antonyms"):
        item["antonyms"] = relation["antonyms"]
    if relation.get("derivatives"):
        item["derivatives"] = relation["derivatives"]
    if sense.get("phrases"):
        item["phrases"] = sense["phrases"]
    if sense.get("roots"):
        item["roots"] = sense["roots"]
    return item


def build() -> None:
    entries, words = [], set()
    with SOURCE.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            word = row["word"]
            if word in words:
                raise ValueError(f"Duplicate lemma: {word}")
            words.add(word)
            entries.append(row)

    pipeline_words = load_words()
    example_zh = load_jsonl(PIPELINE / "data/interim/example-zh.jsonl")
    definition_zh = load_jsonl(PIPELINE / "data/interim/definition-zh.jsonl")

    sense_ids = [
        sense["sense_id"]
        for entry in entries
        for sense in entry["senses"]
    ]
    relations = build_relations(PIPELINE / "data/raw/wordnet30", sense_ids)
    roots = Roots()

    catalog_by_word: dict[str, dict] = {}
    ngsl_ranks = []
    for index, row in enumerate(entries, start=1):
        word = row["word"]
        source = pipeline_words.get(word, {})
        rank = rank_for(source, index)
        ngsl_ranks.append(rank)
        senses = []
        ids = set()
        for sense in sorted(row["senses"], key=lambda item: item["display_order"]):
            identifier = sense["sense_id"]
            if identifier in ids:
                raise ValueError(f"Duplicate sense for {word}: {identifier}")
            ids.add(identifier)
            senses.append(build_sense(sense, source, example_zh, definition_zh, relations))
        if sum(sense["primary"] for sense in senses) > 2:
            raise ValueError(f"Too many primary senses for {word}")
        entry = {
            "word": word,
            "book": BOOK_ID,
            "rank": rank,
            "unit": (rank - 1) // UNIT_SIZE + 1,
            "books": [{"book": BOOK_ID, "rank": rank, "unit": (rank - 1) // UNIT_SIZE + 1}],
            "senses": senses,
        }
        word_roots = roots.lookup(word)
        if word_roots:
            entry["roots"] = word_roots
        catalog_by_word[word] = entry

    catalog = list(catalog_by_word.values())
    book_source = source_for(pipeline_words.get(catalog[0]["word"], {})) if catalog else {}
    books = [{
        "id": BOOK_ID,
        "title": BOOK_TITLE,
        "subtitle": BOOK_SUBTITLE,
        "description": "Core general English for everyday reading and listening.",
        "wordCount": len(catalog),
        "unitSize": UNIT_SIZE,
        "unitCount": (max(ngsl_ranks) + UNIT_SIZE - 1) // UNIT_SIZE if ngsl_ranks else 0,
        "source": {
            "name": book_source.get("source_name", "New General Service List"),
            "version": book_source.get("source_version", "1.2"),
            "license": book_source.get("license_id", "CC-BY-SA-4.0"),
            "url": book_source.get("url", ""),
            "authors": "Browne, Culligan & Phillips",
        },
    }]

    wordnet_dir = PIPELINE / "data/raw/wordnet30"
    wordnet = WordNet(wordnet_dir) if wordnet_dir.exists() else None
    if wordnet is None:
        print("warning: WordNet raw data not found; extra wordbooks will be empty")

    for book in extra_books.BOOKS:
        matched = 0
        for word, _source_rank in extra_books.read_rows(book):
            entry = catalog_by_word.get(word)
            if entry is not None and not entry["senses"]:
                continue
            if entry is None:
                if wordnet is None:
                    continue
                senses = wordnet.lookup(word)[:MAX_EXTRA_SENSES]
                if not senses:
                    continue
                for sense in senses:
                    translation = definition_zh.get(sense["definition"])
                    if translation:
                        sense["definitionZh"] = translation
                    for example in sense.get("examples", []):
                        translated = example_zh.get(example["en"])
                        if translated:
                            example["zh"] = translated
                entry = {
                    "word": word,
                    "book": book["id"],
                    "rank": matched + 1,
                    "unit": matched // UNIT_SIZE + 1,
                    "books": [],
                    "senses": senses,
                }
                word_roots = roots.lookup(word)
                if word_roots:
                    entry["roots"] = word_roots
                catalog_by_word[word] = entry
                catalog.append(entry)
            matched += 1
            entry["books"].append({
                "book": book["id"],
                "rank": matched,
                "unit": (matched - 1) // UNIT_SIZE + 1,
            })
        books.append({
            "id": book["id"],
            "title": book["title"],
            "subtitle": book["subtitle"],
            "description": book["description"],
            "wordCount": matched,
            "unitSize": UNIT_SIZE,
            "unitCount": (matched + UNIT_SIZE - 1) // UNIT_SIZE,
            "source": book["source"],
        })

    exam_counts = {book["id"]: 0 for book in exam_books.BOOKS}
    exam_candidates: dict[str, set[str]] = {}
    for book in exam_books.BOOKS:
        rows = exam_books.read_rows(book)
        if wordnet is not None:
            rows.sort(key=lambda item: (-wordnet.score(item[0]), item[1]))
        for word, _source_rank in rows:
            entry = catalog_by_word.get(word)
            if entry is not None and not entry["senses"]:
                continue
            if entry is not None:
                exam_counts[book["id"]] += 1
                entry["books"].append({
                    "book": book["id"],
                    "rank": exam_counts[book["id"]],
                    "unit": (exam_counts[book["id"]] - 1) // UNIT_SIZE + 1,
                })
            else:
                exam_candidates.setdefault(word, set()).add(book["id"])

    added = 0
    ranked_candidates = sorted(
        exam_candidates.items(),
        key=lambda item: (
            -len(item[1]),
            -(wordnet.score(item[0]) if wordnet else 0),
            item[0],
        ),
    )
    for word, book_ids in ranked_candidates:
        if added >= EXAM_NEW_WORD_BUDGET:
            break
        if wordnet is None:
            break
        senses = wordnet.lookup(word)[:MAX_EXTRA_SENSES]
        if not senses:
            continue
        for sense in senses:
            translation = definition_zh.get(sense["definition"])
            if translation:
                sense["definitionZh"] = translation
            for example in sense.get("examples", []):
                translated = example_zh.get(example["en"])
                if translated:
                    example["zh"] = translated
        entry = {
            "word": word,
            "book": sorted(book_ids)[0],
            "rank": 1,
            "unit": 1,
            "books": [],
            "senses": senses,
        }
        word_roots = roots.lookup(word)
        if word_roots:
            entry["roots"] = word_roots
        for book_id in sorted(book_ids):
            exam_counts[book_id] += 1
            entry["books"].append({
                "book": book_id,
                "rank": exam_counts[book_id],
                "unit": (exam_counts[book_id] - 1) // UNIT_SIZE + 1,
            })
        catalog_by_word[word] = entry
        catalog.append(entry)
        added += 1

    for book in exam_books.BOOKS:
        count = exam_counts[book["id"]]
        books.append({
            "id": book["id"],
            "title": book["title"],
            "subtitle": book["subtitle"],
            "description": book["description"],
            "wordCount": count,
            "unitSize": UNIT_SIZE,
            "unitCount": (count + UNIT_SIZE - 1) // UNIT_SIZE,
            "source": book["source"],
        })

    for entry in catalog:
        entry["books"].sort(key=lambda ref: (ref["book"] != BOOK_ID, ref["book"]))
        first = entry["books"][0]
        entry["book"] = first["book"]
        entry["rank"] = first["rank"]
        entry["unit"] = first["unit"]

    book_order = {book["id"]: index for index, book in enumerate(books)}
    catalog.sort(key=lambda entry: (book_order.get(entry["book"], 99), entry["rank"], entry["word"]))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"words": catalog, "books": books}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, 9, mtime=0)
    encoded = base64.b64encode(compressed).decode("ascii")
    OUTPUT.write_text('module.exports="' + encoded + '";\n', encoding="ascii")
    for legacy in LEGACY_OUTPUTS:
        legacy.unlink(missing_ok=True)
    summary = ", ".join(f"{book['id']}={book['wordCount']}" for book in books)
    print(
        f"Prepared {len(catalog)} unique words, "
        f"{sum(len(entry['senses']) for entry in catalog)} senses, "
        f"{sum(len(sense.get('examples', [])) for entry in catalog for sense in entry['senses'])} examples, "
        f"{len(example_zh)} example translations, {len(relations)} relation sets; "
        f"books: {summary}; {len(raw)} bytes raw, {len(compressed)} gzip, {len(encoded)} base64"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    build()
