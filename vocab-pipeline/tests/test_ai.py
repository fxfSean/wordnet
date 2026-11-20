import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
import yaml

from vocab_pipeline.ai_pipeline import GenerationPipeline
from vocab_pipeline.ai_provider import ChatProvider, ProviderError
from vocab_pipeline.ai_quality import (
    LearnerOutput,
    inspect_output,
    load_inflections,
    overlap,
)
from vocab_pipeline.config import LLMSettings, load_pipeline_config

ROOT = Path(__file__).resolve().parents[1]


def response_for(source, **overrides):
    return {
        "word": source["word"],
        "pos": source["pos"],
        "sense_id": source["sense_id"],
        "simple_definition": "An organization that keeps money safe for people",
        "example": "She put her savings in the bank.",
        "difficulty": "A2",
        "generation_status": "generated",
        "semantic_check": "supported",
        "reason": "",
    } | overrides


def completion(text, request):
    return httpx.Response(
        200,
        json={
            "model": json.loads(request.content)["model"],
            "choices": [{"message": {"content": text}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 80},
        },
    )


@pytest.fixture
def batch(tmp_path):
    (tmp_path / "license.txt").write_text("Test fixture terms", encoding="utf-8")
    license = {
        "status": "allowed",
        "source_name": "Test data",
        "source_version": "3.0",
        "url": "https://example.invalid",
        "acquired_at": "2026-11-16",
        "license_id": "test",
        "license_name": "Test terms",
        "license_text": "license.txt",
        "commercial_use": True,
        "modification": True,
        "redistribution": True,
        "cloud_storage": True,
        "attribution_required": True,
        "reviewer": "fixture",
        "reviewed_at": "2026-11-16",
    }
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        yaml.safe_dump(
            {
                "wordnet": license,
                "wordlists": {"basic_ngsl_1_2": license},
            }
        ),
        encoding="utf-8",
    )
    config = load_pipeline_config(ROOT / "config" / "pipeline.yaml")
    settings = LLMSettings(
        base_url="https://api.deepseek.com",
        api_key="fixture-key",
        model="deepseek-flash",
        concurrency=1,
        requests_per_minute=10000,
        max_retries=1,
    )
    db = tmp_path / "test.sqlite3"
    runner = GenerationPipeline(
        db, registry, config, settings, ROOT / "config/prompts/v1"
    )
    candidates = [
        {
            "sense_id": f"wn30:noun:{index:08d}",
            "pos": "noun",
            "source": {"source_id": f"noun:{index:08d}"},
            "source_definition": definition,
            "source_examples": [],
            "selection_status": "needs_review",
            "ranking_score": 10 - index,
            "is_recommended": True,
        }
        for index, definition in enumerate(
            ("A financial institution", "Sloping land by a river")
        )
    ]
    word = {
        "lemma": "bank",
        "links": [{"book_id": "basic_ngsl_1_2"}],
        "wordnet": {"source": license, "sha256": {}},
        "candidates": candidates,
    }
    with closing(sqlite3.connect(db)) as connection, connection:
        connection.execute(
            "CREATE TABLE p1_words(word_id TEXT PRIMARY KEY, payload TEXT)"
        )
        connection.execute(
            "INSERT INTO p1_words VALUES (?,?)", ("w_bank", json.dumps(word))
        )
    return runner


def factory(handler):
    return lambda settings: ChatProvider(
        settings, transport=httpx.MockTransport(handler)
    )


def test_retries_and_multisense_generation(batch, monkeypatch):
    monkeypatch.setattr(
        "vocab_pipeline.ai_pipeline.wait_exponential", lambda **_: lambda _: 0
    )
    jobs, vocabulary = batch.plan(words=["bank"])
    vocabulary = set()
    assert len(jobs) == 2 and jobs[0].task_id != jobs[1].task_id
    seen = []

    def answer(request):
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        assert body["thinking"] == {"type": "disabled"}
        source = json.loads(body["messages"][1]["content"].splitlines()[1])
        seen.append(source["sense_id"])
        if len(seen) == 1:
            return httpx.Response(429)
        fields = (
            {}
            if source["sense_id"] == jobs[0].source["sense_id"]
            else {
                "simple_definition": "Sloping ground next to a river or stream",
                "example": "We sat on the bank after lunch.",
            }
        )
        return completion(json.dumps(response_for(source, **fields)), request)

    assert batch.run(jobs, vocabulary, factory(answer)) == {"generated": 2}
    report = batch.report()
    assert report["requests_started"] == 3
    assert report["completed"] == 2
    assert not batch.plan(words=["bank"])[0]
    assert len(batch.plan(words=["bank"], force=True)[0]) == 2
    batch.settings.model = "deepseek-v4-pro"
    assert {job.task_id for job in batch.plan()[0]}.isdisjoint(
        job.task_id for job in jobs
    )


