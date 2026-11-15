import pytest

from app.application.network_settings_service import (
    NetworkSettingsError,
    validate_proxy_url,
)


def test_accepts_supported_proxy_schemes() -> None:
    assert validate_proxy_url("socks5h://127.0.0.1:7897") == "socks5h://127.0.0.1:7897"
    assert validate_proxy_url("http://127.0.0.1:7897") == "http://127.0.0.1:7897"
    assert validate_proxy_url("https://proxy.example.com:443") == "https://proxy.example.com:443"
    assert validate_proxy_url("socks5://127.0.0.1:1080") == "socks5://127.0.0.1:1080"


def test_rejects_missing_host() -> None:
    with pytest.raises(NetworkSettingsError):
        validate_proxy_url("socks5h://")


def test_rejects_unsupported_scheme() -> None:
    with pytest.raises(NetworkSettingsError):
        validate_proxy_url("ftp://127.0.0.1:21")


def test_rejects_invalid_port() -> None:
    with pytest.raises(NetworkSettingsError):
        validate_proxy_url("http://127.0.0.1:99999")
