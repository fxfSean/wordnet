import json
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from .ingest import csv_rows, parse_wordlist
from .models import CandidateSense, StateRecord, Status
from .normalize import normalize_lemma, word_id
from .provenance import ingest_status, load_registry
from .sense_selection import recommend_senses
from .storage import Storage
from .wordnet_adapter import VERSION, WordNet

JOB = "p1"


def serialize(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class SourcesPipeline:
    def __init__(self, db: Path, registry: Path):
        self.storage = Storage(db)
        self.storage.initialize()
        self.registry_path = registry
        self.registry = load_registry(registry)

    @staticmethod
    def _initialize(connection):
        connection.execute("""
            CREATE TABLE IF NOT EXISTS p1_books (
                book_id TEXT PRIMARY KEY, payload TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS p1_words (
                word_id TEXT PRIMARY KEY, payload TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS p1_wordnet (
                id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL
            )
        """)

    @staticmethod
    def _state(connection, record_id: str, status: Status, payload: str):
        digest = sha256(payload.encode("utf-8")).hexdigest()
        previous = connection.execute(
            "SELECT input_hash, status FROM records WHERE job_id = ? AND record_id = ?",
            (JOB, record_id),
        ).fetchone()
        if previous is not None and tuple(previous) == (digest, status):
            return
        Storage.write_records(
            connection,
            [
                StateRecord(
                    job_id=JOB,
                    record_id=record_id,
                    input_hash=digest,
                    pipeline_version="0.1.0",
                    status=status,
                    updated_at=datetime.now(UTC).isoformat(),
                )
            ],
        )

    def ingest(self, book: str, path: Path, *, formal: bool = False) -> dict:
        rows, stats = parse_wordlist(path)
        source = self.registry.wordlists.get(book)
        status = ingest_status(source, self.registry_path)
        if formal and status != Status.INGESTED:
            raise ValueError(f"Formal import blocked by source license: {book}")
        payload = serialize(rows)
        with self.storage.transaction() as connection:
            self._initialize(connection)
            previous = connection.execute(
                "SELECT payload FROM p1_books WHERE book_id = ?",
                (book,),
            ).fetchone()
            if formal:
                old = (
                    {tuple(row) for row in json.loads(previous[0])}
                    if previous
                    else set()
                )
                prior = {normalize_lemma(row[0]): row for row in old}
                current = {normalize_lemma(row[0]): row for row in rows}
                common = current.keys() & prior.keys()
                added = len(current.keys() - prior.keys())
                updated = sum(current[key] != prior[key] for key in common)
                stats.update(
                    imported=added + updated,
                    added=added,
                    updated=updated,
                    removed=len(prior.keys() - current.keys()),
                    unchanged=len(common) - updated,
                )
            if previous is None or previous[0] != payload:
                connection.execute(
                    "INSERT OR REPLACE INTO p1_books VALUES (?, ?)",
                    (book, payload),
                )
            self._state(connection, f"book:{book}", status, payload)
            self._normalize(connection, refresh_only=not formal)
        return stats | {
            "stored_rows": len(rows),
            "license_blocked": len(rows) if status == Status.BLOCKED_LICENSE else 0,
        }

    def _normalize(self, connection, *, refresh_only=False):
        grouped = defaultdict(list)
        for book, payload in connection.execute(
            "SELECT book_id, payload FROM p1_books ORDER BY book_id"
        ):
            source = self.registry.wordlists.get(book)
            status = ingest_status(source, self.registry_path)
            self._state(connection, f"book:{book}", status, payload)
            for lemma, ref, rank in json.loads(payload):
                grouped[normalize_lemma(lemma)].append(
                    {
                        "book_id": book,
                        "display_lemma": lemma,
                        "source_ref": ref,
                        "rank": rank,
                        "license_status": "allowed"
                        if status == Status.INGESTED
                        else "blocked",
                        "source": source.model_dump(mode="json") if source else None,
                    }
                )
        existing = {
            identifier: json.loads(payload)
            for identifier, payload in connection.execute(
                "SELECT word_id, payload FROM p1_words"
            )
        }
        wordnet_source = self.registry.wordnet
        current_wordnet = (
            wordnet_source.model_dump(mode="json")
            if wordnet_source.source_version == VERSION
            and wordnet_source.allows_use(self.registry_path)
            else None
        )
        for lemma, links in grouped.items():
            identifier = word_id(lemma)
            old = existing.pop(identifier, None)
            if old is None and refresh_only:
                continue
            if (
                old
                and old["links"] == links
                and (
                    old["wordnet"] is None
                    or old["wordnet"]["source"] == current_wordnet
                )
            ):
                continue
            word = {"lemma": lemma, "links": links, "candidates": [], "wordnet": None}
            blocked = all(link["license_status"] == "blocked" for link in links)
            self._save_word(
                connection,
                identifier,
                word,
                Status.BLOCKED_LICENSE if blocked else Status.NORMALIZED,
            )
        for identifier in existing:
            connection.execute("DELETE FROM p1_words WHERE word_id = ?", (identifier,))
            connection.execute(
                "DELETE FROM records WHERE job_id = ? AND record_id = ?",
                (JOB, identifier),
            )

    def normalize(self) -> dict:
        with self.storage.transaction() as connection:
            self._initialize(connection)
            self._normalize(connection)
            return self._counts(connection)

    def match(
        self,
        directory: Path,
        checksums: dict[str, str],
        *,
        book: str | None = None,
        limit: int | None = None,
        retry_failed: bool = False,
        recommendation_limit: int = 3,
        min_tags: int = 1,
    ) -> dict:
        source = self.registry.wordnet
        if (
            not source.allows_use(self.registry_path)
            or source.source_version != VERSION
        ):
            raise ValueError(
                "WordNet requires a complete allowed source record for version 3.0"
            )
        metadata = {
            "source": source.model_dump(mode="json"),
            "sha256": checksums,
            "ranking": {
                "rule": "wordnet-tag-count-v1",
                "limit": recommendation_limit,
                "min_tag_count": min_tags,
            },
        }
        net = WordNet(directory, checksums, source.license_id)
        with self.storage.transaction() as connection:
            self._initialize(connection)
            self._normalize(connection, refresh_only=True)
            if (
                book is not None
                and not connection.execute(
                    "SELECT 1 FROM p1_books WHERE book_id = ?",
                    (book,),
                ).fetchone()
            ):
                raise ValueError(f"Book has not been imported: {book}")
            processed = 0
            for identifier, word in self._words(connection).items():
                if not any(
                    link["license_status"] == "allowed"
                    and (book is None or link["book_id"] == book)
                    for link in word["links"]
                ):
                    continue
                if retry_failed and (word["wordnet"] is None or word["candidates"]):
                    continue
                if not retry_failed and word["wordnet"] == metadata:
                    continue
                if limit is not None and processed >= limit:
                    break
                candidates = net.match(word["lemma"])
                processed += 1
                word["needs_review"] = recommend_senses(
                    candidates, recommendation_limit, min_tags
                )
                word["match_status"] = (
                    "exact"
                    if any(sense.match_method == "exact" for sense in candidates)
                    else ("morphology" if candidates else "unmatched")
                )
                if len(candidates) > 1:
                    for candidate in candidates:
                        candidate.selection_status = "needs_review"
                word["wordnet"] = metadata
                word["candidates"] = [
                    candidate.model_dump(mode="json") for candidate in candidates
                ]
                status = {0: Status.UNMATCHED, 1: Status.MATCHED}.get(
                    len(candidates),
                    Status.AMBIGUOUS,
                )
                self._save_word(connection, identifier, word, status)
            connection.execute(
                """
                INSERT INTO p1_wordnet VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                WHERE p1_wordnet.payload <> excluded.payload
                """,
                (serialize(metadata),),
            )
            return self._counts(connection)

    def word(self, lemma: str) -> dict:
        with self.storage.transaction() as connection:
            self._initialize(connection)
            identifier = word_id(normalize_lemma(lemma))
            row = connection.execute(
                "SELECT payload FROM p1_words WHERE word_id = ?", (identifier,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Word has not been imported: {lemma}")
            return json.loads(row[0])

    def quality(self) -> dict:
        with self.storage.transaction() as connection:
            self._initialize(connection)
            words = list(self._words(connection).values())
            books = defaultdict(list)
            for word in words:
                for book in sorted({link["book_id"] for link in word["links"]}):
                    books[book].append(word)
            return summarize(words) | {
                "books": {
                    book: summarize(items, book=book)
                    for book, items in sorted(books.items())
                }
            }

    def select(self, path: Path) -> dict:
        selections = defaultdict(set)
        with csv_rows(path, ("lemma", "sense_id")) as reader:
            for line, row in enumerate(reader, start=2):
                if None in row or any(
                    not value or not value.strip() for value in row.values()
                ):
                    raise ValueError(f"Invalid sense selection at line {line}")
                selections[word_id(normalize_lemma(row["lemma"]))].add(
                    row["sense_id"].strip()
                )
        with self.storage.transaction() as connection:
            self._initialize(connection)
            self._normalize(connection, refresh_only=True)
            words = self._words(connection)
            source = self.registry.wordnet
            if (
                not source.allows_use(self.registry_path)
                or source.source_version != VERSION
            ):
                raise ValueError("WordNet source is blocked")
            for identifier, selected in selections.items():
                word = words.get(identifier)
                if not word or not word["wordnet"]:
                    raise ValueError(f"No matched candidates for {identifier}")
                if word["wordnet"]["source"] != source.model_dump(mode="json"):
                    raise ValueError(
                        f"Re-run match-wordnet for {identifier}: source changed"
                    )
                candidates = [
                    CandidateSense.model_validate(item) for item in word["candidates"]
                ]
                unknown = selected - {candidate.sense_id for candidate in candidates}
                if unknown:
                    raise ValueError(
                        f"Unknown candidate IDs for {identifier}: {sorted(unknown)}"
                    )
                for candidate in candidates:
                    candidate.selection_status = (
                        "selected" if candidate.sense_id in selected else "excluded"
                    )
                word["candidates"] = [
                    candidate.model_dump(mode="json") for candidate in candidates
                ]
                self._save_word(connection, identifier, word, Status.SELECTED)
            return self._counts(connection)

    @staticmethod
    def _words(connection) -> dict:
        return {
            identifier: json.loads(payload)
            for identifier, payload in connection.execute(
                "SELECT word_id, payload FROM p1_words ORDER BY word_id"
            )
        }

    def _save_word(self, connection, identifier: str, word: dict, status: Status):
        payload = serialize(word)
        connection.execute(
            """
            INSERT INTO p1_words VALUES (?, ?)
            ON CONFLICT(word_id) DO UPDATE SET payload = excluded.payload
            WHERE p1_words.payload <> excluded.payload
            """,
            (identifier, payload),
        )
        self._state(connection, identifier, status, payload)

    @staticmethod
    def _counts(connection) -> dict:
        return dict(
            connection.execute(
                """
            SELECT status, count(*) FROM records
            WHERE job_id = ? AND record_id IN (SELECT word_id FROM p1_words)
            GROUP BY status ORDER BY status
            """,
                (JOB,),
            )
        )


def summarize(words: list[dict], *, book: str | None = None) -> dict:
    methods = defaultdict(int)
    unmatched = []
    count_senses = polysemous = needs_review = recommended_words = 0
    for word in words:
        allowed = any(
            link["license_status"] == "allowed"
            and (book is None or link["book_id"] == book)
            for link in word["links"]
        )
        if not allowed:
            methods["blocked"] += 1
            continue
        candidates = word["candidates"]
        method = word.get("match_status")
        if method is None:
            method = (
                ("exact" if candidates else "unmatched")
                if word["wordnet"]
                else "pending"
            )
        methods[method] += 1
        if method == "unmatched":
            unmatched.append(word["lemma"])
        count_senses += len(candidates)
        polysemous += len(candidates) > 1
        needs_review += word.get("needs_review", len(candidates) > 1)
        recommended_words += any(
            sense.get("is_recommended", False) for sense in candidates
        )
    total = len(words)
    return {
        "total": total,
        "exact": methods["exact"],
        "exact_rate": methods["exact"] / total if total else 0.0,
        "morphology_only": methods["morphology"],
        "unmatched": methods["unmatched"],
        "unmatched_words": sorted(unmatched),
        "pending": methods["pending"],
        "blocked": methods["blocked"],
        "matched": methods["exact"] + methods["morphology"],
        "coverage": (methods["exact"] + methods["morphology"]) / total
        if total
        else 0.0,
        "polysemous": polysemous,
        "candidate_senses": count_senses,
        "average_senses_per_word": count_senses / total if total else 0.0,
        "needs_review": needs_review,
        "recommended_words": recommended_words,
    }
