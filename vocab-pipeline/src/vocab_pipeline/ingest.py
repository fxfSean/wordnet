import csv
from contextlib import contextmanager
from pathlib import Path

from .normalize import normalize_lemma


@contextmanager
def csv_rows(path: Path, headers: tuple[str, ...]):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        if reader.fieldnames != list(headers):
            raise ValueError(f"{path}: expected CSV header {','.join(headers)}")
        yield reader


def parse_wordlist(
    path: Path,
) -> tuple[list[tuple[str, str, int | None]], dict[str, int]]:
    stats = {"total": 0, "duplicates": 0, "invalid": 0}
    rows = []
    seen = set()
    stored = set()
    with csv_rows(path, ("lemma", "source_ref", "rank")) as reader:
        for row in reader:
            stats["total"] += 1
            if None in row or None in row.values():
                stats["invalid"] += 1
                continue
            lemma, ref, rank = (row[key].strip() for key in reader.fieldnames)
            normalized = normalize_lemma(lemma)
            if (
                not normalized
                or not ref
                or not any(char.isalpha() for char in normalized)
                or not lemma.isprintable()
                or not ref.isprintable()
                or (
                    rank
                    and (not rank.isascii() or not rank.isdecimal() or len(rank) > 18)
                )
            ):
                stats["invalid"] += 1
                continue
            if normalized in seen:
                stats["duplicates"] += 1
            seen.add(normalized)
            item = lemma, ref, int(rank) if rank else None
            if item not in stored:
                stored.add(item)
                rows.append(item)
    return rows, stats
