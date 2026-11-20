"""Build word-level roots from an open Greek/Latin morpheme dataset.

Source: jupsh/anki-word-roots (CC BY-SA 4.0), adapted from Wikipedia's
"List of Greek and Latin roots in English".  The CSV snapshots live in
``data/wordlists/morphemes.csv`` and ``decode.csv``.
"""
from __future__ import annotations

import csv
import io
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDLIST_DIR = ROOT / "data/wordlists"

# High-frequency affixes with unambiguous learner-facing meanings.  This avoids
# choosing a wrong homonymous morpheme from the larger Wikipedia list (for
# example ``un-`` in "unhappy" is negation, not the Latin numeral "one").
PREFIXES = {
    "un": "not, opposite of",
    "re": "again, back",
    "pre": "before",
    "post": "after",
    "dis": "not, opposite of",
    "mis": "wrongly, badly",
    "over": "too much, above",
    "under": "below, not enough",
    "sub": "under, below",
    "inter": "between, among",
    "trans": "across, through",
    "anti": "against, opposed to",
    "auto": "self",
    "bi": "two",
    "co": "together, with",
    "com": "together, with",
    "con": "together, with",
    "de": "down, away",
    "ex": "out, away from",
    "ab": "away from, off",
    "abs": "away from, off",
    "fore": "before, in front",
    "multi": "many",
    "semi": "half",
    "micro": "small",
    "macro": "large",
    "tele": "far, at a distance",
    "mono": "one",
    "poly": "many",
    "hyper": "over, too much",
    "hypo": "under, too little",
}
SUFFIXES = {
    "able": "able to be",
    "ible": "able to be",
    "al": "relating to",
    "ial": "relating to",
    "ance": "state or quality",
    "ence": "state or quality",
    "er": "person or thing that does",
    "or": "person or thing that does",
    "ful": "full of",
    "ify": "make, cause",
    "ize": "make, cause",
    "ise": "make, cause",
    "ion": "act or process",
    "tion": "act or process",
    "sion": "act or process",
    "ity": "state or quality",
    "less": "without",
    "ly": "in a ... way",
    "ment": "result or state",
    "ness": "state or quality",
    "ous": "full of, having",
    "ive": "having a tendency to",
    "ic": "relating to, like",
    "ish": "somewhat, like",
    "ward": "in the direction of",
}


def normalize(word: str) -> str:
    word = unicodedata.normalize("NFKD", word)
    word = "".join(char for char in word if not unicodedata.combining(char))
    return " ".join(word.replace("_", " ").split()).strip().lower()


def _read_csv(name: str) -> list[dict]:
    path = WORDLIST_DIR / name
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


class Roots:
    def __init__(self):
        self.morphemes = _read_csv("morphemes.csv")
        self.by_id = {row["id"]: row for row in self.morphemes}
        self.decode = {normalize(row["word"]): row for row in _read_csv("decode.csv")}
        self.roots = []
        self.root_forms = []
        for row in self.morphemes:
            if row.get("core") != "y" or row.get("kind") != "root":
                continue
            for form in row["forms"].split(","):
                form = form.strip().strip("-").lower()
                if len(form) >= 3:
                    self.root_forms.append(form)
                if len(form) >= 4:
                    self.roots.append((form, row["meaning"]))
        self.roots.sort(key=lambda item: -len(item[0]))

    def lookup(self, word: str) -> list[dict]:
        word = normalize(word)
        result: list[dict] = []

        explicit = self.decode.get(word)
        if explicit:
            for part in str(explicit.get("parts") or "").split(" + "):
                left = part.split(":")[0]
                identifier = left.split("=")[1] if "=" in left else ""
                form = left.split("=")[0] if "=" in left else left
                source = self.by_id.get(identifier)
                if not source:
                    continue
                kind = source["kind"]
                display = form
                if kind == "prefix":
                    display += "-"
                elif kind == "suffix":
                    display = "-" + display
                result.append({"form": display, "meaning": source["meaning"], "kind": kind})

        if len(word) >= 5:
            for prefix in sorted(PREFIXES, key=len, reverse=True):
                if word.startswith(prefix) and len(word) - len(prefix) >= 3:
                    longer_root = any(
                        word.startswith(form) and len(form) > len(prefix)
                        for form in self.root_forms
                    )
                    if not longer_root:
                        result.append({"form": prefix + "-", "meaning": PREFIXES[prefix], "kind": "prefix"})
                    break
            for suffix in sorted(SUFFIXES, key=len, reverse=True):
                if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                    result.append({"form": "-" + suffix, "meaning": SUFFIXES[suffix], "kind": "suffix"})
                    break

        if len(word) >= 6:
            for form, meaning in self.roots:
                if form in word:
                    result.append({"form": form, "meaning": meaning, "kind": "root"})
                    if len(result) >= 3:
                        break

        seen = set()
        unique = []
        for item in result:
            key = (item["form"], item["meaning"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        final = []
        for item in unique:
            contained = any(
                other is not item
                and len(other["form"].strip("-")) > len(item["form"].strip("-"))
                and item["form"].strip("-") in other["form"].strip("-")
                for other in unique
            )
            if not contained:
                final.append(item)
        return final[:3]
