import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from hashlib import sha256
from threading import Lock

from .ai_pipeline import settings_prices
from .ai_provider import ChatProvider, ProviderError
from .p1 import serialize
from .storage import Storage

SYSTEM = (
    "Select senses of an English word for a beginner learner's dictionary. "
    "Choose 1 or 2 everyday senses as primary and at most 3 additional useful senses. "
    "Avoid rare technical meanings and redundant near-duplicates. Historical tag counts are "
    "weak evidence. Preserve distinct parts of speech when useful. Prefer exact matches. "
    "Return JSON only with keys primary and more, both arrays of the provided sense IDs. "
    "Order each array by learner usefulness. Do not generate definitions or examples."
)


def ranking_input(word: dict) -> list[dict]:
    candidates = [
        sense for sense in word["candidates"] if sense["selection_status"] != "excluded"
    ]
    selected = [
        sense for sense in candidates if sense["selection_status"] == "selected"
    ]
    return [
        {
            "id": sense["sense_id"],
            "pos": sense["pos"],
            "definition": sense["source_definition"],
            "tags": sense.get("tag_count"),
            "match": sense.get("match_method"),
        }
        for sense in selected or candidates
    ]


def ranking_hash(word: dict) -> str:
    return sha256(serialize(ranking_input(word)).encode()).hexdigest()


def validate_ranking(text: str, allowed: set[str]) -> dict:
    ranking = json.loads(text)
    if not isinstance(ranking, dict) or set(ranking) != {"primary", "more"}:
        raise ValueError("Invalid ranking fields")
    primary, more = ranking["primary"], ranking["more"]
    if not (
        isinstance(primary, list)
        and isinstance(more, list)
        and 1 <= len(primary) <= 2
        and len(more) <= 3
    ):
        raise ValueError("Invalid ranking sizes")
    ids = primary + more
    if any(not isinstance(value, str) or value not in allowed for value in ids):
        raise ValueError("Invalid sense ID")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate sense ID")
    return ranking


def rank_words(db, settings, source_registry, registry_path, *, limit, execute, budget):
    source = source_registry.wordnet
    if source.source_version != "3.0" or not source.allows_use(registry_path):
        raise ValueError("Allowed WordNet 3.0 source required")
    allowed_books = {
        book
        for book, entry in source_registry.wordlists.items()
        if entry.allows_use(registry_path)
    }
    input_price, output_price = settings_prices(settings)
    with closing(
        sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        previous = {}
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learner_rankings'"
        ).fetchone():
            previous = dict(
                connection.execute("SELECT word_id, fingerprint FROM learner_rankings")
            )
        jobs = []
        charges = 0.0
        for identifier, payload in connection.execute(
            "SELECT word_id,payload FROM p1_words ORDER BY word_id"
        ):
            word = json.loads(payload)
            if not any(link["book_id"] in allowed_books for link in word["links"]):
                continue
            if (word.get("wordnet") or {}).get("source") != source.model_dump(
                mode="json"
            ):
                continue
            candidates = ranking_input(word)
            fingerprint = ranking_hash(word)
            if len(candidates) < 2 or previous.get(identifier) == fingerprint:
                continue
            prompt = serialize({"word": word["lemma"], "senses": candidates})
            jobs.append(
                (identifier, fingerprint, prompt, {sense["id"] for sense in candidates})
            )
            charges += (
                (len(prompt.encode()) + len(SYSTEM.encode()) + 128) * input_price
                + settings.max_tokens * output_price
            ) / 1_000_000
            if limit is not None and len(jobs) >= limit:
                break
    summary = {
        "requests": len(jobs),
        "maximum_attempts": len(jobs) * (1 + settings.max_retries),
        "estimated_usd": round(charges, 8),
        "estimated_usd_with_retries": round(charges * (1 + settings.max_retries), 8),
        "model": settings.model,
    }
    print(json.dumps(summary), flush=True)
    if not execute or not jobs:
        return summary
    if charges * (1 + settings.max_retries) > budget:
        raise ValueError("Estimate with retries exceeds the confirmed batch budget")
    if not settings.api_key or not settings.base_url:
        raise ValueError("Configure LLM_API_KEY and LLM_BASE_URL")
    from urllib.parse import urlsplit

    endpoint = urlsplit(settings.base_url)
    if (
        endpoint.scheme != "https"
        or not endpoint.hostname
        or endpoint.username
        or endpoint.query
    ):
        raise ValueError(
            "Ranking requires an HTTPS API endpoint without embedded credentials"
        )

    storage = Storage(db)
    with storage.transaction() as connection:
        connection.execute("""
          CREATE TABLE IF NOT EXISTS learner_rankings (
              word_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, result TEXT NOT NULL
          )
        """)
    pacing = Lock()
    next_request = 0.0

    def rank(job):
        nonlocal next_request
        identifier, fingerprint, prompt, ids = job
        attempts = tokens_in = tokens_out = 0
        for attempt in range(settings.max_retries + 1):
            with pacing:
                delay = max(0.0, next_request - time.monotonic())
                next_request = (
                    time.monotonic() + delay + 60 / settings.requests_per_minute
                )
            time.sleep(delay)
            attempts += 1
            try:
                response = provider.complete(
                    [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": prompt},
                    ]
                )
                tokens_in += response.input_tokens or 0
                tokens_out += response.output_tokens or 0
                result = validate_ranking(response.text, ids)
            except (ProviderError, ValueError) as error:
                if isinstance(error, ProviderError) and not error.retryable:
                    return False, attempts, tokens_in, tokens_out
                if attempt < settings.max_retries:
                    time.sleep(max(getattr(error, "retry_after", 0), 2**attempt))
                continue
            result["model"] = settings.model
            result["provider"] = settings.provider
            result["ranking_version"] = "v1"
            with storage.transaction() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO learner_rankings VALUES (?,?,?)",
                    (identifier, fingerprint, serialize(result)),
                )
            return True, attempts, tokens_in, tokens_out
        return False, attempts, tokens_in, tokens_out

    with (
        ChatProvider(settings) as provider,
        ThreadPoolExecutor(settings.concurrency) as executor,
    ):
        results = list(executor.map(rank, jobs))
    success = sum(row[0] for row in results)
    return summary | {
        "succeeded": success,
        "failed": len(jobs) - success,
        "actual_requests": sum(row[1] for row in results),
        "input_tokens": sum(row[2] for row in results),
        "output_tokens": sum(row[3] for row in results),
    }
