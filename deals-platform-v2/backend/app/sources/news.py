"""Google News RSS adapter — public RSS only, no article body fetch."""
from __future__ import annotations

import datetime as dt
import json
import logging
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

try:
    import feedparser  # type: ignore
except Exception:  # pragma: no cover
    feedparser = None  # type: ignore

from app.config import get_settings
from app.models.enums import DataScope, SourceMode
from app.sources.base import RawItem, Source

log = logging.getLogger(__name__)


class GoogleNewsRSS(Source):
    id = "news.google_rss"
    name = "Google News RSS"
    scope = DataScope.PUBLIC

    def fetch(self, query: str, limit: int = 30, **_: object) -> list[RawItem]:
        s = get_settings()
        url = (
            "https://news.google.com/rss/search?q="
            f"{httpx.QueryParams({'q': query})['q']}&hl=en-US&gl=US&ceid=US:en"
        )
        mode = SourceMode.LIVE
        try:
            if feedparser is None:
                raise RuntimeError("feedparser not installed")
            with httpx.Client(timeout=10, follow_redirects=True) as cli:
                resp = cli.get(url, headers={"User-Agent": "DealsPlatformPoC/0.1"})
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
                entries = feed.entries[:limit]
                if not entries:
                    raise RuntimeError("empty feed")
        except Exception as e:
            log.warning("google news live fetch failed (%s): fallback fixture", e)
            fx = _load_fixture(s.fixtures_dir, "news_google.json")
            entries = [
                _DictEntry(**d)
                for d in fx.get("entries", [])
                if query.lower() in d.get("title", "").lower()
                or query.lower() in d.get("summary", "").lower()
            ]
            mode = SourceMode.FIXTURE

        out: list[RawItem] = []
        for e in entries[:limit]:
            title = getattr(e, "title", None) or ""
            link = getattr(e, "link", None)
            summary = getattr(e, "summary", None) or ""
            pub = None
            raw_date = getattr(e, "published", None) or getattr(e, "updated", None)
            if raw_date:
                try:
                    pub = parsedate_to_datetime(raw_date)
                except Exception:
                    pub = None
            out.append(
                RawItem(
                    kind="news",
                    source_id=self.id,
                    title=title,
                    url=link,
                    snippet=summary[:1000],
                    published_at=pub,
                    scope=DataScope.PUBLIC,
                    mode=mode,
                    company_name=None,
                    meta={"query": query},
                )
            )
        return out


class _DictEntry(dict):
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError as ex:
            raise AttributeError(k) from ex


def _load_fixture(dirpath: str, name: str) -> dict:
    p = Path(dirpath) / name
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}
