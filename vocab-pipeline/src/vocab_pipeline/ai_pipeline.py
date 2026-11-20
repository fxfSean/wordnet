import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock
from urllib.parse import urlsplit

from pydantic import ValidationError
from tenacity import RetryCallState, wait_exponential

from .ai_provider import ChatProvider, ProviderError
from .ai_quality import LearnerOutput, inspect_output, language_words, load_inflections
from .config import LLMSettings, PipelineConfig
from .normalize import normalize_lemma
from .p1 import serialize
from .provenance import load_registry
from .storage import Storage

SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ai_generations (
        id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL,
        word TEXT NOT NULL, sense_id TEXT NOT NULL, payload TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS ai_generations_task ON ai_generations(task_id, id)""",
    """CREATE TABLE IF NOT EXISTS ai_requests (
        id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, started_at TEXT NOT NULL,
        reserved_usd REAL NOT NULL, cost_usd REAL, input_tokens INTEGER,
        output_tokens INTEGER, elapsed REAL, outcome TEXT
    )""",
)
TRIAL_WORDS = (
    "bank",
    "book",
    "light",
    "run",
    "water",
    "justice",
    "freedom",
    "change",
    "take",
    "play",
    "clear",
    "strong",
    "set",
    "school",
    "family",
    "move",
    "care",
    "mean",
    "power",
    "support",
)


@dataclass(frozen=True)
class Job:
    task_id: str
    source: dict
    messages: list[dict]
    forms: set[str]
    input_bound: int
    reserved_usd: float


def now() -> str:
    return datetime.now(UTC).isoformat()


def settings_prices(settings: LLMSettings) -> tuple[float, float]:
    prices = (settings.input_usd_per_million, settings.output_usd_per_million)
    if all(price is not None for price in prices):
        return prices
    host = urlsplit(settings.base_url or "").hostname
    if host == "api.deepseek.com" and settings.model == "deepseek-flash":
        return (0.30, 1.20)
    if host == "api.deepseek.com" and settings.model == "deepseek-v4-pro":
        return (1.32, 3.96)
    raise ValueError(
        "Configure both LLM input and output prices for the selected model"
    )


class GenerationPipeline:
    def __init__(
        self,
        db: Path,
        registry: Path,
        config: PipelineConfig,
        settings: LLMSettings,
        prompt_dir: Path,
    ):
        self.storage = Storage(db)
        self.registry_path = registry
        self.config = config
        self.settings = settings
        self.prompt_dir = prompt_dir
        self.stop = Event()
        self.rate_lock = Lock()
        self.next_request = 0.0
        self.storage.initialize()
        with self.storage.transaction() as connection:
            for statement in SCHEMA:
                connection.execute(statement)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        input_price, output_price = settings_prices(self.settings)
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    @property
    def daily_budget(self) -> float:
        override = self.settings.daily_budget_usd
        return self.config.generation_budget_usd if override is None else override

    @contextmanager
    def exclusive_generation(self):
        lock_path = self.storage.path.with_name(
            self.storage.path.name + ".ai-lock.sqlite3"
        )
        with closing(sqlite3.connect(lock_path, timeout=0)) as lock:
            try:
                lock.execute("BEGIN EXCLUSIVE")
            except sqlite3.OperationalError as error:
                raise ValueError("Another AI batch is using this database") from error
            yield

    def plan(
        self,
        *,
        book=None,
        words=(),
        word_limit=None,
        limit=None,
        sense_id=None,
        senses_per_word=None,
        failed=False,
        force=False,
    ) -> tuple[list[Job], set[str]]:
        system = (
            (self.prompt_dir / "definition_system.txt")
            .read_text(encoding="utf-8")
            .strip()
        )
        template = (self.prompt_dir / "definition_user.txt").read_text(encoding="utf-8")
        registry = load_registry(self.registry_path)
        allowed = {
            name
            for name, license in registry.wordlists.items()
            if license.allows_use(self.registry_path)
        }
        if book is not None and book not in allowed:
            raise ValueError(
                f"Book is missing or blocked by its current license: {book}"
            )
        source_license = registry.wordnet
        if source_license.source_version != "3.0" or not source_license.allows_use(
            self.registry_path
        ):
            raise ValueError("A currently allowed WordNet 3.0 source is required")
        with self.storage.transaction() as connection:
            tables = {
                name
                for (name,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "p1_words" not in tables:
                raise ValueError("No matched WordNet data found")
            data = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM p1_words ORDER BY word_id"
                )
            ]
            latest = dict(
                connection.execute(
                    """
                SELECT task_id, status FROM ai_generations
                WHERE id IN (SELECT max(id) FROM ai_generations GROUP BY task_id)
                """
                )
            )
        wanted = {normalize_lemma(word) for word in words}
        vocabulary = {
            item["lemma"]
            for item in data
            if any(
                link["book_id"] == "basic_ngsl_1_2" and link["book_id"] in allowed
                for link in item["links"]
            )
        }
        jobs = []
        eligible_words = set()
        seen_words = set()
        inflections = {}
        wordnet_directory = (
            self.registry_path.parent / source_license.license_text
        ).parent
        for item in data:
            lemma = item["lemma"]
            if wanted and lemma not in wanted:
                continue
            if not any(
                link["book_id"] in allowed and (not book or link["book_id"] == book)
                for link in item["links"]
            ):
                continue
            origin = item.get("wordnet")
            if not origin or origin["source"] != source_license.model_dump(mode="json"):
                continue
            candidates = [
                sense for sense in item["candidates"] if self.eligible(sense, sense_id)
            ]
            candidates.sort(
                key=lambda x: (-(x.get("ranking_score") or 0), x["sense_id"])
            )
            if not candidates:
                continue
            eligible_words.add(lemma)
            if word_limit is not None and len(seen_words) >= word_limit:
                continue
            checksum_key = serialize(origin["sha256"])
            if checksum_key not in inflections:
                inflections[checksum_key] = load_inflections(
                    wordnet_directory, origin["sha256"]
                )
            for sense in candidates[:senses_per_word]:
                forms = inflections[checksum_key].get((sense["pos"], lemma), set())
                job = self.make_job(
                    lemma, sense, origin["sha256"], system, template, forms
                )
                state = latest.get(job.task_id)
                if (failed and state != "failed") or (
                    not failed and not force and state is not None
                ):
                    continue
                if limit is not None and len(jobs) >= limit:
                    break
                jobs.append(job)
                seen_words.add(lemma)
        if missing := wanted - eligible_words:
            raise ValueError(
                f"No eligible WordNet senses for: {', '.join(sorted(missing))}"
            )
        return jobs, vocabulary

    @staticmethod
    def eligible(sense: dict, sense_id: str | None) -> bool:
        status = sense["selection_status"]
        if status == "excluded":
            return False
        if sense_id is not None:
            return sense["sense_id"] == sense_id
        return status == "selected" or sense.get("is_recommended", False)

    def make_job(self, lemma, sense, checksums, system, template, forms) -> Job:
        source = {
            "word": lemma,
            "pos": sense["pos"],
            "sense_id": sense["sense_id"],
            "synset_id": sense.get("synset_id") or sense["source"]["source_id"],
            "original_definition": sense["source_definition"],
            "original_examples": sense["source_examples"],
            "target_level": "A2-B1",
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": template.format(source=serialize(source))},
        ]
        options = self.settings
        identity = [
            messages,
            checksums,
            sense["source"],
            self.config.prompt_version,
            options.provider,
            options.model,
            options.base_url,
            options.temperature,
            options.max_tokens,
            options.json_mode,
        ]
        task_id = sha256(serialize(identity).encode("utf-8")).hexdigest()
        input_bound = sum(len(msg["content"].encode("utf-8")) for msg in messages) + 128
        forms = forms | set(sense.get("matched_lemmas", []))
        return Job(
            task_id,
            source,
            messages,
            forms,
            input_bound,
            self.cost(input_bound, options.max_tokens),
        )

    def estimate(self, jobs: list[Job]) -> dict:
        options = self.settings
        return {
            "provider": options.provider,
            "model": options.model,
            "words": len({job.source["word"] for job in jobs}),
            "senses": len(jobs),
            "planned_requests": len(jobs),
            "max_requests_including_retries": len(jobs) * (1 + options.max_retries),
            "estimated_usd": round(sum(job.reserved_usd for job in jobs), 8),
            "estimated_usd_including_retries": round(
                sum(job.reserved_usd for job in jobs) * (1 + options.max_retries), 8
            ),
            "daily_budget_usd": self.daily_budget,
        }

    def _reserve(self, job: Job) -> int | None:
        timestamp = now()
        with self.storage.transaction() as connection:
            (spent,) = connection.execute(
                "SELECT coalesce(sum(coalesce(cost_usd, reserved_usd)), 0) "
                "FROM ai_requests WHERE started_at >= ?",
                (timestamp[:10],),
            ).fetchone()
            if spent + job.reserved_usd > self.daily_budget:
                return None
            return connection.execute(
                "INSERT INTO ai_requests(task_id, started_at, reserved_usd) VALUES (?, ?, ?)",
                (job.task_id, timestamp, job.reserved_usd),
            ).lastrowid

    def run(
        self, jobs: list[Job], vocabulary: set[str], provider_factory=ChatProvider
    ) -> dict:
        if not jobs:
            return {}
        settings = self.settings
        url = urlsplit(settings.base_url or "")
        if not (settings.api_key and settings.model):
            raise ValueError("Set LLM_API_KEY and LLM_MODEL before a real run")
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or (
                url.scheme != "https"
                and not (
                    url.scheme == "http"
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                )
            )
        ):
            raise ValueError(
                "LLM_BASE_URL must be an HTTPS endpoint or local HTTP endpoint"
            )
        self.stop.clear()
        with provider_factory(settings) as provider:
            executor = ThreadPoolExecutor(max_workers=settings.concurrency)
            try:
                results = list(
                    executor.map(
                        lambda job: self._generate(job, vocabulary, provider), jobs
                    )
                )
            finally:
                self.stop.set()
                executor.shutdown(wait=True, cancel_futures=True)
        return {status: results.count(status) for status in sorted(set(results))}

    def _pace(self) -> bool:
        with self.rate_lock:
            delay = max(0.0, self.next_request - time.monotonic())
            self.next_request = (
                time.monotonic() + delay + 60 / self.settings.requests_per_minute
            )
        return not self.stop.wait(delay)

    def _generate(self, job, vocabulary, provider) -> str:
        for attempt in range(1 + self.settings.max_retries):
            if not self._pace():
                return "stopped"
            request_id = self._reserve(job)
            if request_id is None:
                self.stop.set()
                return "budget_limit"
            start = time.monotonic()
            response = output = None
            code = "ok"
            retryable = False
            retry_after = 0.0
            try:
                response = provider.complete(job.messages)
                output = LearnerOutput.model_validate_json(response.text)
            except ProviderError as error:
                code = str(error)
                retryable, retry_after = error.retryable, error.retry_after
            except ValidationError:
                code = "invalid_model_json_or_schema"
                retryable = True

            elapsed = time.monotonic() - start
            retry = (
                retryable
                and attempt < self.settings.max_retries
                and not self.stop.is_set()
            )
            status = self._persist(
                job,
                request_id,
                response,
                output,
                code,
                elapsed,
                vocabulary,
                retry=retry,
            )
            if code in {"http_401", "http_403", "http_402", "http_404"}:
                self.stop.set()
            if not retry:
                return status
            retry_state = RetryCallState(None, None, (), {})
            retry_state.attempt_number = attempt + 1
            delay = max(retry_after, wait_exponential(min=1, max=16)(retry_state))
            if self.stop.wait(delay):
                return "stopped"
        raise AssertionError("Unreachable retry state")

    def _persist(
        self, job, request_id, response, output, code, elapsed, vocabulary, *, retry
    ):
        input_tokens = response.input_tokens if response else None
        output_tokens = response.output_tokens if response else None
        cost = None
        if input_tokens is not None and output_tokens is not None:
            cost = self.cost(input_tokens, output_tokens)
        elif code in {"http_401", "http_403", "http_402", "http_404", "http_429"}:
            cost = 0.0
        with self.storage.transaction() as connection:
            connection.execute(
                "UPDATE ai_requests SET cost_usd=?, input_tokens=?, output_tokens=?, "
                "elapsed=?, outcome=? WHERE id=?",
                (cost, input_tokens, output_tokens, elapsed, code, request_id),
            )
            if retry:
                return
            errors, warnings = [code], []
            if output is not None:
                errors, warnings = inspect_output(
                    output,
                    job.source,
                    job.forms,
                    vocabulary,
                    self.config.definition_max_words,
                    self.config.example_max_words,
                )
                self._check_duplicates(connection, job, output, errors)
            status = (
                "failed"
                if output is None
                else (
                    "needs_review"
                    if errors or warnings or output.generation_status == "needs_review"
                    else "generated"
                )
            )
            payload = {
                **job.source,
                "provider": self.settings.provider,
                "model": self.settings.model,
                "resolved_model": response.model if response else None,
                "prompt_version": self.config.prompt_version,
                "task_id": job.task_id,
                "request_id": request_id,
                "generation_status": status,
                "review_status": "pending",
                "validation_errors": errors,
                "warnings": warnings,
                "semantic_verification": "human_review_required",
                "generation_time_seconds": elapsed,
                "created_at": now(),
                "token_usage": {"input": input_tokens, "output": output_tokens},
                "estimated_cost_usd": cost,
                "simple_definition": output.simple_definition if output else None,
                "example_en": output.example if output else None,
                "difficulty": output.difficulty if output else None,
                "model_semantic_check": output.semantic_check if output else None,
                "model_review_reason": output.reason if output else None,
            }
            connection.execute(
                "INSERT INTO ai_generations(task_id,status,word,sense_id,payload) VALUES (?,?,?,?,?)",
                (
                    job.task_id,
                    status,
                    job.source["word"],
                    job.source["sense_id"],
                    serialize(payload),
                ),
            )
            return status

    @staticmethod
    def _check_duplicates(connection, job, output, errors):
        if not output.simple_definition:
            return
        definition = language_words(output.simple_definition)
        for (payload,) in connection.execute(
            "SELECT payload FROM ai_generations WHERE word=? AND sense_id<>? "
            "AND id IN (SELECT max(id) FROM ai_generations GROUP BY task_id)",
            (job.source["word"], job.source["sense_id"]),
        ):
            previous = json.loads(payload).get("simple_definition")
            if previous and language_words(previous) == definition:
                errors.append("DUPLICATE_DEFINITION")
                break

    def report(self) -> dict:
        with self.storage.transaction() as connection:
            results = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM ai_generations WHERE id IN "
                    "(SELECT max(id) FROM ai_generations GROUP BY task_id) ORDER BY word, sense_id, id"
                )
            ]
            summary = connection.execute(
                """
                SELECT count(*), coalesce(sum(input_tokens),0), coalesce(sum(output_tokens),0),
                    coalesce(sum(cost_usd),0), coalesce(sum(
                        CASE WHEN cost_usd IS NULL THEN reserved_usd ELSE 0 END),0),
                    coalesce(avg(elapsed),0), count(CASE WHEN cost_usd IS NULL THEN 1 END)
                FROM ai_requests
                """
            ).fetchone()
        count, inputs, outputs, cost, unknown_reserved, average, unknown_requests = (
            summary
        )
        completed = sum(row["generation_status"] != "failed" for row in results)
        passed = sum(row["generation_status"] == "generated" for row in results)
        return {
            "requests_started": count,
            "requests_without_cost": unknown_requests,
            "input_tokens": inputs,
            "output_tokens": outputs,
            "estimated_cost_usd": round(cost, 8),
            "unknown_cost_reserved_usd": unknown_reserved,
            "average_request_seconds": average,
            "tasks": len(results),
            "completed": completed,
            "success_rate": completed / len(results) if results else 0,
            "automatic_check_pass_rate": passed / completed if completed else 0,
            "needs_review": completed - passed,
            "needs_review_rate": (completed - passed) / completed if completed else 0,
            "human_review_pending": completed,
            "results": results,
        }
