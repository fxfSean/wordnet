import json
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from urllib.error import URLError

import pytest
import yaml
from typer.testing import CliRunner

from vocab_pipeline.cli import app
from vocab_pipeline.normalize import normalize_lemma, word_id
from vocab_pipeline.sense_selection import recommend_senses
from vocab_pipeline.wordnet_adapter import POS, WordNet
from vocab_pipeline.wordnet_source import install_wordnet


def make_wordnet(directory, version="3.0"):
    directory.mkdir(exist_ok=True)
    header = f"  1 WordNet {version} synthetic test data\n".encode("ascii")
    entries = {
        "noun": [
            ("anchor", "An object that holds a boat in place"),
            ("apple", "An edible fruit"),
            ("bank", 'An institution that handles money; "the bank opened"'),
            ("bank", "Land beside a river"),
            ("ice_cream", "A frozen dessert"),
            ("light", "Electromagnetic radiation"),
        ],
        "verb": [
            ("bank", "To tilt when turning"),
            ("go", "To move from one place to another"),
            ("light", "To set on fire"),
            ("run", "To move fast on foot"),
            ("see", "To notice with the eyes"),
        ],
        "adj": [
            ("light", "Of little weight"),
            ("well-known", "Recognized by many people"),
        ],
    }
    checksums = {}
    for pos, code in POS.items():
        data = bytearray(header)
        offsets = {}
        for lemma, gloss in entries.get(pos, []):
            offset = f"{len(data):08d}"
            offsets.setdefault(lemma, []).append(offset)
            sense_code = "s" if code == "a" else code
            data.extend(
                f"{offset} 00 {sense_code} 01 {lemma} 0 000 | {gloss}\n".encode("ascii")
            )
        index = bytes(header) + "".join(
            f"{lemma} {code} {len(ids)} 0 {len(ids)} 0 {' '.join(ids)}\n"
            for lemma, ids in sorted(offsets.items())
        ).encode("ascii")
        for name, content in ((f"data.{pos}", data), (f"index.{pos}", index)):
            (directory / name).write_bytes(content)
            checksums[name] = sha256(content).hexdigest()
    (directory / "sha256.json").write_text(json.dumps(checksums), encoding="utf-8")
    return checksums


@pytest.mark.parametrize(
    "text,expected",
    [
        ("  ＩＣＥ   Cream ", "ice cream"),
        ("DON'T", "don't"),
        ("Well-Known", "well-known"),
        ("SAW", "saw"),
    ],
)
def test_normalization(text, expected):
    assert normalize_lemma(text) == expected
    assert word_id("ice cream") != word_id("ice%20cream")


def test_wordnet_checksums_and_version(tmp_path):
    checksums = make_wordnet(tmp_path, "3.1")
    with pytest.raises(ValueError, match="3.0 header"):
        WordNet(tmp_path, checksums, "fixture")
    checksums = make_wordnet(tmp_path)
    net = WordNet(tmp_path, checksums, "fixture")
    assert len(net.lookup("bank", "noun")) == 2
    assert net.lookup("bank", "verb")[0].pos == "verb"
    assert net.lookup("well-known")[0].pos == "adj"
    (tmp_path / "data.noun").write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256"):
        WordNet(tmp_path, checksums, "fixture")


def test_morphology_and_ranking(tmp_path):
    checksums = make_wordnet(tmp_path)
    exceptions = b"running run\nwent go\n"
    (tmp_path / "verb.exc").write_bytes(exceptions)
    checksums["verb.exc"] = sha256(exceptions).hexdigest()
    net = WordNet(tmp_path, checksums, "fixture")
    assert net.match("apple")[0].synonyms == ["apple"]
    assert net.match("run")[0].match_method == "exact"
    assert {sense.pos for sense in net.match("light")} == {"noun", "verb", "adj"}
    assert not net.match("zibblewug")
    for inflection, base in (("running", "run"), ("went", "go")):
        (candidate,) = net.match(inflection)
        assert candidate.match_method == "morphology"
        assert candidate.match_confidence == "medium"
        assert candidate.matched_lemmas == [base]
        assert candidate.lemma == inflection

    bank = net.match("bank")
    assert len(bank) == 3
    assert recommend_senses(bank, 1, 1)
    assert not any(sense.is_recommended for sense in bank)
    for candidate, count in zip(bank, (2, 9, 1), strict=True):
        candidate.tag_count = count
    assert not recommend_senses(bank, 1, 1)
    assert [sense for sense in bank if sense.is_recommended] == [bank[1]]
    bank[0].tag_count = 9
    assert recommend_senses(bank, 1, 1)
    assert not any(sense.is_recommended for sense in bank)


