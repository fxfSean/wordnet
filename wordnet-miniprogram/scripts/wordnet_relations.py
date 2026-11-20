"""Extract antonyms and derivationally related words from WordNet 3.0 data files.

The mini-program catalog only carries WordNet synset IDs.  This module keeps the
build self-contained by reading the raw WordNet data that already exists in the
workspace, without copying dictionary text into the app.
"""
from __future__ import annotations

from pathlib import Path

POS_CODES = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}
DATA_FILES = {"noun": "data.noun", "verb": "data.verb", "adj": "data.adj", "adv": "data.adv"}


def _clean(word: str) -> str:
    return word.split("(")[0].replace("_", " ").strip().lower()


def _parse(directory: Path):
    synsets: dict[tuple[str, int], tuple[list[str], list[tuple[str, int, str]]]] = {}
    for pos, name in DATA_FILES.items():
        path = directory / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as file:
            for line in file:
                if not line or line.startswith(" "):
                    continue
                fields, separator, _gloss = line.partition("|")
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
                key = ("adj" if ss_type in {"a", "s"} else pos, offset)
                synsets[key] = (words, pointers)
    return synsets


def build_relations(directory: Path, sense_ids: list[str] | None = None) -> dict[str, dict[str, list[str]]]:
    """Return ``{sense_id: {antonyms: [...], derivatives: [...]}}``.

    Only antonym (``!``) and derivationally related form (``+``) pointers are
    used.  The result is intentionally small and optional; missing raw data
    simply yields no relations.
    """
    if not directory.exists():
        return {}
    synsets = _parse(directory)
    wanted = set(sense_ids) if sense_ids else None
    result: dict[str, dict[str, list[str]]] = {}
    for (pos, offset), (words, pointers) in synsets.items():
        sense_id = f"wn30:{pos}:{offset:08d}"
        if wanted is not None and sense_id not in wanted:
            continue
        own = set(words)
        antonyms: list[str] = []
        derivatives: list[str] = []
        for symbol, target, target_pos in pointers:
            if symbol not in {"!", "+"}:
                continue
            target_words = synsets.get((target_pos, target), ([], []))[0]
            bucket = antonyms if symbol == "!" else derivatives
            for word in target_words:
                if not word or word in own or word in bucket:
                    continue
                bucket.append(word)
        bucket_map = {}
        if antonyms:
            bucket_map["antonyms"] = antonyms[:8]
        if derivatives:
            bucket_map["derivatives"] = derivatives[:8]
        if bucket_map:
            result[sense_id] = bucket_map
    return result
