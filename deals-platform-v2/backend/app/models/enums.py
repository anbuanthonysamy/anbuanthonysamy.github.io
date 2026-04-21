"""Canonical enums."""
from __future__ import annotations

from enum import Enum


class DataScope(str, Enum):
    """Isolation scope for every Evidence row.

    Public sources produce `public` rows. Uploaded client inputs produce
    `client` rows. CS1/CS2 pipelines may only read `public`. CS3/CS4 read
    both `public` (benchmarks) and `client` (their own uploads).
    """

    PUBLIC = "public"
    CLIENT = "client"


class SourceMode(str, Enum):
    LIVE = "live"
    FIXTURE = "fixture"
    BLOCKED = "blocked"


class Module(str, Enum):
    ORIGINATION = "origination"
    CARVE_OUTS = "carve_outs"
    POST_DEAL = "post_deal"
    WORKING_CAPITAL = "working_capital"


class SituationKind(str, Enum):
    COMPANY = "company"
    SEGMENT = "segment"
    DIVISION = "division"
    ASSET_CLUSTER = "asset_cluster"
    STRATEGIC_REVIEW = "strategic_review"


class ReviewState(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EDITED = "edited"
    APPROVED = "approved"


class CurveShape(str, Enum):
    LINEAR = "linear"
    S_CURVE = "s_curve"
    J_CURVE = "j_curve"


class Tier(str, Enum):
    """Priority tier for situations, module-specific."""

    P1_HOT = "p1_hot"  # CS1: Active catalyst
    P1_READY = "p1_ready"  # CS2: High separation readiness
    P1_AT_RISK = "p1_at_risk"  # CS3: Synergy gap > 25%
    P1_QUICK_WIN = "p1_quick_win"  # CS4: Cash oppy > $50M

    P2_TARGET = "p2_target"  # CS1: Market underperformance/leverage stress
    P2_CANDIDATE = "p2_candidate"  # CS2: Stress signals present
    P2_ON_TRACK = "p2_on_track"  # CS3: Synergy gap 10-25%
    P2_SOLID = "p2_solid"  # CS4: Cash oppy $20-50M

    P3_MONITOR = "p3_monitor"  # Early signals, longer horizon


class TierColour(str, Enum):
    """Colour coding for tiers."""

    RED = "red"  # P1: Urgent action required
    AMBER = "amber"  # P2: Monitor and prepare
    GREEN = "green"  # P3: Early-stage signals


class Geography(str, Enum):
    """Geographic filter for CS1/CS2."""

    WORLDWIDE = "worldwide"
    UK_ONLY = "uk_only"
