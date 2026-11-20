import csv
import json
from contextlib import contextmanager
from pathlib import Path

import typer
import yaml

DEFAULT_DB = Path("data/state/pipeline.sqlite3")
DEFAULT_REGISTRY = Path("data/raw/sources.yaml")
DEFAULT_CONFIG = Path("config/pipeline.yaml")


@contextmanager
def command_errors():
    try:
        yield
    except (TypeError, ValueError, OSError, yaml.YAMLError, csv.Error) as error:
        raise typer.BadParameter(str(error)) from error


def show_result(result: dict) -> None:
    typer.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))
