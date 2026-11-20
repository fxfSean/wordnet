import csv
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from vocab_pipeline.cli import app
from vocab_pipeline.config import load_llm_settings, load_pipeline_config
from vocab_pipeline.models import (
    CandidateSense,
    GeneratedSense,
    SourceRef,
    StateRecord,
    Status,
)
from vocab_pipeline.storage import Storage

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "pipeline.yaml"


def test_cli_initializes_database(tmp_path):
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    database = tmp_path / "state" / "test.sqlite3"
    for _ in range(2):
        result = runner.invoke(app, ["init-state", "--db", str(database)])
        assert result.exit_code == 0, result.output
    assert Storage(database).read("job", "missing") is None


def test_state_round_trip_and_upsert(tmp_path):
    database = tmp_path / "test.sqlite3"
    storage = Storage(database)
    storage.initialize()
    record = StateRecord(
        job_id="job",
        record_id="one",
        input_hash="test-hash",
        pipeline_version="0.1.0",
        status=Status.INGESTED,
        updated_at="2026-11-13T00:00:00Z",
    )
    other_job = record.model_copy(update={"job_id": "other"})
    storage.write(record, other_job)
    assert Storage(database).read("job", "one") == record
    updated = record.model_copy(update={"status": Status.NORMALIZED, "attempt_count": 1})
    storage.write(updated)
    assert Storage(database).read("job", "one") == updated
    assert Storage(database).read("other", "one") == other_job
    bad = record.model_copy(update={"attempt_count": -1})
    with pytest.raises(sqlite3.IntegrityError):
        storage.write(record, bad)
    assert Storage(database).read("job", "one") == updated


def test_pipeline_configuration(tmp_path):
    settings = load_pipeline_config(CONFIG)
    assert settings.wordnet_version == "3.0"
    assert settings.model_dump() == {
        "wordnet_version": "3.0",
        "batch_size": 50,
        "concurrency": 3,
        "max_retries": 3,
        "prompt_version": "v1",
        "definition_max_words": 30,
        "example_max_words": 25,
        "generation_budget_usd": 5,
        "temperature": 0,
        "books": ["basic_ngsl_1_2"],
        "wordnet_recommendation_limit": 3,
        "wordnet_min_tag_count": 1,
    }
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(settings.model_dump_json().replace('"3.0"', '"3.1"'), encoding="utf-8")
    with pytest.raises(ValidationError, match="wordnet_version"):
        load_pipeline_config(invalid)


def test_dotenv_precedence_and_secret(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("LLM_MODEL=file-model\nLLM_API_KEY=test-secret\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "process-model")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT", raising=False)
    settings = load_llm_settings(path)
    assert settings.model == "process-model"
    assert settings.request_timeout == 45
    assert settings.api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)


def test_all_fixture_rows_through_offline_mock(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with (ROOT / "tests" / "fixtures" / "dev20.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        assert reader.fieldnames == ["lemma", "source_ref", "rank"]
        rows = list(reader)
    assert len(rows) == len({row["lemma"] for row in rows}) == 20
    assert len({row["source_ref"] for row in rows}) == 20

    runner = CliRunner()
    path = tmp_path / "candidate.json"
    hashes = set()
    for row in rows:
        candidate = CandidateSense(
            sense_id=row["source_ref"],
            lemma=row["lemma"],
            pos="noun",
            source_definition="Synthetic fixture",
            source=SourceRef(
                source_name="dev20",
                source_version="1",
                source_id=row["source_ref"],
                license_id="local-dev",
            ),
            selection_status="selected",
        )
        path.write_text(candidate.model_dump_json(), encoding="utf-8")
        args = ["mock-response", str(path), "--config", str(CONFIG)]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert runner.invoke(app, args).output == result.output
        response = GeneratedSense.model_validate_json(result.output)
        assert response.sense_id == candidate.sense_id
        assert candidate.lemma in response.example_en
        assert response.model_id == "mock"
        assert response.review_status == "pending"
        hashes.add(response.generation_hash)
    assert len(hashes) == 20
