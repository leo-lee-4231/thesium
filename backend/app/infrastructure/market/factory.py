from app.infrastructure.market.okx import OKXProvider

_provider: OKXProvider | None = None


def get_provider() -> OKXProvider:
    """Process-wide public OKX provider (no API key)."""

    global _provider
    if _provider is None:
        _provider = OKXProvider()
    return _provider
