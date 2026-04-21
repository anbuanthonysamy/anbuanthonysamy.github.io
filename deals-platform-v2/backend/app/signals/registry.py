"""Declarative signal registry.

Signals are defined in signals.yaml and have small code handlers. Each
handler receives a company (and its evidence list) and returns a Signal
row with strength, confidence and evidence refs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from app.models.orm import Company, Evidence


@dataclass
class SignalDef:
    key: str
    module: str
    description: str
    feeds_dimension: str
    evidence_kinds: list[str]
    handler: str  # dotted path


@dataclass
class SignalResult:
    strength: float  # 0..1
    confidence: float  # 0..1
    evidence_ids: list[str]
    detail: dict


HandlerFn = Callable[[Company, list[Evidence]], SignalResult]


def load_signals(path: Path) -> list[SignalDef]:
    data = yaml.safe_load(path.read_text())
    out = []
    for sig in data.get("signals", []):
        out.append(SignalDef(**sig))
    return out


def resolve_handler(dotted: str) -> HandlerFn:
    mod_name, _, fn_name = dotted.rpartition(".")
    import importlib

    mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)
