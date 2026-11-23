"""Model prices, to turn token counts into dollars.

Prices are USD per million tokens. Update this table when prices change.
Cache writes cost 1.25x the input price (only used once we add prompt caching).
"""

# model: (input, output, cache_read)
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 20.00, 0.40),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float | None:
    """Dollar cost of one call, or None if the model is not in the table."""
    if model not in PRICES:
        return None
    input_price, output_price, cache_read_price = PRICES[model]
    total = (
        input_tokens * input_price
        + cache_write_tokens * input_price * 1.25
        + cache_read_tokens * cache_read_price
        + output_tokens * output_price  # includes thinking tokens
    )
    return total / 1_000_000
