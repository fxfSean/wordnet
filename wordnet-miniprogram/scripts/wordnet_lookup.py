"""Minimal WordNet 3.0 lookup used to build extra wordbooks.

This intentionally only reads the raw WordNet data files that are already used by
the vocab pipeline.  It selects the most frequent senses by WordNet tag counts,
so a new wordbook can ship without an AI sense-selection pass.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

POS_FILES = {"noun": "data.noun", "verb": "data.verb", "adj": "data.adj", "adv": "data.adv"}
POS_INDEX = {"noun": "index.noun", "verb": "index.verb", "adj": "index.adj", "adv": "index.adv"}
POS_CODES = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}
SENSE_POS = {"1": "noun", "2": "verb", "3": "adj", "4": "adv", "5": "adj"}
POS_ORDER = {"noun": 0, "verb": 1, "adj": 2, "adv": 3}
MAX_SENSES = 4
MAX_EXAMPLES = 2
MAX_RELATIONS = 8


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(char for char in word if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", word.replace("_", " ")).strip().lower()


def _clean(word: str) -> str:
    return word.split("(")[0].replace("_", " ").strip().lower()


class WordNet:
    def __init__(self, directory: Path):
        self.directory = directory
        self.synsets: dict[tuple[str, int], dict] = {}
        self.index: dict[str, list[tuple[str, int]]] = {}
        self.tag_counts: dict[tuple[str, str, int], int] = {}
        self._read_tag_counts()
        self._read_synsets()
        self._read_index()

    def _read_tag_counts(self) -> None:
        path = self.directory / "index.sense"
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) != 4:
                continue
            sense_key, offset, _sense_number, count = fields
            lemma, sense_type = sense_key.split("%", 1)
            pos = SENSE_POS.get(sense_type[0]) or POS_CODES.get(sense_type[0])
            if pos:
                self.tag_counts[(normalize(lemma), pos, int(offset))] = int(count)

    def _read_synsets(self) -> None:
        for pos, name in POS_FILES.items():
            path = self.directory / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith(" "):
                    continue
                fields, separator, gloss = line.partition("|")
                if not separator:
                    continue
                tokens = fields.split()
                if len(tokens) < 5:
                    continue
                offset = int(tokens[0])
                ss_type = tokens[2]
                count = int(tokens[3], 16)
                cursor = 4
                words = []
                for _ in range(count):
                    words.append(_clean(tokens[cursor]))
                    cursor += 2
                pointer_count = int(tokens[cursor])
                cursor += 1
                pointers = []
                for _ in range(pointer_count):
                    symbol = tokens[cursor]
                    target = int(tokens[cursor + 1])
                    target_pos = POS_CODES.get(tokens[cursor + 2], tokens[cursor + 2])
                    pointers.append((symbol, target, target_pos))
                    cursor += 4
                gloss = gloss.strip()
                parts = re.split(r';\s*(?=")', gloss, maxsplit=1)
                definition = parts[0].strip()
                examples = re.findall(r'"([^"]*)"', parts[1]) if len(parts) == 2 else []
                key = ("adj" if ss_type in {"a", "s"} else pos, offset)
                self.synsets[key] = {
                    "words": words,
                    "definition": definition,
                    "examples": examples[:MAX_EXAMPLES],
                    "pointers": pointers,
                }

    def _read_index(self) -> None:
        for pos, name in POS_INDEX.items():
            path = self.directory / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith(" "):
                    continue
                fields = line.split()
                if len(fields) < 6:
                    continue
                lemma = normalize(fields[0])
                count = int(fields[2])
                pointer_count = int(fields[3])
                offsets = fields[4 + pointer_count + 2 :]
                if len(offsets) < count:
                    continue
                for offset in offsets[:count]:
                    self.index.setdefault(lemma, []).append((pos, int(offset)))

    def lookup(self, word: str) -> list[dict]:
        lemma = normalize(word)
        candidates = []
        seen = set()
        for pos, offset in self.index.get(lemma, []):
            if (pos, offset) in seen:
                continue
            seen.add((pos, offset))
            synset = self.synsets.get((pos, offset))
            if not synset:
                continue
            candidates.append({
                "pos": pos,
                "offset": offset,
                **synset,
                "count": self.tag_counts.get((lemma, pos, offset), 0),
            })
        candidates.sort(key=lambda item: (-item["count"], POS_ORDER.get(item["pos"], 9), item["offset"]))
        return [self._sense(lemma, item, index) for index, item in enumerate(candidates[:MAX_SENSES])]

    def score(self, word: str) -> int:
        lemma = normalize(word)
        return sum(
            self.tag_counts.get((lemma, pos, offset), 0)
            for pos, offset in self.index.get(lemma, [])
        )

    def _sense(self, lemma: str, item: dict, index: int) -> dict:
        own = set(item["words"])
        antonyms: list[str] = []
        derivatives: list[str] = []
        for symbol, target, target_pos in item["pointers"]:
            if symbol not in {"!", "+"}:
                continue
            target_words = self.synsets.get((target_pos, target), {}).get("words", [])
            bucket = antonyms if symbol == "!" else derivatives
            for word in target_words:
                if word and word not in own and word not in bucket:
                    bucket.append(word)
        sense = {
            "id": f"wn30:{item['pos']}:{item['offset']:08d}",
            "pos": item["pos"],
            "definition": item["definition"],
            "primary": index == 0,
            "examples": [{"en": example} for example in item["examples"]],
            "synonyms": [word for word in item["words"] if word != lemma][:MAX_RELATIONS],
        }
        if antonyms:
            sense["antonyms"] = antonyms[:MAX_RELATIONS]
        if derivatives:
            sense["derivatives"] = derivatives[:MAX_RELATIONS]
        return sense
