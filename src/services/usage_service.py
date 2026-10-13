from contextvars import ContextVar
from decimal import Decimal
from typing import Annotated

import tiktoken
from fastapi import Depends, Header
from langchain_core.callbacks import BaseCallbackHandler
from pydantic import BaseModel, Field, field_serializer

from src.config.settings import xsettings
from src.core.exceptions import InsufficientCreditsAPIException

# USD per 1M tokens: (input, cached input, output). Matched by longest model-name prefix, since
# OpenAI reports dated snapshots (e.g. gpt-5.4-mini-2026-03-17). Standard tier; re-check
# https://developers.openai.com/api/docs/pricing when changing models.
PRICES: dict[str, tuple[Decimal, Decimal, Decimal]] = {
    "gpt-5.4-nano": (Decimal("0.20"), Decimal("0.02"), Decimal("1.25")),
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
    "gpt-5.1": (Decimal("1.25"), Decimal("0.125"), Decimal("10.00")),
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0.02"), Decimal("0")),
}
# An unpriced model is charged at the dearest rate rather than silently free.
FALLBACK_PRICE = PRICES["gpt-5.1"]


def price_for(model: str) -> tuple[Decimal, Decimal, Decimal]:
    matches = [prefix for prefix in PRICES if model.startswith(prefix)]
    return PRICES[max(matches, key=len)] if matches else FALLBACK_PRICE


class TokenCount(BaseModel):
    """OpenAI semantics: input_tokens includes cached_input_tokens, output_tokens includes
    reasoning_tokens. total_tokens = input + output + embedding, so sum it, don't re-add parts."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_input_tokens: int = 0
    embedding_tokens: int = 0
    total_tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    credits: Decimal = Decimal(0)
    # credits per bill line (input, cached_input, output, reasoning, embedding); sums to credits
    credits_breakdown: dict[str, Decimal] = Field(default_factory=dict)

    @field_serializer("cost_usd", "credits", when_used="json")
    def _fixed_point(self, value: Decimal, info) -> str:
        # Strings keep exact decimals (no float rounding); credits use the configured precision.
        places = 9 if info.field_name == "cost_usd" else xsettings.CREDIT_DECIMALS
        return f"{value:.{places}f}"

    @field_serializer("credits_breakdown", when_used="json")
    def _breakdown_fixed_point(self, value: dict[str, Decimal]) -> dict[str, str]:
        return {k: f"{v:.{xsettings.CREDIT_DECIMALS}f}" for k, v in value.items()}


class Usage(BaseModel):
    """Tokens spent by one request: grand total plus a per-model split for pricing."""

    total: TokenCount = Field(default_factory=TokenCount)
    by_model: dict[str, TokenCount] = Field(default_factory=dict)

    def add(self, model: str, **counts: int) -> None:
        price_in, price_cached, price_out = price_for(model)
        cached = counts.get("cached_input_tokens", 0)
        reasoning = counts.get("reasoning_tokens", 0)
        # Bill lines in USD. input_tokens includes cached and output_tokens includes reasoning,
        # so each is split out here; reasoning is billed at the output rate.
        lines = {
            "input": (counts.get("input_tokens", 0) - cached) * price_in,
            "cached_input": cached * price_cached,
            "output": (counts.get("output_tokens", 0) - reasoning) * price_out,
            "reasoning": reasoning * price_out,
            "embedding": counts.get("embedding_tokens", 0) * price_in,
        }
        usd_to_credits = xsettings.CREDIT_MARKUP * xsettings.CREDITS_PER_USD
        cost = sum(lines.values()) / 1_000_000
        for bucket in (self.total, self.by_model.setdefault(model, TokenCount())):
            for name, n in counts.items():
                setattr(bucket, name, getattr(bucket, name) + n)
            bucket.cost_usd += cost
            bucket.credits += cost * usd_to_credits
            for line, amount in lines.items():
                bucket.credits_breakdown[line] = (
                    bucket.credits_breakdown.get(line, Decimal(0))
                    + amount / 1_000_000 * usd_to_credits
                )
            bucket.total_tokens += (
                counts.get("input_tokens", 0)
                + counts.get("output_tokens", 0)
                + counts.get("embedding_tokens", 0)
            )


# Set per request by track_usage; None outside a request (scripts, tests) so recording is a no-op.
current_usage: ContextVar[Usage | None] = ContextVar("current_usage", default=None)


async def track_usage(x_credits_balance: Annotated[Decimal | None, Header()] = None) -> Usage:
    """FastAPI dependency: start a fresh Usage for this request and return it to the route.

    The caller owns balances and may send its remaining credits in X-Credits-Balance; a balance
    of zero or less is refused before any LLM call. Without the header nothing is enforced.
    ponytail: only refuses an empty balance (cost isn't known up front), so a small positive
    balance can still be overspent by one request; the caller deducts usage.total.credits.
    """
    if x_credits_balance is not None and x_credits_balance <= 0:
        raise InsufficientCreditsAPIException()
    usage = Usage()
    current_usage.set(usage)
    return usage


TrackedUsage = Annotated[Usage, Depends(track_usage)]


class UsageCallback(BaseCallbackHandler):
    """Records every chat completion's token usage onto the current request's Usage."""

    run_inline = True  # run in the request's context, not an executor thread

    def on_llm_end(self, response, **kwargs) -> None:
        usage = current_usage.get()
        if usage is None:
            return
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                meta = getattr(message, "usage_metadata", None)
                if not meta:
                    continue
                usage.add(
                    message.response_metadata.get("model_name", "unknown"),
                    input_tokens=meta.get("input_tokens", 0),
                    output_tokens=meta.get("output_tokens", 0),
                    reasoning_tokens=(meta.get("output_token_details") or {}).get("reasoning", 0),
                    cached_input_tokens=(meta.get("input_token_details") or {}).get(
                        "cache_read", 0
                    ),
                )


def record_embedding_usage(model: str, texts: list[str]) -> None:
    """The embeddings client reports no usage, so count with tiktoken (matches OpenAI's count)."""
    usage = current_usage.get()
    if usage is None:
        return
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    usage.add(model, embedding_tokens=sum(len(encoding.encode(t)) for t in texts))


usage_callback = UsageCallback()
