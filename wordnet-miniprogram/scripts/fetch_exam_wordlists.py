"""Refresh the compact CET-4/CET-6/考研/IELTS/TOEFL word-list snapshots.

Sources:
- KyleBing/english-vocabulary (BSD-3-Clause): CET-4, CET-6, 考研, TOEFL
- hefengxian/ielts-vocabulary (MIT): IELTS

The upstream files contain translations and examples; this script keeps only
``word,rank`` so the repository stays small.  Definitions/examples come from
WordNet at build time.
"""
from __future__ import annotations

import csv
import json
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/wordlists"

KYLE = "https://cdn.jsdelivr.net/gh/KyleBing/english-vocabulary@master/json/"
FILES = {
    "exam_cet4.csv": (KYLE + "3-CET4-%E9%A1%BA%E5%BA%8F.json", "json"),
    "exam_cet6.csv": (KYLE + "4-CET6-%E9%A1%BA%E5%BA%8F.json", "json"),
    "exam_kaoyan.csv": (KYLE + "5-%E8%80%83%E7%A0%94-%E9%A1%BA%E5%BA%8F.json", "json"),
    "exam_toefl.csv": (KYLE + "6-%E6%89%98%E7%A6%8F-%E9%A1%BA%E5%BA%8F.json", "json"),
    "exam_ielts.csv": ("https://raw.githubusercontent.com/hefengxian/ielts-vocabulary/main/vocabulary.txt", "text"),
}


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(char for char in word if not unicodedata.combining(char))
    return " ".join(word.replace("_", " ").split()).strip().lower()


def read_words(url: str, kind: str) -> list[str]:
    data = urllib.request.urlopen(url, timeout=120).read()
    words: list[str] = []
    seen: set[str] = set()
    if kind == "json":
        for row in json.loads(data):
            word = normalize(str(row.get("word") or ""))
            if word and word not in seen:
                seen.add(word)
                words.append(word)
    else:
        for line in data.decode("utf-8", "replace").splitlines():
            if "|" not in line:
                continue
            word = normalize(line.split("|", 1)[0])
            if word and word not in seen:
                seen.add(word)
                words.append(word)
    return words


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (url, kind) in FILES.items():
        words = read_words(url, kind)
        with (OUT / name).open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["word", "rank"])
            for index, word in enumerate(words, 1):
                writer.writerow([word, index])
        print(name, len(words))


if __name__ == "__main__":
    main()
