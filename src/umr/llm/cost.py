"""Token cost estimates from `price_per_mtok` (spec LLM)."""

from __future__ import annotations

from umr.llm.base import Price

# Defaults when the config gives no cache prices (Claude: reads ~0.1x, 5-minute writes 1.25x the input price).
ANTHROPIC_CACHE_READ_FACTOR = 0.1
ANTHROPIC_CACHE_WRITE_FACTOR = 1.25


def cost_usd(price: Price, *, uncached_input: int, output: int, cache_read: int = 0, cache_write: int = 0,
             cache_read_factor: float = 1.0, cache_write_factor: float = 1.0) -> float:
    """USD cost of one call.

    `uncached_input` are input tokens billed at the full input price. When the config has no
    `cache_read` / `cache_write` price, the input price times the given factor is used.
    """
    read_price = price.cache_read if price.cache_read is not None else price.input * cache_read_factor
    write_price = price.cache_write if price.cache_write is not None else price.input * cache_write_factor
    total = (uncached_input * price.input + output * price.output
             + cache_read * read_price + cache_write * write_price)
    return total / 1_000_000
