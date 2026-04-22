"""Live / Offline API mode state.

Persists the user's explicit choice in SettingKV so that:
- live  = always attempt real APIs; surface failures honestly in the UI
- offline = force fixture / seeded data only, useful for demos
- auto  = detect based on available API keys (fallback default)

The frontend drives this through GET/POST /api/v2/mode.
"""
from __future__ import annotations

import datetime as dt
import os
from typing import Literal

from sqlalchemy.orm import Session

from app.models.orm import SettingKV

Mode = Literal["live", "offline", "auto"]
MODE_KEY = "api_mode"


def _available_keys() -> dict[str, bool]:
    return {
        "EDGAR_USER_AGENT": bool(os.getenv("EDGAR_USER_AGENT") or os.getenv("EDGAR_API_EMAIL")),
        "NEWS": True,  # Google News RSS needs no key
        "YFINANCE": True,  # yfinance needs no key
        "COMPANIES_HOUSE": bool(os.getenv("COMPANIES_HOUSE_API_KEY")),
        "FRED": bool(os.getenv("FRED_API_KEY")),
    }


def get_mode(db: Session) -> Mode:
    """Return current effective mode (resolves 'auto')."""
    row = db.get(SettingKV, MODE_KEY)
    stored: Mode = (row.value or {}).get("mode", "auto") if row else "auto"
    if stored in ("live", "offline"):
        return stored
    # auto: if essential keys (EDGAR UA) missing, prefer offline
    keys = _available_keys()
    return "live" if keys["EDGAR_USER_AGENT"] else "offline"


def get_raw_mode(db: Session) -> Mode:
    """Return the stored mode *without* auto-resolution."""
    row = db.get(SettingKV, MODE_KEY)
    return (row.value or {}).get("mode", "auto") if row else "auto"


def set_mode(db: Session, mode: Mode) -> Mode:
    if mode not in ("live", "offline", "auto"):
        raise ValueError(f"invalid mode: {mode}")
    row = db.get(SettingKV, MODE_KEY)
    payload = {"mode": mode}
    if row:
        row.value = payload
        row.updated_at = dt.datetime.now(dt.timezone.utc)
    else:
        db.add(SettingKV(key=MODE_KEY, value=payload))
    db.commit()
    return get_mode(db)


def mode_status(db: Session) -> dict:
    stored = get_raw_mode(db)
    effective = get_mode(db)
    return {
        "stored_mode": stored,
        "effective_mode": effective,
        "auto_detected": stored == "auto",
        "available_keys": _available_keys(),
    }
