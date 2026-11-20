"""Generate Chinese translations for WordNet definitions/examples.

This is an optional build-time helper.  It talks to any OpenAI-compatible chat
completions endpoint and writes a sidecar JSONL that ``prepare_data.py`` merges
into the mini-program catalog.

Examples::

    python scripts/translate_content.py --kind examples --dry-run
    python scripts/translate_content.py --kind examples --limit 100
    python scripts/translate_content.py --kind definitions --batch-size 20

Environment variables: ``LLM_BASE_URL`` (default ``https://api.deepseek.com/v1``),
``LLM_API_KEY`` and ``LLM_MODEL`` (default ``deepseek-chat``).
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT.parent / "vocab-pipeline"
SOURCE = PIPELINE / "data/interim/learner-preview.jsonl"
OUTPUTS = {
    "examples": PIPELINE / "data/interim/example-zh.jsonl",
    "definitions": PIPELINE / "data/interim/definition-zh.jsonl",
}


def load_existing(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            en, zh = row.get("en"), row.get("zh")
            if isinstance(en, str) and isinstance(zh, str):
                values[en] = zh
    return values


def collect(kind: str) -> list[str]:
    seen: dict[str, None] = {}
    with SOURCE.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            for sense in row["senses"]:
                if kind == "examples":
                    for example in sense.get("examples_en", []):
                        if example:
                            seen.setdefault(example, None)
                else:
                    definition = sense.get("definition_en")
                    if definition:
                        seen.setdefault(definition, None)
    return list(seen)


def write_rows(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        for en, zh in values.items():
            file.write(json.dumps({"en": en, "zh": zh}, ensure_ascii=False) + "\n")
    temp.replace(path)


def request(batch: list[str], kind: str) -> list[str]:
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    if not key:
        raise SystemExit("LLM_API_KEY is required (or use --dry-run).")
    label = "definitions" if kind == "definitions" else "example sentences"
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You translate English learner vocabulary content into natural, concise "
                    "Simplified Chinese. Preserve meaning and tone. Return only a JSON array "
                    "of strings, in the same order and with the same length as the input."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "kind": label,
                    "items": batch,
                }, ensure_ascii=False),
            },
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                parsed = parsed.get("translations") or parsed.get("items")
            if not isinstance(parsed, list) or len(parsed) != len(batch):
                raise ValueError("Model returned an unexpected number of translations.")
            if not all(isinstance(item, str) and item.strip() for item in parsed):
                raise ValueError("Model returned an empty translation.")
            return [item.strip() for item in parsed]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
            if attempt == 2:
                raise SystemExit(f"Translation request failed: {error}")
            time.sleep(2 ** attempt)
    raise SystemExit("Translation request failed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["examples", "definitions", "both"], default="examples")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    kinds = ["examples", "definitions"] if args.kind == "both" else [args.kind]
    for kind in kinds:
        source = collect(kind)
        output = args.out if args.out and len(kinds) == 1 else OUTPUTS[kind]
        existing = load_existing(output)
        missing = [item for item in source if item not in existing]
        if args.limit:
            missing = missing[:args.limit]
        batches = (len(missing) + args.batch_size - 1) // args.batch_size
        print(json.dumps({
            "kind": kind,
            "source_items": len(source),
            "translated": len(existing),
            "missing": len(missing),
            "batches": batches,
            "output": str(output),
            "dry_run": args.dry_run,
        }, ensure_ascii=False))
        if args.dry_run or not missing:
            continue
        for start in range(0, len(missing), args.batch_size):
            batch = missing[start:start + args.batch_size]
            translated = request(batch, kind)
            for en, zh in zip(batch, translated):
                existing[en] = zh
            write_rows(output, existing)
            print(f"{kind}: {min(start + len(batch), len(missing))}/{len(missing)}", flush=True)
        print(f"Saved {output}")


if __name__ == "__main__":
    main()
