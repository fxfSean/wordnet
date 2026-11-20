import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .learner_view import learner_entry, read_ranking
from .normalize import normalize_lemma, word_id

AI_FIELDS = (
    "simple_definition",
    "example_en",
    "difficulty",
    "review_status",
    "generation_status",
)


def lookup(db: Path, lemma: str, *, learner: bool = False) -> dict | None:
    normalized = normalize_lemma(lemma)
    with closing(
        sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    ) as connection:
        row = connection.execute(
            "SELECT payload FROM p1_words WHERE word_id = ?", (word_id(normalized),)
        ).fetchone()
        if row is None:
            return None
        word = json.loads(row[0])
        if learner:
            return learner_entry(
                word, read_ranking(connection, word_id(normalized), word)
            )
        has_ai = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_generations'"
        ).fetchone()
        drafts = {}
        if has_ai:
            for sense_id, payload in connection.execute(
                "SELECT sense_id, payload FROM ai_generations WHERE word=? "
                "AND status IN ('generated', 'needs_review') ORDER BY id DESC",
                (normalized,),
            ):
                if sense_id not in drafts:
                    draft = json.loads(payload)
                    drafts[sense_id] = {field: draft.get(field) for field in AI_FIELDS}
    origin = word.get("wordnet")
    return {
        "word": word["lemma"],
        "book_ids": sorted({link["book_id"] for link in word["links"]}),
        "match_status": word.get("match_status", "pending"),
        "wordnet_version": origin["source"]["source_version"] if origin else None,
        "senses": [
            {
                "sense_id": sense["sense_id"],
                "pos": sense["pos"],
                "definition_original": sense["source_definition"],
                "examples_original": sense["source_examples"],
                "recommended": sense.get("is_recommended", False),
                "ai_draft": drafts.get(sense["sense_id"]),
            }
            for sense in word["candidates"]
        ],
    }


def serve(db: Path, port: int) -> None:
    if not db.is_file():
        raise ValueError(f"SQLite state database not found: {db}")
    html = files(__package__).joinpath("preview.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status: int, content_type: str, content: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def send_json(self, status: int, data: dict) -> None:
            self.respond(
                status,
                "application/json; charset=utf-8",
                json.dumps(data, ensure_ascii=False).encode("utf-8"),
            )

        def do_GET(self) -> None:
            route = urlsplit(self.path)
            if route.path == "/":
                self.respond(200, "text/html; charset=utf-8", html)
                return
            if route.path not in {"/api/word", "/api/learner-word"}:
                self.send_json(404, {"error": "Route not found"})
                return
            lemma = parse_qs(route.query).get("lemma", [""])[0].strip()
            if not lemma or len(lemma) > 140:
                self.send_json(400, {"error": "请输入 1–140 个字符的英文词或词组。"})
                return
            try:
                result = lookup(db, lemma, learner=route.path == "/api/learner-word")
            except sqlite3.Error:
                self.send_json(503, {"error": "无法读取词库数据库。"})
                return
            if result is None:
                self.send_json(404, {"error": "本地词表未收录这个词。"})
            else:
                self.send_json(200, result)

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Vocabulary preview: http://127.0.0.1:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
