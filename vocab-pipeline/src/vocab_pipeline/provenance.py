from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, StrictBool

from .models import Status


class SourceLicense(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["allowed", "blocked"] = "blocked"
    source_name: str = ""
    source_version: str = ""
    url: str = ""
    acquired_at: date | None = None
    license_id: str = ""
    license_name: str = ""
    license_text: str = ""
    commercial_use: StrictBool | None = None
    modification: StrictBool | None = None
    redistribution: StrictBool | None = None
    cloud_storage: StrictBool | None = None
    attribution_required: StrictBool | None = None
    reviewer: str = ""
    reviewed_at: date | None = None

    def allows_use(self, registry: Path) -> bool:
        return (
            self.status == "allowed"
            and all(
                (
                    self.source_name,
                    self.source_version,
                    self.url,
                    self.acquired_at,
                    self.license_id,
                    self.license_name,
                    self.license_text,
                    self.reviewer,
                    self.reviewed_at,
                )
            )
            and all(
                value is True
                for value in (
                    self.commercial_use,
                    self.modification,
                    self.redistribution,
                    self.cloud_storage,
                )
            )
            and self.attribution_required is not None
            and (registry.parent / self.license_text).is_file()
        )


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wordlists: dict[str, SourceLicense] = {}
    wordnet: SourceLicense = SourceLicense()


def load_registry(path: Path) -> SourceRegistry:
    if not path.exists():
        return SourceRegistry()
    return SourceRegistry.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def ingest_status(source: SourceLicense | None, path: Path) -> Status:
    return (
        Status.INGESTED
        if source and source.allows_use(path)
        else Status.BLOCKED_LICENSE
    )
