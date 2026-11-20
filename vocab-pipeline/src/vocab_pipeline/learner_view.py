import json
import sqlite3
from contextlib import closing
from pathlib import Path

from .learner_ranking import ranking_hash


def read_ranking(connection, identifier, word):
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='learner_rankings'"
    ).fetchone():
        return None
    row = connection.execute(
        "SELECT result FROM learner_rankings WHERE word_id=? AND fingerprint=?",
        (identifier, ranking_hash(word)),
    ).fetchone()
    return json.loads(row[0]) if row else None


def learner_entry(word: dict, ai_ranking: dict | None = None) -> dict:
    """Project WordNet evidence into a preview of the learner-facing entry."""
    candidates = word["candidates"]
    selected = [
        sense for sense in candidates if sense["selection_status"] == "selected"
    ]
    source = "manual_selection" if selected else "wordnet_tag_count"
    visible = selected or [
        sense
        for sense in candidates
        if sense.get("is_recommended") and sense["selection_status"] != "excluded"
    ]
    ranked = sorted(
        visible,
        key=lambda sense: (-(sense.get("ranking_score") or 0), sense["sense_id"]),
    )
    primary_count = 2
    if ai_ranking and not selected:
        by_id = {sense["sense_id"]: sense for sense in candidates}
        ranked = [
            by_id[sense_id] for sense_id in ai_ranking["primary"] + ai_ranking["more"]
        ]
        primary_count = len(ai_ranking["primary"])
        source = "ai_selection"
    return {
        "word": word["lemma"],
        "match_status": word.get("match_status", "pending"),
        "ranking_source": source if ranked else None,
        "needs_review": not selected
        and (not ranked or word.get("needs_review", False)),
        "senses": [
            {
                "sense_id": sense["sense_id"],
                "pos": sense["pos"],
                "definition_en": sense["source_definition"],
                "examples_en": sense["source_examples"],
                "display_order": index,
                "is_primary": index <= primary_count,
            }
            for index, sense in enumerate(ranked, start=1)
        ],
    }


def export_learner_preview(db: Path, out: Path) -> int:
    with closing(
        sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        entries = []
        for identifier, payload in connection.execute(
            "SELECT word_id,payload FROM p1_words ORDER BY word_id"
        ):
            word = json.loads(payload)
            entries.append(
                learner_entry(word, read_ranking(connection, identifier, word))
            )
    out.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return len(entries)
