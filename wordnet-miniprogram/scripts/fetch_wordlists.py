"""Download the open word list snapshots used by ``extra_books.py``.

The lists are published by the New General Service List Project under
CC BY-SA 4.0.  Run this only when you intentionally want to refresh the
snapshots; the CSV files are committed for reproducible builds.
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/wordlists"
BASE = "https://www.newgeneralservicelist.com"

FILES = {
    "nawl.csv": "/s/NAWL_12_stats.csv",
    "tsl.csv": "/s/TSL_12_stats.csv",
    "bsl.csv": "/s/BSL_120_stats.csv",
    "spoken.csv": "/s/NGSL-Spoken_12_stats.csv",
    "dolch.csv": "/s/NDL_11_stats.csv",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, path in FILES.items():
        data = urllib.request.urlopen(BASE + path, timeout=60).read()
        target = OUT / name
        target.write_bytes(data)
        print(f"{name}: {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
