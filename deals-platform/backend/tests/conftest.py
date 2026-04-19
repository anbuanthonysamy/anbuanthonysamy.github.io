"""Shared fixtures — in-memory SQLite DB and FastAPI client."""
from __future__ import annotations

import os

import pytest

# Force offline-safe defaults BEFORE importing app.*
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("FIXTURES_DIR", str(
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent / "fixtures"
))
os.environ.setdefault("UPLOAD_DIR", "/tmp/deals-uploads")


@pytest.fixture()
def db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base import Base
    # ensure models are imported so metadata is populated
    import app.models.orm  # noqa: F401

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(monkeypatch):
    """FastAPI TestClient with a fresh SQLite file DB."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./.pytest.db")
    # Reimport the app with the patched URL
    import importlib

    import app.config
    import app.db
    import app.main

    importlib.reload(app.config)
    importlib.reload(app.db)
    importlib.reload(app.main)
    from fastapi.testclient import TestClient

    with TestClient(app.main.app) as c:
        yield c
