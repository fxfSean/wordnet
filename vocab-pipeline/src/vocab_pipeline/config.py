import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wordnet_version: Literal["3.0"]
    batch_size: int = Field(gt=0)
    concurrency: int = Field(gt=0)
    max_retries: int = Field(ge=0, le=3)
    prompt_version: str = Field(min_length=1)
    definition_max_words: int = Field(ge=4)
    example_max_words: int = Field(ge=4)
    generation_budget_usd: float = Field(ge=0, allow_inf_nan=False)
    temperature: float = Field(default=0, ge=0, le=2)
    books: list[str] = Field(default_factory=list)
    wordnet_recommendation_limit: int = Field(default=3, ge=1)
    wordnet_min_tag_count: int = Field(default=1, ge=1)


class LLMSettings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    api_key: SecretStr | None = None
    base_url: str | None = None
    model: str | None = None
    provider: Literal["deepseek", "openai_compatible"] = "deepseek"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=400, gt=0, le=4096)
    request_timeout: float = Field(default=45, gt=0, allow_inf_nan=False)
    max_retries: int = Field(default=3, ge=0, le=3)
    concurrency: int = Field(default=3, ge=1, le=32)
    requests_per_minute: int = Field(default=30, ge=1, le=10000)
    daily_budget_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    input_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_usd_per_million: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    json_mode: bool = False


def load_pipeline_config(path: Path) -> PipelineConfig:
    return PipelineConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_llm_settings(path: Path = Path(".env")) -> LLMSettings:
    file_values = dotenv_values(path, interpolate=False)
    values = {}
    for field in LLMSettings.model_fields:
        name = f"LLM_{field.upper()}"
        value = os.environ.get(name, file_values.get(name))
        if value:
            values[field] = value
    return LLMSettings.model_validate(values)
