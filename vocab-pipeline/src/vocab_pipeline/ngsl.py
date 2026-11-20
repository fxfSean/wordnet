import csv
import io
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from .normalize import normalize_lemma
from .p1 import SourcesPipeline

BOOK = "basic_ngsl_1_2"
URL = "https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv"
DIGEST = "2098bab8955a120a9766c6282a51d7d578c6cb0a7d946600d2ffb73ba25a0b44"
LICENSE_ID = "CC-BY-SA-4.0"
MAX_BYTES = 1024 * 1024


def convert_ngsl(content: bytes, output: Path) -> dict:
    stream = io.StringIO(content.decode("utf-8-sig"), newline="")
    reader = csv.DictReader(stream, strict=True)
    if reader.fieldnames != [
        "Lemma",
        "SFI Rank",
        "SFI",
        "Adjusted Frequency per Million (U)",
    ]:
        raise ValueError("Unexpected NGSL CSV header")
    failures = []
    rows = {}
    duplicates = 0
    total = 0
    for row in reader:
        total += 1
        lemma = (row.get("Lemma") or "").strip()
        rank = (row.get("SFI Rank") or "").strip()
        key = normalize_lemma(lemma)
        ref = f"ngsl:1.2:sfi:{rank}" if rank else f"ngsl:1.2:line:{reader.line_num}"
        if (
            None in row
            or None in row.values()
            or not lemma.isprintable()
            or not any(char.isalpha() for char in key)
            or not rank.isascii()
            or not rank.isdecimal()
            or not 0 < int(rank) <= MAX_BYTES
        ):
            failures.append(
                {"source_ref": ref, "line": reader.line_num, "reason": "invalid_row"}
            )
            continue
        if key in rows:
            duplicates += 1
            continue
        rows[key] = (lemma, ref, int(rank))
    if not rows:
        raise ValueError("NGSL CSV contains no valid rows")
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(("lemma", "source_ref", "rank"))
        writer.writerows(rows.values())
    return {
        "raw_rows": total,
        "duplicate_rows": duplicates,
        "invalid_rows": len(failures),
        "valid_unique_words": len(rows),
        "failures": failures,
    }


def import_ngsl(db: Path, registry: Path, raw_dir: Path) -> dict:
    pipeline = SourcesPipeline(db, registry)
    source = pipeline.registry.wordlists.get(BOOK)
    if (
        source is None
        or not source.allows_use(registry)
        or source.url != URL
        or source.source_version != "1.2"
        or source.license_id != LICENSE_ID
        or source.attribution_required is not True
    ):
        raise ValueError(
            f"NGSL 1.2 requires an approved {LICENSE_ID} registry entry for {BOOK}"
        )
    with urlopen(URL, timeout=30) as response:
        content = response.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES or sha256(content).hexdigest() != DIGEST:
        raise ValueError("NGSL download does not match the approved SHA256")
    raw_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=raw_dir) as temp:
        staging = Path(temp)
        converted = staging / "ngsl.csv"
        report = convert_ngsl(content, converted)
        snapshot = raw_dir / f"ngsl-1.2-{DIGEST}.csv"
        if not snapshot.exists():
            pending = staging / "raw.csv"
            pending.write_bytes(content)
            pending.replace(snapshot)
        elif sha256(snapshot.read_bytes()).hexdigest() != DIGEST:
            raise ValueError(f"Local snapshot has an incorrect SHA256: {snapshot}")
        counts = pipeline.ingest(BOOK, converted, formal=True)
    return (
        report
        | counts
        | {
            "book_id": BOOK,
            "source_url": URL,
            "source_version": "1.2",
            "license_id": LICENSE_ID,
            "sha256": DIGEST,
        }
    )
