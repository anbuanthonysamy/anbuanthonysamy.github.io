"""Hashing helpers used to deduplicate evidence and cache LLM calls."""
from __future__ import annotations

import hashlib


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def evidence_hash(source_id: str, title: str, url: str | None, published_at: str | None) -> str:
    payload = f"{source_id}|{title}|{url or ''}|{published_at or ''}"
    return sha256_str(payload)
