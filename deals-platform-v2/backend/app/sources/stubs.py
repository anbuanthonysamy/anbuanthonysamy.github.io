"""Stub source adapters — sources that are documented in source-matrix.md
but not yet implemented. They register themselves in the registry so the
/sources page can clearly show which integrations exist as placeholders
versus which have real adapters that may have fallen back."""
from __future__ import annotations

import datetime as dt

from app.models.enums import DataScope, SourceMode
from app.sources.base import RawItem, Source


class _StubSource(Source):
    """Base for stub adapters. Always returns mode=STUB with a clear reason."""

    is_stub = True

    def fetch(self, **_: object) -> list[RawItem]:
        now = dt.datetime.now(dt.timezone.utc)
        return [
            RawItem(
                kind="stub_placeholder",
                source_id=self.id,
                title=f"{self.name} — not yet implemented",
                url=self.homepage_url,
                snippet=(
                    "This source is documented in source-matrix.md but the adapter "
                    "is not yet implemented. No live or fixture data is returned."
                ),
                published_at=now,
                scope=self.scope,
                mode=SourceMode.STUB,
                meta={"is_stub": True},
                fallback_reason=f"{self.name} adapter not yet implemented (stub)",
            )
        ]


class GDELT(_StubSource):
    id = "news.gdelt"
    name = "GDELT 2.0 DOC API"
    description = (
        "Global Database of Events, Language, and Tone — a planet-scale news "
        "monitoring service. Free with attribution. Adapter not yet implemented; "
        "currently returns stub placeholder data."
    )
    homepage_url = "https://api.gdeltproject.org/api/v2/doc/doc"


class Stooq(_StubSource):
    id = "market.stooq"
    name = "Stooq EOD CSVs"
    description = (
        "Stooq end-of-day market data CSVs — free backup market data source. "
        "Adapter not yet implemented; would serve as fallback for Yahoo Finance."
    )
    homepage_url = "https://stooq.com/q/d/"


class GLEIF(_StubSource):
    id = "lei.gleif"
    name = "GLEIF LEI"
    description = (
        "Global Legal Entity Identifier Foundation — official LEI registry. "
        "Free CC0 license. Adapter not yet implemented (backlog)."
    )
    homepage_url = "https://www.gleif.org/en/lei-data/gleif-api"


class OpenCorporates(_StubSource):
    id = "corp.opencorporates"
    name = "OpenCorporates"
    description = (
        "OpenCorporates — global company database. Free tier with attribution "
        "(50 req/day). Adapter not yet implemented (backlog)."
    )
    homepage_url = "https://api.opencorporates.com/"


class WorldBank(_StubSource):
    id = "macro.worldbank"
    name = "World Bank Indicators"
    description = (
        "World Bank Indicators API — country-level macroeconomic indicators. "
        "Free, CC-BY licensed. Adapter not yet implemented (backlog for sector lens)."
    )
    homepage_url = "https://api.worldbank.org/v2/"
