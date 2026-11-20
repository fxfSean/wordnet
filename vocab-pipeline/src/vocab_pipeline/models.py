from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

PartOfSpeech = Literal["noun", "verb", "adj", "adv"]
TargetLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2", "unknown"]


class SourceRef(BaseModel):
    source_name: str
    source_version: str
    source_id: str
    license_id: str


class CandidateSense(BaseModel):
    sense_id: str
    lemma: str
    pos: PartOfSpeech
    source_definition: str
    source_gloss: str | None = None
    synset_id: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    matched_lemmas: list[str] = Field(default_factory=list)
    match_method: Literal["exact", "morphology"] = "exact"
    match_confidence: Literal["high", "medium", "low"] = "high"
    tag_count: int | None = None
    ranking_score: int | None = None
    is_recommended: bool = False
    review_status: Literal["pending"] = "pending"
    source_examples: list[str] = Field(default_factory=list)
    source: SourceRef
    selection_status: Literal["candidate", "selected", "excluded", "needs_review"]


class GeneratedSense(BaseModel):
    sense_id: str
    simple_definition: str
    example_en: str
    target_level: TargetLevel
    model_id: str
    prompt_version: str
    generation_hash: str
    validation_errors: list[str] = Field(default_factory=list)
    review_status: Literal["pending", "approved", "rejected", "needs_revision"] = "pending"
    reviewer: str | None = None
    reviewed_at: str | None = None


class PublishedSense(BaseModel):
    sense_id: str
    pos: str
    definition_en: str
    example_en: str
    source: SourceRef


class PublishedWord(BaseModel):
    word_id: str
    lemma: str
    senses: list[PublishedSense]
    book_ids: list[str]
    content_version: int


class Status(StrEnum):
    INGESTED = "INGESTED"
    NORMALIZED = "NORMALIZED"
    MATCHED = "MATCHED"
    SELECTED = "SELECTED"
    GENERATED = "GENERATED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    GENERATION_FAILED = "GENERATION_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    REJECTED = "REJECTED"
    BLOCKED_LICENSE = "BLOCKED_LICENSE"


class StateRecord(BaseModel):
    job_id: str
    record_id: str
    input_hash: str
    pipeline_version: str
    status: Status
    attempt_count: int = Field(default=0, ge=0)
    last_error: str | None = None
    updated_at: str
