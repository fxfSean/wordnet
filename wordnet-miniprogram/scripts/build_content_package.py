"""Build the shared collocation + word-root content package.

The main mini-program package stays below the 2 MB limit, so phrases and roots
are downloaded on demand after the first launch.  The package is keyed by word:

    {"version": 1, "words": {"abandon": {"phrases": [...], "roots": [...]}}}

Sources
-------
* ``data/wordlists/phrases.json`` - collocations extracted from
  KyleBing/english-vocabulary (BSD-3-Clause), which itself derives from the
  exam word lists.  Up to six collocations per word are kept.
* ``scripts/roots_data.py`` - Greek/Latin roots adapted from
  jupsh/anki-word-roots (CC BY-SA 4.0).

Run ``python scripts/build_content_package.py`` then upload the generated
``data/packages/content.json.gz`` to cloud storage / an HTTPS CDN and set
``contentPackageFileId`` or ``contentPackageBaseUrl`` in ``src/cloud-config.ts``.
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

from roots_data import Roots

CATALOG = ROOT / "miniprogram/data/catalog.gz.js"
PHRASES = ROOT / "data/wordlists/phrases.json"
OUT = ROOT / "data/packages"
MAX_PHRASES = 6
VERSION = 1


def catalog_words() -> list[str]:
    payload = json.loads(gzip.decompress(base64.b64decode(CATALOG.read_text().split('"')[1])))
    return [word["word"] for word in payload["words"]]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    phrases: dict[str, list[dict]] = json.loads(PHRASES.read_text(encoding="utf-8"))
    roots = Roots()

    candidates = list(dict.fromkeys(catalog_words() + list(phrases)))
    words: dict[str, dict] = {}
    phrase_words = 0
    root_words = 0
    for word in candidates:
        content: dict = {}
        items = phrases.get(word)
        if items:
            trimmed = []
            for item in items[:MAX_PHRASES]:
                en = str(item.get("en") or "").strip()
                if not en:
                    continue
                row = {"en": en}
                zh = str(item.get("zh") or "").strip()
                if zh:
                    row["zh"] = zh
                trimmed.append(row)
            if trimmed:
                content["phrases"] = trimmed
                phrase_words += 1
        matches = roots.lookup(word)
        if matches:
            content["roots"] = matches
            root_words += 1
        if content:
            words[word] = content

    payload = {"version": VERSION, "words": words}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(raw, 9, mtime=0)
    target = OUT / "content.json.gz"
    target.write_bytes(compressed)
    manifest = {
        "version": VERSION,
        "file": target.name,
        "bytes": len(compressed),
        "sha256": hashlib.sha256(compressed).hexdigest(),
        "words": len(words),
        "phraseWords": phrase_words,
        "rootWords": root_words,
        "maxPhrases": MAX_PHRASES,
    }
    (OUT / "content-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"content package: {len(words)} words ({phrase_words} with phrases, "
        f"{root_words} with roots), {len(raw)} bytes raw, {len(compressed)} bytes gzip"
    )
    print("manifest:", OUT / "content-manifest.json")


if __name__ == "__main__":
    main()
