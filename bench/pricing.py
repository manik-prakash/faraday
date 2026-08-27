from __future__ import annotations

MODEL_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-haiku-4": {"input": 0.80, "output": 4.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "llama-mock": {"input": 0.00, "output": 0.00},
}

_PREFIX_ORDER = sorted(MODEL_PRICES.items(), key=lambda kv: -len(kv[0]))


def resolve_price(model: str) -> dict[str, float] | None:
    model = (model or "").strip().lower()
    if not model:
        return None
    if model in MODEL_PRICES:
        return MODEL_PRICES[model]
    for prefix, price in _PREFIX_ORDER:
        if model.startswith(prefix):
            return price
    return None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = resolve_price(model)
    if price is None:
        return None
    cost = (
        input_tokens / 1_000_000 * price["input"]
        + output_tokens / 1_000_000 * price["output"]
    )
    return round(cost, 6)