@pytest.mark.parametrize("failure", ["timeout", 500, "invalid_json", "missing_fields"])
def test_failures_are_retried_then_persisted(batch, monkeypatch, failure):
    monkeypatch.setattr(
        "vocab_pipeline.ai_pipeline.wait_exponential", lambda **_: lambda _: 0
    )
    jobs, vocabulary = batch.plan(limit=1)

    def answer(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("fixture")
        if failure == 500:
            return httpx.Response(500)
        return completion("invalid" if failure == "invalid_json" else "{}", request)

    assert batch.run(jobs, vocabulary, factory(answer)) == {"failed": 1}
    assert batch.report()["requests_started"] == 2
    assert batch.plan(failed=True)[0][0].task_id == jobs[0].task_id


def test_auth_is_not_retried(batch):
    jobs, vocabulary = batch.plan()
    result = batch.run(
        jobs, vocabulary, factory(lambda _: httpx.Response(401, text="fixture-key"))
    )
    assert result == {"failed": 1, "stopped": 1}
    report = batch.report()
    assert report["requests_started"] == 1
    assert report["results"][0]["validation_errors"] == ["http_401"]
    assert "fixture-key" not in json.dumps(report)


def test_budget_and_interrupt_resume(batch):
    jobs, vocabulary = batch.plan()
    batch.settings.daily_budget_usd = 0

    def answer(request):
        source = json.loads(
            json.loads(request.content)["messages"][1]["content"].splitlines()[1]
        )
        return completion(json.dumps(response_for(source)), request)

    assert "budget_limit" in batch.run(jobs, vocabulary, factory(answer))
    assert batch.report()["requests_started"] == 0
    batch.settings.daily_budget_usd = 1
    seen = 0

    def interrupt_second(request):
        nonlocal seen
        seen += 1
        if seen == 2:
            raise KeyboardInterrupt
        return answer(request)

    with pytest.raises(KeyboardInterrupt):
        batch.run(jobs, vocabulary, factory(interrupt_second))
    assert batch.report()["completed"] == 1
    remaining, _ = batch.plan()
    assert [job.task_id for job in remaining] == [jobs[1].task_id]
    batch.run(remaining, vocabulary, factory(answer))
    assert batch.report()["completed"] == 2
    assert batch.report()["requests_without_cost"] == 1
    assert "DUPLICATE_DEFINITION" in batch.report()["results"][1]["validation_errors"]


def test_quality_flags_lemma_and_wrong_sense(batch):
    job = batch.plan(limit=1)[0][0]
    text = LearnerOutput.model_validate(
        response_for(
            job.source,
            simple_definition="A bank that keeps money safe",
            example="We sat on the bank after lunch.",
            semantic_check="mismatch",
            reason="This use refers to a riverbank.",
        )
    )
    errors, _ = inspect_output(text, job.source, set(), set(), 30, 25)
    assert {"LEMMA_LEAK", "SENSE_DRIFT_SUSPECTED"} <= set(errors)


def test_verified_irregular_example_forms(tmp_path):
    content = b"meant mean\nran run\ntook take\n"
    (tmp_path / "verb.exc").write_bytes(content)
    forms = load_inflections(tmp_path, {"verb.exc": sha256(content).hexdigest()})
    for base, example in (
        ("mean", "She meant after lunch."),
        ("run", "She ran to catch the bus."),
        ("take", "She took steps to fix it."),
    ):
        assert overlap(example, base, forms["verb", base])
        assert not overlap(example, base, set())


def test_compatible_endpoint_uses_plain_text_by_default(batch):
    batch.settings.provider = "openai_compatible"

    def answer(request):
        payload = json.loads(request.content)
        assert "response_format" not in payload and "thinking" not in payload
        return httpx.Response(403)

    with (
        factory(answer)(batch.settings) as provider,
        pytest.raises(ProviderError, match="http_403"),
    ):
        provider.complete([])
