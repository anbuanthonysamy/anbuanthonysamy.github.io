import datetime as dt

from app.models.enums import DataScope, SourceMode
from app.shared.evidence import upsert_evidence


def test_upsert_dedupes_on_hash(db_session):
    kwargs = dict(
        source_id="edgar.submissions",
        scope=DataScope.PUBLIC,
        mode=SourceMode.LIVE,
        kind="filing_8k",
        title="8-K filing X",
        url="http://example.com/x",
        published_at=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
    )
    a = upsert_evidence(db_session, **kwargs)
    b = upsert_evidence(db_session, **kwargs)
    assert a.id == b.id


def test_scope_stored(db_session):
    ev = upsert_evidence(
        db_session,
        source_id="upload.file",
        scope=DataScope.CLIENT,
        mode=SourceMode.LIVE,
        kind="upload.kpi_actual",
        title="uploaded",
        published_at=dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc),
    )
    assert ev.scope == "client"
