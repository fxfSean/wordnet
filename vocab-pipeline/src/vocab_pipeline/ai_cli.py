import json
from pathlib import Path
from typing import Annotated

import typer

from . import cli_options
from .ai_pipeline import TRIAL_WORDS, GenerationPipeline
from .config import load_llm_settings, load_pipeline_config

ai = typer.Typer(
    help="Generate and inspect learner English drafts.", no_args_is_help=True
)
Positive = Annotated[int | None, typer.Option(min=1)]


def pipeline(db: Path, registry: Path, config: Path, env: Path) -> GenerationPipeline:
    settings = load_pipeline_config(config)
    return GenerationPipeline(
        db,
        registry,
        settings,
        load_llm_settings(env),
        config.parent / "prompts" / settings.prompt_version,
    )


@ai.command()
def generate(
    book: str | None = None,
    word: Annotated[list[str] | None, typer.Option()] = None,
    limit: Positive = None,
    word_limit: Positive = None,
    sense_id: str | None = None,
    senses_per_word: Positive = None,
    trial: bool = False,
    force: bool = False,
    dry_run: bool = False,
    execute: bool = False,
    db: Path = cli_options.DEFAULT_DB,
    registry: Path = cli_options.DEFAULT_REGISTRY,
    config: Path = cli_options.DEFAULT_CONFIG,
    env: Path = Path(".env"),
) -> None:
    """Preview a plan, or generate drafts with the explicitly configured API."""
    with cli_options.command_errors():
        if force and not (word or sense_id):
            raise ValueError("Force generation requires --word or --sense-id")
        if trial:
            if any((book, word, limit, word_limit, sense_id, senses_per_word, force)):
                raise ValueError(
                    "--trial uses a fixed book, word list and one sense per word"
                )
            book, word, senses_per_word = "basic_ngsl_1_2", TRIAL_WORDS, 1
        runner = pipeline(db, registry, config, env)
        run_plan(
            runner,
            execute and not dry_run,
            book=book,
            words=word or (),
            limit=limit,
            word_limit=word_limit,
            sense_id=sense_id,
            senses_per_word=senses_per_word,
            force=force,
        )


@ai.command()
def retry(
    failed: bool = typer.Option(False, "--failed/--no-failed"),
    book: str | None = None,
    word: Annotated[list[str] | None, typer.Option()] = None,
    limit: Positive = None,
    dry_run: bool = False,
    execute: bool = False,
    db: Path = cli_options.DEFAULT_DB,
    registry: Path = cli_options.DEFAULT_REGISTRY,
    config: Path = cli_options.DEFAULT_CONFIG,
    env: Path = Path(".env"),
) -> None:
    """Retry failed tasks for the current provider, model and prompt."""
    with cli_options.command_errors():
        if not failed:
            raise ValueError("Specify --failed")
        run_plan(
            pipeline(db, registry, config, env),
            execute and not dry_run,
            failed=True,
            book=book,
            words=word or (),
            limit=limit,
        )


@ai.command()
def estimate(
    book: str | None = None,
    word: Annotated[list[str] | None, typer.Option()] = None,
    limit: Positive = None,
    word_limit: Positive = None,
    db: Path = cli_options.DEFAULT_DB,
    registry: Path = cli_options.DEFAULT_REGISTRY,
    config: Path = cli_options.DEFAULT_CONFIG,
    env: Path = Path(".env"),
) -> None:
    """Estimate calls and costs without sending model requests."""
    with cli_options.command_errors():
        run_plan(
            pipeline(db, registry, config, env),
            False,
            book=book,
            words=word or (),
            limit=limit,
            word_limit=word_limit,
        )


@ai.command()
def report(
    out: Path | None = None,
    db: Path = cli_options.DEFAULT_DB,
    registry: Path = cli_options.DEFAULT_REGISTRY,
    config: Path = cli_options.DEFAULT_CONFIG,
    env: Path = Path(".env"),
) -> None:
    """Report persisted draft quality, token usage and estimated cost."""
    with cli_options.command_errors():
        result = pipeline(db, registry, config, env).report()
        if out is not None:
            out.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            cli_options.show_result(
                {key: value for key, value in result.items() if key != "results"}
            )
        else:
            cli_options.show_result(result)


def run_plan(runner: GenerationPipeline, execute: bool, **filters) -> None:
    if not execute:
        jobs, _ = runner.plan(**filters)
        cli_options.show_result(runner.estimate(jobs))
        return
    with runner.exclusive_generation():
        jobs, vocabulary = runner.plan(**filters)
        cli_options.show_result(runner.estimate(jobs))
        cli_options.show_result(runner.run(jobs, vocabulary))
