import json
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError

from .ai_cli import ai
from .cli_options import (
    DEFAULT_CONFIG,
    DEFAULT_DB,
    DEFAULT_REGISTRY,
    command_errors,
    show_result,
)
from .config import load_llm_settings, load_pipeline_config
from .learner_ranking import rank_words
from .learner_view import export_learner_preview
from .mock import mock_response
from .models import CandidateSense
from .ngsl import BOOK, import_ngsl
from .p1 import SourcesPipeline
from .preview import serve
from .provenance import load_registry
from .storage import Storage
from .wordnet_source import install_wordnet, load_checksums

app = typer.Typer(
    help="Learner dictionary pipeline project tools.", no_args_is_help=True
)
sources = typer.Typer(help="Check source license records.", no_args_is_help=True)
app.add_typer(sources, name="sources")
app.add_typer(ai, name="ai")


@sources.command("import-ngsl")
def import_ngsl_command(
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
    raw_dir: Path = Path("data/raw/wordlists/ngsl"),
    config: Path = DEFAULT_CONFIG,
) -> None:
    """Import the approved official NGSL 1.2 snapshot."""
    with command_errors():
        if BOOK not in load_pipeline_config(config).books:
            raise ValueError(f"Book is not configured: {BOOK}")
        show_result(import_ngsl(db, registry, raw_dir))


@sources.command("check")
def check_sources(registry: Path = DEFAULT_REGISTRY) -> None:
    """Report the effective license status of registered sources."""
    with command_errors():
        if not registry.is_file():
            raise ValueError(f"Source registry not found: {registry}")
        entries = load_registry(registry)
        show_result(
            {
                "wordlists": {
                    book: "allowed" if source.allows_use(registry) else "blocked"
                    for book, source in entries.wordlists.items()
                },
                "wordnet": (
                    "allowed"
                    if entries.wordnet.source_version == "3.0"
                    and entries.wordnet.allows_use(registry)
                    else "blocked"
                ),
            }
        )


@app.command()
def ingest(
    book: Annotated[str, typer.Option()],
    file: Annotated[Path, typer.Option()],
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
    config: Path = DEFAULT_CONFIG,
) -> None:
    """Import a configured book's CSV snapshot."""
    with command_errors():
        if book not in load_pipeline_config(config).books:
            raise ValueError(f"Book is not configured: {book}")
        show_result(SourcesPipeline(db, registry).ingest(book, file))


@app.command("normalize")
def normalize_words(db: Path = DEFAULT_DB, registry: Path = DEFAULT_REGISTRY) -> None:
    """Normalize and deduplicate imported lemmas across books."""
    with command_errors():
        show_result(SourcesPipeline(db, registry).normalize())


@app.command()
def match_wordnet(
    wordnet_dir: Annotated[Path, typer.Option()],
    checksums: Path | None = None,
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
    book: str | None = None,
    limit: Annotated[int | None, typer.Option(min=1)] = None,
    retry_failed: bool = False,
    config: Path = DEFAULT_CONFIG,
) -> None:
    """Match exact and inflected forms. Retry only unmatched words with --retry-failed."""
    with command_errors():
        manifest = checksums if checksums is not None else wordnet_dir / "sha256.json"
        settings = load_pipeline_config(config)
        show_result(
            SourcesPipeline(db, registry).match(
                wordnet_dir,
                load_checksums(manifest),
                book=book,
                limit=limit,
                retry_failed=retry_failed,
                recommendation_limit=settings.wordnet_recommendation_limit,
                min_tags=settings.wordnet_min_tag_count,
            )
        )


@app.command()
def prepare_wordnet(
    wordnet_dir: Path = Path("data/raw/wordnet30"),
    archive: Path | None = None,
) -> None:
    """Download, install a local archive, or verify an installed WordNet 3.0 snapshot."""
    with command_errors():
        show_result(install_wordnet(wordnet_dir, archive))


@app.command()
def show_wordnet(
    lemma: str,
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
) -> None:
    """Show all stored candidates for one imported word."""
    with command_errors():
        show_result(SourcesPipeline(db, registry).word(lemma))


@app.command()
def wordnet_report(
    out: Path | None = None,
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
) -> None:
    """Report persisted match coverage and unmatched lemmas by book."""
    with command_errors():
        result = SourcesPipeline(db, registry).quality()
        if out is not None:
            out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        show_result(result)


@app.command()
def select_senses(
    decisions: Annotated[Path, typer.Option()],
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
) -> None:
    """Apply explicit lemma and sense selections from CSV."""
    with command_errors():
        show_result(SourcesPipeline(db, registry).select(decisions))


@app.command("init-state")
def init_state(db: Path = DEFAULT_DB) -> None:
    """Initialize the local SQLite database."""
    Storage(db).initialize()
    typer.echo(f"Initialized {db}")


@app.command()
def preview(
    db: Path = DEFAULT_DB,
    port: Annotated[int, typer.Option(min=0, max=65535)] = 8765,
) -> None:
    """Serve a local read-only vocabulary preview."""
    with command_errors():
        serve(db, port)


@app.command()
def export_learner(
    out: Annotated[Path, typer.Option()],
    db: Path = DEFAULT_DB,
) -> None:
    """Export the local learner preview as JSONL."""
    with command_errors():
        show_result({"words": export_learner_preview(db, out)})


@app.command()
def rank_learner(
    limit: Annotated[int | None, typer.Option(min=1)] = None,
    execute: bool = False,
    budget: Annotated[float, typer.Option(min=0)] = 0,
    db: Path = DEFAULT_DB,
    registry: Path = DEFAULT_REGISTRY,
) -> None:
    """Estimate or execute offline AI ranking of existing WordNet senses."""
    with command_errors():
        summary = rank_words(
            db,
            load_llm_settings(),
            load_registry(registry),
            registry,
            limit=limit,
            execute=execute,
            budget=budget,
        )
        if execute:
            show_result(summary)


@app.command("mock-response")
def mock_response_command(
    candidate: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, readable=True)
    ],
    config: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, readable=True)
    ] = Path("config/pipeline.yaml"),
) -> None:
    """Print a deterministic offline sample for a candidate JSON file."""
    try:
        settings = load_pipeline_config(config)
        sense = CandidateSense.model_validate_json(
            candidate.read_text(encoding="utf-8")
        )
    except (ValidationError, yaml.YAMLError, UnicodeError, OSError) as error:
        raise typer.BadParameter(
            "Could not load the candidate or pipeline configuration."
        ) from error
    typer.echo(mock_response(sense, settings.prompt_version).model_dump_json())
