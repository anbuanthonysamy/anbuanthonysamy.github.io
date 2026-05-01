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


class Source(abc.ABC):
    id: str
    name: str
    scope: DataScope = DataScope.PUBLIC

    @abc.abstractmethod
    def fetch(self, **kwargs) -> list[RawItem]: ...

    def health(self) -> dict:
        return {"id": self.id, "name": self.name, "scope": self.scope.value}
