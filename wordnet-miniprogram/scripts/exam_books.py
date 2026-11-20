"""Exam word lists gathered from open GitHub repositories.

CET-4/CET-6/Postgraduate/TOEFL snapshots come from KyleBing/english-vocabulary
(BSD-3-Clause).  IELTS comes from hefengxian/ielts-vocabulary (MIT).  Only the
word lists are used; definitions/examples still come from WordNet.
"""
from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDLIST_DIR = ROOT / "data/wordlists"

BOOKS = [
    {
        "id": "cet4",
        "title": "CET-4",
        "subtitle": "College English Test Band 4 · Core",
        "description": "Core vocabulary for the CET-4 exam.",
        "file": "exam_cet4.csv",
        "source": {
            "name": "KyleBing/english-vocabulary",
            "version": "master",
            "license": "BSD-3-Clause",
            "url": "https://github.com/KyleBing/english-vocabulary",
            "authors": "KyleBing",
        },
    },
    {
        "id": "cet6",
        "title": "CET-6",
        "subtitle": "College English Test Band 6 · Core",
        "description": "Core vocabulary for the CET-6 exam.",
        "file": "exam_cet6.csv",
        "source": {
            "name": "KyleBing/english-vocabulary",
            "version": "master",
            "license": "BSD-3-Clause",
            "url": "https://github.com/KyleBing/english-vocabulary",
            "authors": "KyleBing",
        },
    },
    {
        "id": "kaoyan",
        "title": "Postgraduate",
        "subtitle": "考研英语 · Core",
        "description": "Core vocabulary for the postgraduate entrance exam.",
        "file": "exam_kaoyan.csv",
        "source": {
            "name": "KyleBing/english-vocabulary",
            "version": "master",
            "license": "BSD-3-Clause",
            "url": "https://github.com/KyleBing/english-vocabulary",
            "authors": "KyleBing",
        },
    },
    {
        "id": "ielts",
        "title": "IELTS",
        "subtitle": "Academic & General Training · Core",
        "description": "Thematic IELTS vocabulary for reading and writing.",
        "file": "exam_ielts.csv",
        "source": {
            "name": "hefengxian/ielts-vocabulary",
            "version": "main",
            "license": "MIT",
            "url": "https://github.com/hefengxian/ielts-vocabulary",
            "authors": "hefengxian",
        },
    },
    {
        "id": "toefl",
        "title": "TOEFL",
        "subtitle": "Test of English as a Foreign Language · Core",
        "description": "Core vocabulary for TOEFL reading and listening.",
        "file": "exam_toefl.csv",
        "source": {
            "name": "KyleBing/english-vocabulary",
            "version": "master",
            "license": "BSD-3-Clause",
            "url": "https://github.com/KyleBing/english-vocabulary",
            "authors": "KyleBing",
        },
    },
]


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(char for char in word if not unicodedata.combining(char))
    return " ".join(word.replace("_", " ").split()).strip().lower()


def read_rows(book: dict) -> list[tuple[str, int]]:
    path = WORDLIST_DIR / book["file"]
    rows: dict[str, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for index, row in enumerate(csv.DictReader(file)):
            word = normalize(row.get("word") or "")
            if not word:
                continue
            try:
                rank = int(row.get("rank") or index + 1)
            except ValueError:
                rank = index + 1
            if word not in rows or rank < rows[word]:
                rows[word] = rank
    return sorted(rows.items(), key=lambda item: (item[1], item[0]))
