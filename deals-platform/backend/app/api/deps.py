"""API dependencies — session + header-stub reviewer identity."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db import get_session


def reviewer(x_reviewer: Annotated[str | None, Header()] = None) -> str:
    return x_reviewer or "anonymous"


DbSession = Annotated[Session, Depends(get_session)]
Reviewer = Annotated[str, Depends(reviewer)]
