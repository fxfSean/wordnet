"""Open word lists from the New General Service List project.

All lists are released under CC BY-SA 4.0.  The raw CSV snapshots live in
``wordnet-miniprogram/data/wordlists``; this module only normalizes them.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDLIST_DIR = ROOT / "data/wordlists"

BOOKS = [
    {
        "id": "nawl_1_2",
        "title": "Academic English",
        "subtitle": "NAWL 1.2",
        "description": "Academic words for university reading, lectures and writing.",
        "file": "nawl.csv",
        "word": "Word",
        "rank": "Rank",
        "source": {
            "name": "New Academic Word List",
            "version": "1.2",
            "license": "CC-BY-SA-4.0",
            "url": "https://www.newgeneralservicelist.com/new-academic-word-list",
            "authors": "Browne, Culligan & Phillips",
        },
    },
    {
        "id": "tsl_1_2",
        "title": "TOEIC English",
        "subtitle": "TSL 1.2",
        "description": "High-frequency words for TOEIC listening and reading.",
        "file": "tsl.csv",
        "word": "Word",
        "rank": "TSL Rank",
        "source": {
            "name": "TOEIC Service List",
            "version": "1.2",
            "license": "CC-BY-SA-4.0",
            "url": "https://www.newgeneralservicelist.com/toeic-service-list",
            "authors": "Browne & Culligan",
        },
    },
    {
        "id": "bsl_1_2",
        "title": "Business English",
        "subtitle": "BSL 1.2",
        "description": "Business vocabulary for meetings, finance and the workplace.",
        "file": "bsl.csv",
        "word": "Word",
        "rank": "BSL Rank",
        "source": {
            "name": "Business Service List",
            "version": "1.2",
            "license": "CC-BY-SA-4.0",
            "url": "https://www.newgeneralservicelist.com/business-service-list",
            "authors": "Browne & Culligan",
        },
    },
    {
        "id": "ngsl_spoken_1_2",
        "title": "Spoken English",
        "subtitle": "NGSL-Spoken 1.2",
        "description": "Everyday conversation words, ordered by spoken frequency.",
        "file": "spoken.csv",
        "word": "Lemma",
        "rank": "Rank",
        "source": {
            "name": "NGSL-Spoken",
            "version": "1.2",
            "license": "CC-BY-SA-4.0",
            "url": "https://www.newgeneralservicelist.com/ngsl-spoken",
            "authors": "New General Service List Project",
        },
    },
    {
        "id": "new_dolch_1_1",
        "title": "Children's English",
        "subtitle": "New Dolch List 1.1",
        "description": "A gentle first wordbook for younger learners.",
        "file": "dolch.csv",
        "word": "Word",
        "rank": "Rank",
        "source": {
            "name": "New Dolch List",
            "version": "1.1",
            "license": "CC-BY-SA-4.0",
            "url": "https://www.newgeneralservicelist.com/new-dolch-list",
            "authors": "New General Service List Project",
        },
    },
]


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(char for char in word if not unicodedata.combining(char))
    return " ".join(word.replace("_", " ").split()).strip().lower()


def read_rows(book: dict) -> list[tuple[str, int]]:
    path = WORDLIST_DIR / book["file"]
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"Cannot decode {path}")
    entries: dict[str, int] = {}
    for index, row in enumerate(csv.DictReader(io.StringIO(text))):
        word = normalize(row.get(book["word"]) or "")
        if not word:
            continue
        raw_rank = (row.get(book["rank"]) or "").strip().rstrip(".")
        try:
            rank = int(float(raw_rank))
        except ValueError:
            rank = index + 1
        if word not in entries or rank < entries[word]:
            entries[word] = rank
    return sorted(entries.items(), key=lambda item: (item[1], item[0]))
