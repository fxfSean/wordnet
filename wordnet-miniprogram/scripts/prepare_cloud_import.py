"""Generate idempotent SQL batches for importing the NGSL development preview."""
import argparse
import json
from pathlib import Path
import sqlite3

WORKSPACE = Path(__file__).resolve().parents[2]
PIPELINE = WORKSPACE / "vocab-pipeline"
BOOK = "basic_ngsl_1_2"
MAX_BATCH_BYTES = 24_000


def literal(value):
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    tag = "$vocab$"
    if tag in payload:
        raise ValueError("Unexpected SQL delimiter in dataset")
    return tag + payload + tag


def batch_sql(rows):
    return f"""
WITH input AS (
 SELECT * FROM jsonb_to_recordset({literal(rows)}::jsonb)
 AS row(word_id text, lemma text, rank integer, senses jsonb)
), inserted_words AS (
 INSERT INTO vocab.words(word_id, lemma, content_version)
 SELECT word_id, lemma, 1 FROM input
 ON CONFLICT (word_id) DO NOTHING RETURNING word_id
), inserted_items AS (
 INSERT INTO vocab.wordbook_items(book_id, word_id, display_order)
 SELECT '{BOOK}', word_id, rank FROM input
 ON CONFLICT (book_id, word_id) DO NOTHING RETURNING word_id
), inserted_senses AS (
 INSERT INTO vocab.word_senses
 (word_id, sense_id, pos, definition_en, examples_en, display_order, is_primary, source)
 SELECT w.word_id, s.sense_id, s.pos, s.definition_en, s.examples_en, s.display_order,
        s.is_primary, jsonb_build_object(
          'source_id', s.source_id, 'name', 'Princeton WordNet', 'version', '3.0',
          'license_id', 'wordnet-3.0', 'ranking_source', s.ranking_source)
 FROM input w CROSS JOIN LATERAL jsonb_to_recordset(w.senses)
 AS s(sense_id text, pos text, definition_en text, examples_en text[], display_order integer,
      is_primary boolean, source_id text, ranking_source text)
 ON CONFLICT (word_id, sense_id) DO NOTHING RETURNING word_id
)
SELECT (SELECT count(*) FROM inserted_words) AS words,
       (SELECT count(*) FROM inserted_items) AS items,
       (SELECT count(*) FROM inserted_senses) AS senses;
""".strip()


def prepare(out):
    db_uri = (PIPELINE / "data/state/pipeline.sqlite3").as_uri() + "?mode=ro"
    with sqlite3.connect(db_uri, uri=True) as db:
        words = {
            word["lemma"]: (word_id, word)
            for word_id, payload in db.execute("SELECT word_id,payload FROM p1_words")
            if (word := json.loads(payload))
        }
    preview = (PIPELINE / "data/interim/learner-preview.jsonl").read_text(encoding="utf-8")
    rows, ranks = [], set()
    book_sources = set()
    for line in preview.splitlines():
        entry = json.loads(line)
        identifier, stored = words.pop(entry["word"])
        linked, = [link for link in stored["links"] if link["book_id"] == BOOK]
        source = linked["source"]
        if (linked["license_status"] != "allowed" or source["status"] != "allowed"
                or not all(source[field] is True for field in
                           ("commercial_use", "modification", "redistribution", "cloud_storage"))):
            raise ValueError(f"Source is not eligible: {identifier}")
        book_sources.add(literal(source))
        rank = linked["rank"]
        if not isinstance(rank, int) or rank <= 0 or rank in ranks:
            raise ValueError(f"Invalid NGSL rank: {rank}")
        ranks.add(rank)

        base = {sense["sense_id"]: sense for sense in stored["candidates"]}
        senses = []
        for sense in entry["senses"]:
            origin = base[sense["sense_id"]]
            ref = origin["source"]
            if (sense["definition_en"], sense["examples_en"], sense["pos"]) != (
                origin["source_definition"], origin["source_examples"], origin["pos"]
            ) or (ref["source_version"], ref["license_id"]) != ("3.0", "wordnet-3.0"):
                raise ValueError(f"WordNet provenance mismatch: {identifier}")
            senses.append(sense | {
                "source_id": ref["source_id"], "ranking_source": entry["ranking_source"],
            })
        rows.append({"word_id": identifier, "lemma": entry["word"], "rank": rank, "senses": senses})
    if words or len(book_sources) != 1:
        raise ValueError("Preview and SQLite input are inconsistent")
    book_source, = book_sources
    out.mkdir(parents=True, exist_ok=False)
    (out / "0000.sql").write_text(
        f"INSERT INTO vocab.wordbooks(book_id,title,enabled,content_version,source) "
        f"VALUES ('{BOOK}','General English',false,1,{book_source}::jsonb) "
        "ON CONFLICT (book_id) DO NOTHING;", encoding="utf-8"
    )
    batch, size, number = [], 0, 1
    for row in sorted(rows, key=lambda row: row["rank"]):
        row_size = len(literal(row).encode("utf-8"))
        if batch and size + row_size > MAX_BATCH_BYTES:
            (out / f"{number:04}.sql").write_text(batch_sql(batch), encoding="utf-8")
            batch, size, number = [], 0, number + 1
        batch.append(row)
        size += row_size
    if batch:
        (out / f"{number:04}.sql").write_text(batch_sql(batch), encoding="utf-8")
    print(json.dumps({"words": len(rows), "senses": sum(len(row["senses"]) for row in rows),
                      "batches": number + 1}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    prepare(parser.parse_args().out)
