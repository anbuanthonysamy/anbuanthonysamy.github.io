"""LLM client with two roles (extract, synthesize) and an offline fallback.

Offline mode is the default for CI and demos. Set ANTHROPIC_API_KEY to
switch to live. Every call is logged to the llm_call table with tokens
and cost (0 in offline mode). See ADR-0004.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.orm import LLMCall
from app.shared.hashing import sha256_str

Role = Literal["extract", "synthesize"]


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    offline: bool
    model: str

    def json(self) -> dict:
        try:
            return json.loads(self.text)
        except Exception:
            return {"raw": self.text}


def _offline_extract(prompt: str) -> str:
    """Deterministic extraction. Returns a compact JSON object based on
    keyword hits in the prompt — crude but stable, good for tests."""
    p = prompt.lower()
    hits: dict[str, bool] = {
        "activist_13d": "13d" in p or "activist" in p,
        "strategic_review": "strategic review" in p or "explore options" in p,
        "refi_window": "refinanc" in p or "matur" in p,
        "mgmt_change": "ceo change" in p or "new chief executive" in p or "cfo" in p,
        "breakup": "break up" in p or "break-up" in p or "spin off" in p or "spin-off" in p,
        "covenant": "covenant" in p or "waiver" in p,
        "rating_watch": "rating watch" in p or "downgrade" in p,
        "peer_divestment": "peer divest" in p or "comparable divest" in p,
    }
    return json.dumps({k: bool(v) for k, v in hits.items()})


def _offline_synth(prompt: str) -> str:
    """Deterministic synthesis — template referencing the evidence ids
    mentioned in the prompt. The Explainer ensures those ids exist."""
    lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
    cited = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("evidence:")]
    cited_txt = ", ".join(cited) if cited else "(no evidence cited)"
    return (
        "Offline synthesis. Drivers surfaced from evidence "
        f"[{cited_txt}]. See the evidence side panel for sources. "
        "Human reviewer to confirm before approval."
    )


def chat(
    db: Session,
    role: Role,
    prompt: str,
    system: str | None = None,
    max_tokens: int = 600,
) -> LLMResponse:
    s = get_settings()
    ph = sha256_str((system or "") + "||" + prompt + "||" + role)

    if not s.live_llm:
        text = _offline_extract(prompt) if role == "extract" else _offline_synth(prompt)
        model = f"offline-{role}"
        resp = LLMResponse(text=text, input_tokens=0, output_tokens=0, offline=True, model=model)
    else:
        # Real Anthropic client
        try:
            from anthropic import Anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "anthropic SDK not installed; pip install anthropic or remove ANTHROPIC_API_KEY"
            ) from e

        client = Anthropic(api_key=s.anthropic_api_key)
        model = s.anthropic_model_extract if role == "extract" else s.anthropic_model_synth
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system or "You are a careful analyst. Respond in JSON when asked.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        )
        resp = LLMResponse(
            text=text,
            input_tokens=getattr(msg.usage, "input_tokens", 0),
            output_tokens=getattr(msg.usage, "output_tokens", 0),
            offline=False,
            model=model,
        )

    db.add(
        LLMCall(
            role=role,
            model=resp.model,
            offline=resp.offline,
            prompt_hash=ph,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=0.0 if resp.offline else _estimate_cost(model, resp),
        )
    )
    db.flush()
    return resp


def _estimate_cost(model: str, r: LLMResponse) -> float:
    # Rough placeholder pricing; real numbers can be wired via config later.
    price_in = 0.25 / 1_000_000 if "haiku" in model else 3.00 / 1_000_000
    price_out = 1.25 / 1_000_000 if "haiku" in model else 15.00 / 1_000_000
    return round(r.input_tokens * price_in + r.output_tokens * price_out, 6)
