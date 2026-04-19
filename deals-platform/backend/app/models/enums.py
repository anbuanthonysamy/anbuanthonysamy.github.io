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
