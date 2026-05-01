"""FileUpload source — produces client-scope evidence from CSV/XLSX uploads."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

from app.models.enums import DataScope, SourceMode
from app.sources.base import RawItem, Source


class FileUpload(Source):
    id = "upload.file"
    name = "FileUpload"
    scope = DataScope.CLIENT
    is_stub = False
    description = (
        "Client file uploads (CSV/XLSX) — used by CS3 (post-deal) and CS4 (working "
        "capital) for AR, AP, inventory, and KPI data. Always live (user-controlled, "
        "never shared with CS1/CS2 modules)."
    )
    homepage_url = None

    def fetch(self, file_path: str, module: str, kind: str, **_: object) -> list[RawItem]:
        p = Path(file_path)
        df = _read(p)
        now = dt.datetime.now(dt.timezone.utc)
        return [
            RawItem(
                kind=f"upload.{kind}",
                source_id=self.id,
                title=f"Upload: {p.name} ({len(df)} rows, kind={kind})",
                url=None,
                snippet=f"columns={','.join(df.columns[:12])}",
                published_at=now,
                scope=DataScope.CLIENT,
                mode=SourceMode.LIVE,
                meta={"filename": p.name, "rows": int(len(df)), "module": module, "kind": kind},
            )
        ]


def _read(p: Path) -> pd.DataFrame:
    if p.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(p)
    return pd.read_csv(p)
