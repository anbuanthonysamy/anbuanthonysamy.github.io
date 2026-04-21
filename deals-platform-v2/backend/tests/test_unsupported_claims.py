import datetime as dt

import pytest

from app.explain.unsupported_claims import UnsupportedClaimsError, check_situation
from app.models.enums import DataScope, SourceMode
from app.shared.evidence import upsert_evidence


def test_passes_when_evidence_exists(db_session):
    ev = upsert_evidence(
        db_session, source_id="x", scope=DataScope.PUBLIC, mode=SourceMode.LIVE,
        kind="news", title="t",
        published_at=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
    )
    check_situation(db_session, {"evidence_ids": [ev.id], "explanation_cites": [ev.id]})


def test_rejects_unknown_ids(db_session):
    with pytest.raises(UnsupportedClaimsError):
        check_situation(db_session, {"evidence_ids": ["nope"], "explanation_cites": []})
