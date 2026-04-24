"""Source registry."""
from __future__ import annotations

from app.sources.base import Source
from app.sources.companies_house import CompaniesHouse
from app.sources.edgar import EdgarCompanyFacts, EdgarSubmissions
from app.sources.edgar_structured import EdgarSegmentFacts
from app.sources.file_upload import FileUpload
from app.sources.fred import FRED
from app.sources.market import YFinanceMarket
from app.sources.news import GoogleNewsRSS

ALL_SOURCES: list[Source] = [
    EdgarSubmissions(),
    EdgarCompanyFacts(),
    EdgarSegmentFacts(),
    GoogleNewsRSS(),
    YFinanceMarket(),
    FRED(),
    CompaniesHouse(),
    FileUpload(),
]

BY_ID: dict[str, Source] = {s.id: s for s in ALL_SOURCES}
