import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from .models import StateRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    job_id TEXT NOT NULL,
    record_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL CHECK (attempt_count >= 0),
    last_error TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (job_id, record_id)
)
"""


class Storage:
    def __init__(self, path: Path):
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(SCHEMA)

    def write(self, *records: StateRecord) -> None:
        with self.transaction() as connection:
            self.write_records(connection, records)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    @staticmethod
    def write_records(connection, records) -> None:
        connection.executemany(
            """
                INSERT INTO records VALUES (
                    :job_id, :record_id, :input_hash, :pipeline_version, :status,
                    :attempt_count, :last_error, :updated_at
                )
                ON CONFLICT(job_id, record_id) DO UPDATE SET
                    input_hash = excluded.input_hash,
                    pipeline_version = excluded.pipeline_version,
                    status = excluded.status,
                    attempt_count = excluded.attempt_count,
                    last_error = excluded.last_error,
                    updated_at = excluded.updated_at
                """,
            [record.model_dump(mode="json") for record in records],
        )

    def read(self, job_id: str, record_id: str) -> StateRecord | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM records WHERE job_id = ? AND record_id = ?",
                (job_id, record_id),
            ).fetchone()
        return StateRecord.model_validate(dict(row)) if row is not None else None
