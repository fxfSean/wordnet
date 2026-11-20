"""Build downloadable full-book packages for the exam wordbooks.

Each package contains:
- full book metadata and unit count
- ``memberships`` for every usable word (book rank/unit)
- full WordNet senses only for words that are not already in the core catalog

This keeps packages small while letting the client merge them into the bundled
catalog at runtime.  Upload the generated files to cloud storage or an HTTPS
CDN, then configure ``bookPackageFileIds`` or ``bookPackageBaseUrl`` in
``src/cloud-config.ts``.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import exam_books
from wordnet_lookup import WordNet

CATALOG = ROOT / "miniprogram/data/catalog.gz.js"
OUT = ROOT / "data/packages"
PIPELINE = ROOT.parent / "vocab-pipeline"
UNIT_SIZE = 50
MAX_SENSES = 2


def core_catalog() -> dict[str, list[dict]]:
    payload = json.loads(gzip.decompress(base64.b64decode(CATALOG.read_text().split('"')[1])))
    return {word["word"]: word["senses"] for word in payload["words"]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    wordnet = WordNet(PIPELINE / "data/raw/wordnet30")
    core = core_catalog()
    manifest = []
    for meta in exam_books.BOOKS:
        rows = exam_books.read_rows(meta)
        rows.sort(key=lambda item: (-wordnet.score(item[0]), item[1]))
        memberships = []
        entries = []
        matched = 0
        for word, _source_rank in rows:
            senses = core.get(word)
            if senses is not None and not senses:
                continue
            if senses is None:
                senses = wordnet.lookup(word)[:MAX_SENSES]
                if not senses:
                    continue
            matched += 1
            rank = matched
            unit = (rank - 1) // UNIT_SIZE + 1
            memberships.append({"word": word, "rank": rank, "unit": unit})
            if word not in core:
                entries.append({"word": word, "rank": rank, "unit": unit, "senses": senses})
        book = {
            "id": meta["id"],
            "title": meta["title"],
            "subtitle": meta["subtitle"].replace(" · Core", ""),
            "description": meta["description"],
            "wordCount": matched,
            "unitSize": UNIT_SIZE,
            "unitCount": (matched + UNIT_SIZE - 1) // UNIT_SIZE,
            "source": meta["source"],
        }
        payload = {"version": 1, "book": book, "memberships": memberships, "entries": entries}
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        compressed = gzip.compress(raw, 9, mtime=0)
        target = OUT / (meta["id"] + ".json.gz")
        target.write_bytes(compressed)
        manifest.append({
            "id": meta["id"],
            "title": meta["title"],
            "file": target.name,
            "bytes": len(compressed),
            "sha256": hashlib.sha256(compressed).hexdigest(),
            "words": matched,
            "newWords": len(entries),
            "units": book["unitCount"],
        })
        print(f"{meta['id']}: {matched} words, {len(entries)} new entries, {len(compressed)} bytes")
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("manifest:", OUT / "manifest.json")


if __name__ == "__main__":
    main()
