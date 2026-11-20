import re
from hashlib import sha256
from pathlib import Path

from .models import CandidateSense, PartOfSpeech, SourceRef

POS: dict[PartOfSpeech, str] = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}
VERSION = "3.0"
CORE_FILES = {f"{kind}.{pos}" for pos in POS for kind in ("index", "data")}
AUX_FILES = {"index.sense", *(f"{pos}.exc" for pos in POS)}
RULES = {
    "noun": (
        ("s", ""),
        ("ses", "s"),
        ("xes", "x"),
        ("zes", "z"),
        ("ches", "ch"),
        ("shes", "sh"),
        ("men", "man"),
        ("ies", "y"),
    ),
    "verb": (
        ("s", ""),
        ("ies", "y"),
        ("es", "e"),
        ("es", ""),
        ("ed", "e"),
        ("ed", ""),
        ("ing", "e"),
        ("ing", ""),
    ),
    "adj": (("er", ""), ("est", ""), ("er", "e"), ("est", "e")),
    "adv": (),
}
TYPE_POS = {"1": "noun", "2": "verb", "3": "adj", "4": "adv", "5": "adj"}


class WordNet:
    def __init__(self, directory: Path, checksums: dict[str, str], license_id: str):
        self.index = {}
        self.data = {}
        self.license_id = license_id
        self.exceptions = {}
        self.tag_counts = None
        for pos, code in POS.items():
            for kind in ("index", "data"):
                name = f"{kind}.{pos}"
                content = checked_file(directory, name, checksums)
                if not re.search(rb"WordNet (?:Release )?3\.0\b", content[:4096]):
                    raise ValueError(f"{name}: expected WordNet 3.0 header")
                if kind == "data":
                    self.data[pos] = content
                else:
                    self.index[pos] = self._parse_index(content, code)
            name = f"{pos}.exc"
            if name in checksums or (directory / name).exists():
                content = checked_file(directory, name, checksums)
                self.exceptions[pos] = {
                    form: bases
                    for form, *bases in map(
                        str.split, content.decode("ascii").splitlines()
                    )
                }
        if "index.sense" in checksums or (directory / "index.sense").exists():
            content = checked_file(directory, "index.sense", checksums)
            self.tag_counts = {}
            for line in content.decode("ascii").splitlines():
                sense_key, offset, _, count = line.split()
                lemma, sense_type = sense_key.split("%", 1)
                self.tag_counts[lemma, TYPE_POS[sense_type[0]], int(offset)] = int(
                    count
                )

    def match(self, lemma: str) -> list[CandidateSense]:
        key = lemma.replace(" ", "_")
        by_id = {sense.sense_id: sense for sense in self.lookup(lemma)}
        for pos in POS:
            if "_" in key:
                continue
            exceptional = self.exceptions.get(pos, {}).get(key)
            bases = exceptional or [
                key[: -len(suffix)] + replacement
                for suffix, replacement in RULES[pos]
                if len(key) > len(suffix) and key.endswith(suffix)
            ]
            bases = sorted(
                {base for base in bases if base != key and base in self.index[pos]}
            )
            for base in bases:
                for sense in self.lookup(base, pos):
                    if previous := by_id.get(sense.sense_id):
                        if base not in previous.matched_lemmas:
                            previous.matched_lemmas.append(base)
                        continue
                    sense.lemma = lemma
                    sense.match_method = "morphology"
                    sense.match_confidence = (
                        "medium" if exceptional and len(bases) == 1 else "low"
                    )
                    by_id[sense.sense_id] = sense
        return list(by_id.values())

    @staticmethod
    def _parse_index(content: bytes, code: str) -> dict[str, list[int]]:
        index = {}
        for line in content.decode("ascii").splitlines():
            if not line or line.startswith(" "):
                continue
            lemma, pos, count, pointers, *fields = line.split()
            offsets = fields[int(pointers) + 2 :]
            if pos != code or len(offsets) != int(count):
                raise ValueError(f"Invalid WordNet index entry for {lemma}")
            index[lemma] = sorted(map(int, offsets))
        return index

    def lookup(
        self, lemma: str, pos: PartOfSpeech | None = None
    ) -> list[CandidateSense]:
        key = lemma.replace(" ", "_")
        return [
            self._read_sense(lemma, category, offset)
            for category in (POS if pos is None else (pos,))
            for offset in self.index[category].get(key, ())
        ]

    def _read_sense(self, lemma: str, pos: PartOfSpeech, offset: int) -> CandidateSense:
        content = self.data[pos]
        end = content.find(b"\n", offset)
        line = content[offset : end if end != -1 else None].decode("ascii")
        fields, separator, gloss = line.partition("|")
        tokens = fields.split()
        offset_id = f"{offset:08d}"
        valid_codes = {"a", "s"} if pos == "adj" else {POS[pos]}
        if not separator or len(tokens) < 4 or tokens[0] != offset_id:
            raise ValueError(f"Invalid WordNet synset at {pos}:{offset_id}")
        words = tokens[4 : 4 + 2 * int(tokens[3], 16) : 2]
        if tokens[2] not in valid_codes or lemma.replace(" ", "_") not in {
            word.split("(")[0].lower() for word in words
        }:
            raise ValueError(f"Inconsistent WordNet synset at {pos}:{offset_id}")

        gloss = gloss.strip()
        # WordNet places quoted examples after the definition, separated by semicolons.
        parts = re.split(r';\s*(?=")', gloss, maxsplit=1)
        examples = re.findall(r'"([^"]*)"', parts[1]) if len(parts) == 2 else []
        return CandidateSense(
            sense_id=f"wn30:{pos}:{offset_id}",
            lemma=lemma,
            pos=pos,
            source_definition=parts[0].strip(),
            source_examples=examples,
            source_gloss=gloss,
            synset_id=f"{tokens[2]}:{offset_id}",
            synonyms=[word.split("(")[0].replace("_", " ") for word in words],
            matched_lemmas=[lemma],
            tag_count=(
                self.tag_counts.get((lemma.replace(" ", "_"), pos, offset), 0)
                if self.tag_counts is not None
                else None
            ),
            source=SourceRef(
                source_name="Princeton WordNet",
                source_version=VERSION,
                source_id=f"{pos}:{offset_id}",
                license_id=self.license_id,
            ),
            selection_status="candidate",
        )


def checked_file(directory: Path, name: str, checksums: dict[str, str]) -> bytes:
    content = (directory / name).read_bytes()
    if sha256(content).hexdigest() != checksums.get(name):
        raise ValueError(f"Missing or incorrect SHA256 for {name}")
    return content
