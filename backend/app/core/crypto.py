import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class SecretError(Exception):
    pass


def _secret_path() -> Path:
    settings = get_settings()
    path = Path(settings.secret_key_file)
    if not path.is_absolute():
        if path.name == ".thesium-secret":
            # Stable across API/worker working directories: backend root or /app.
            return Path(__file__).resolve().parents[2] / path
        path = Path.cwd() / path
    return path


def _load_key() -> bytes:
    settings = get_settings()
    if settings.secret_key:
        return settings.secret_key.encode()
    path = _secret_path()
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.write_bytes(key)
    os.chmod(path, 0o600)
    return key


def encrypt_secret(value: str) -> bytes:
    return Fernet(_load_key()).encrypt(value.encode())


def decrypt_secret(value: bytes) -> str:
    try:
        return Fernet(_load_key()).decrypt(value).decode()
    except (InvalidToken, ValueError) as exc:
        raise SecretError("cannot decrypt stored API key; re-enter it") from exc
