import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import PartOfSpeech
from .wordnet_adapter import POS, checked_file

WORDS = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
FOREIGN = re.compile(r"[^\x00-\x7f’‘“”–—…]")
DIFFICULTIES = ("A1", "A2", "B1", "B2", "C1", "C2")


def load_inflections(directory: Path, checksums: dict) -> dict:
    forms = defaultdict(set)
    for pos in POS:
        name = f"{pos}.exc"
        if name not in checksums or not (directory / name).is_file():
            continue
        for line in (
            checked_file(directory, name, checksums).decode("ascii").splitlines()
        ):
            inflection, *bases = line.split()
            for base in bases:
                forms[pos, base.replace("_", " ")].add(inflection.replace("_", " "))
    return forms


class LearnerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)

    word: str = Field(min_length=1, max_length=140)
    sense_id: str = Field(min_length=1, max_length=100)
    pos: PartOfSpeech
    simple_definition: str | None = Field(max_length=500)
    example: str | None = Field(max_length=500)
    difficulty: Literal["A1", "A2", "B1", "B2", "C1", "C2", "unknown"]
    generation_status: Literal["generated", "needs_review"]
    semantic_check: Literal["supported", "uncertain", "mismatch"]
    reason: str = Field(max_length=500)

    @model_validator(mode="after")
    def required_text(self) -> Self:
        if self.generation_status == "generated" and not (
            self.simple_definition and self.example
        ):
            raise ValueError("Generated results require a definition and example")
        if (
            self.generation_status == "needs_review"
            or self.semantic_check != "supported"
        ) and not self.reason:
            raise ValueError("A review reason is required")
        return self


def language_words(text: str) -> list[str]:
    return WORDS.findall(text.lower().replace("’", "'"))


def root(word: str) -> str:
    # Conservative suffix heuristics. Documented exceptions supplement this check.
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def overlap(text: str, target: str, alternatives: set[str]) -> bool:
    tokens = language_words(text)
    for form in alternatives | {target}:
        base = language_words(form)
        if not base:
            continue
        for index in range(len(tokens) - len(base) + 1):
            actual = tokens[index : index + len(base)]
            if all(
                a == b
                or root(a) == root(b)
                or (a != b and root(a) in {b, b.removesuffix("e"), b + b[-1]})
                for a, b in zip(actual, base, strict=True)
            ):
                return True
    return False


def inspect_output(
    output: LearnerOutput,
    source: dict,
    forms: set[str],
    vocabulary: set[str],
    definition_max: int,
    example_max: int,
) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    if (output.word, output.sense_id, output.pos) != (
        source["word"],
        source["sense_id"],
        source["pos"],
    ):
        errors.append("SOURCE_IDENTITY_MISMATCH")
    if not output.simple_definition or not output.example:
        return errors + ["MISSING_LEARNER_TEXT"], warnings
    definition, example = output.simple_definition, output.example
    for value in (definition, example):
        if FOREIGN.search(value) or any(
            unicodedata.category(char) == "Cc" for char in value
        ):
            errors.append("NON_ENGLISH_OR_CONTROL")
            break
    if "<" in definition + example or ">" in definition + example:
        errors.append("MARKUP")
    words = language_words(definition)
    if not 4 <= len(words) <= definition_max:
        errors.append("DEFINITION_LENGTH")
    elif not 8 <= len(words) <= 20:
        warnings.append("DEFINITION_OUTSIDE_PREFERRED_LENGTH")
    if not 4 <= len(language_words(example)) <= example_max:
        errors.append("EXAMPLE_LENGTH")
    if overlap(definition, source["word"], forms):
        errors.append("LEMMA_LEAK")
    if not overlap(example, source["word"], forms):
        errors.append("EXAMPLE_TARGET_MISSING")
    canonical = " ".join(language_words(example))
    if canonical in {
        " ".join(language_words(item)) for item in source["original_examples"]
    }:
        errors.append("SOURCE_EXAMPLE_REUSED")
    if output.semantic_check == "mismatch":
        errors.append("SENSE_DRIFT_SUSPECTED")
    elif output.semantic_check != "supported":
        warnings.append("SENSE_SEMANTICS_UNCERTAIN")
    if output.difficulty in DIFFICULTIES[3:]:
        warnings.append("DIFFICULTY_ABOVE_B1")
    if (
        words
        and vocabulary
        and sum(
            word not in vocabulary and root(word) not in vocabulary for word in words
        )
        / len(words)
        > 0.35
    ):
        warnings.append("LOW_BASIC_VOCABULARY_COVERAGE")
    return errors, warnings
