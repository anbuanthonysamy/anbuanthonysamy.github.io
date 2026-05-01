"""Source adapter base class."""
from __future__ import annotations

import abc
import datetime as dt
from dataclasses import dataclass

from app.models.enums import DataScope, SourceMode


@dataclass
class RawItem:
    """Normalised unit yielded by every source adapter."""
    kind: str           # e.g. news, filing_8k, xbrl_segment, market
    source_id: str      # source registry id (edgar.submissions, ...)
    title: str
    url: str | None = None
    snippet: str | None = None
    published_at: dt.datetime | None = None
    scope: DataScope = DataScope.PUBLIC
    mode: SourceMode = SourceMode.LIVE
    company_cik: str | None = None
    company_ticker: str | None = None
    company_name: str | None = None
    meta: dict | None = None
    fallback_reason: str | None = None  # populated when mode != LIVE


class Source(abc.ABC):
    id: str
    name: str
    scope: DataScope = DataScope.PUBLIC
    is_stub: bool = False  # True = adapter not implemented, always returns fixtures
    description: str = ""  # human-readable description for UI
    homepage_url: str | None = None  # link to the source's documentation/site

    @abc.abstractmethod
    def fetch(self, **kwargs) -> list[RawItem]: ...

    def health(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "scope": self.scope.value,
            "is_stub": self.is_stub,
            "description": self.description,
            "homepage_url": self.homepage_url,
        }