def test_wordnet_missing_and_download_failure(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        WordNet(missing, {}, "fixture")

    def offline(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr("vocab_pipeline.wordnet_source.urlopen", offline)
    with pytest.raises(URLError, match="offline"):
        install_wordnet(missing)
    assert not missing.exists()


def test_p1_cli(tmp_path):
    db = tmp_path / "state.db"
    registry = tmp_path / "sources.yaml"
    config = tmp_path / "config.yaml"
    directory = tmp_path / "wordnet"
    make_wordnet(directory)
    (tmp_path / "license.txt").write_text("Synthetic fixture license", encoding="utf-8")
    source = {
        "source_name": "Synthetic fixture",
        "source_version": "1",
        "url": "https://example.invalid",
        "acquired_at": "2026-11-16",
        "license_id": "fixture",
        "license_name": "Development fixture",
        "license_text": "license.txt",
        "commercial_use": True,
        "modification": True,
        "redistribution": True,
        "cloud_storage": True,
        "attribution_required": False,
        "reviewer": "fixture",
        "reviewed_at": "2026-11-16",
        "status": "allowed",
    }
    entries = {
        "wordlists": {"left": source.copy(), "right": source.copy()},
        "wordnet": source | {"source_version": "3.0"},
    }
    registry.write_text(yaml.safe_dump(entries), encoding="utf-8")
    base_config = Path(__file__).resolve().parents[1] / "config" / "pipeline.yaml"
    options = yaml.safe_load(base_config.read_text(encoding="utf-8"))
    config.write_text(
        yaml.safe_dump(options | {"books": ["left", "right", "unknown"]}),
        encoding="utf-8",
    )
    runner = CliRunner()

    def invoke(*args, ok=True):
        result = runner.invoke(
            app, [*args, "--db", str(db), "--registry", str(registry)]
        )
        if ok:
            assert result.exit_code == 0, (result.output, result.exception)
            return json.loads(result.output)
        assert result.exit_code != 0

    def ingest(book, lines, *, ok=True):
        path = tmp_path / f"{book}.csv"
        path.write_text(lines, encoding="utf-8-sig")
        return invoke(
            "ingest",
            "--book",
            book,
            "--file",
            str(path),
            "--config",
            str(config),
            ok=ok,
        )

    def snapshot():
        with closing(sqlite3.connect(db)) as connection:
            return dict(
                connection.execute("SELECT word_id, payload FROM p1_words")
            ), list(
                connection.execute("SELECT * FROM records ORDER BY job_id, record_id")
            )

    header = "lemma,source_ref,rank\n"
    left = (
        header
        + "anchor,left:1,1\nBank,left:2,2\nBank,left:2,2\nsaw,left:3,\n,left:4,\n"
    )
    assert ingest("left", left) == {
        "total": 5,
        "duplicates": 1,
        "invalid": 1,
        "stored_rows": 3,
        "license_blocked": 0,
    }
    ingest("left", "wrong,header\n", ok=False)
    ingest("right", header + "ＢＡＮＫ,right:1,\nice cream,right:2,\n")
    assert ingest("unknown", header + "well-known,unknown:1,\n")["license_blocked"] == 1
    before = invoke("normalize")
    assert before == {"BLOCKED_LICENSE": 1, "NORMALIZED": 4}
    invoke(
        "match-wordnet",
        "--wordnet-dir",
        str(directory),
        "--book",
        "left",
        "--limit",
        "1",
    )
    partial = invoke("wordnet-report")
    assert partial["exact"] == 1
    assert partial["pending"] == 3
    assert partial["books"]["left"]["matched"] == 1
    assert invoke("match-wordnet", "--wordnet-dir", str(directory)) == {
        "AMBIGUOUS": 1,
        "BLOCKED_LICENSE": 1,
        "MATCHED": 2,
        "UNMATCHED": 1,
    }
    report = invoke("wordnet-report")
    assert report["unmatched_words"] == ["saw"]
    assert report["polysemous"] == 1
    assert report["books"]["unknown"]["blocked"] == 1
    old = snapshot()
    invoke("match-wordnet", "--wordnet-dir", str(directory), "--retry-failed")
    assert snapshot() == old
    bank = json.loads(snapshot()[0]["w_bank"])
    assert [(link["book_id"], link["display_lemma"]) for link in bank["links"]] == [
        ("left", "Bank"),
        ("right", "ＢＡＮＫ"),
    ]
    assert len(bank["candidates"]) == 3
    assert {item["selection_status"] for item in bank["candidates"]} == {"needs_review"}
    assert bank["candidates"][0]["source_examples"] == ["the bank opened"]
    assert (
        bank["candidates"][0]["source_definition"]
        == "An institution that handles money"
    )
    assert "the bank opened" in bank["candidates"][0]["source_gloss"]
    assert bank["wordnet"]["sha256"] == json.loads(
        (directory / "sha256.json").read_text(encoding="utf-8")
    )

    decisions = tmp_path / "sense_selection.csv"
    selected = bank["candidates"][0]["sense_id"]
    decisions.write_text(
        f"lemma,sense_id\nBank,{selected}\nsaw,bad-id\n", encoding="utf-8"
    )
    old = snapshot()
    invoke("select-senses", "--decisions", str(decisions), ok=False)
    assert snapshot() == old
    decisions.write_text(f"lemma,sense_id\nBank,{selected}\n", encoding="utf-8")
    assert invoke("select-senses", "--decisions", str(decisions))["SELECTED"] == 1
    old = snapshot()
    ingest("left", left)
    invoke("normalize")
    invoke("match-wordnet", "--wordnet-dir", str(directory))
    invoke("select-senses", "--decisions", str(decisions))
    assert snapshot() == old

    entries["wordlists"]["left"]["status"] = "blocked"
    entries["wordnet"]["status"] = "blocked"
    registry.write_text(yaml.safe_dump(entries), encoding="utf-8")
    assert invoke("normalize") == {"BLOCKED_LICENSE": 3, "NORMALIZED": 2}
    assert json.loads(snapshot()[0]["w_bank"])["candidates"] == []
    result = runner.invoke(app, ["sources", "check", "--registry", str(registry)])
    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "wordlists": {"left": "blocked", "right": "allowed"},
        "wordnet": "blocked",
    }
