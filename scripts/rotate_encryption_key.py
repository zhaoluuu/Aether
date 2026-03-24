#!/usr/bin/env python3
"""
Rotate encrypted database fields from an old ENCRYPTION_KEY to a new one.

This script never writes plaintext back to the database. It decrypts with the
old key and immediately re-encrypts with the new key.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from collections import Counter
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.models.database import ApiKey, LDAPConfig, OAuthProvider, Provider, ProviderAPIKey, SystemConfig

APP_SALT = hashlib.sha256(b"aether-v1").digest()[:16]
SENSITIVE_CREDENTIAL_FIELDS = frozenset(
    {
        "api_key",
        "password",
        "refresh_token",
        "session_token",
        "session_cookie",
        "token_cookie",
        "auth_cookie",
        "cookie_string",
        "cookie",
    }
)
ENCRYPTED_SYSTEM_CONFIG_KEYS = frozenset({"smtp_password"})


class AetherCipher:
    def __init__(self, key_source: str) -> None:
        self._cipher = Fernet(self._derive_fernet_key(key_source))

    @staticmethod
    def _derive_fernet_key(key_source: str) -> bytes:
        # Keep compatibility with src.core.crypto.CryptoService.
        try:
            key_bytes = key_source.encode()
            Fernet(key_bytes)
            return key_bytes
        except Exception:
            pass

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=APP_SALT,
            iterations=100000,
        )
        derived_key = kdf.derive(key_source.encode())
        return base64.urlsafe_b64encode(derived_key)

    def encrypt(self, plaintext: str) -> str:
        encrypted = self._cipher.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> str:
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = self._cipher.decrypt(encrypted)
        return decrypted.decode()


def rotate_encrypted_text(
    value: str | None,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
) -> tuple[str | None, bool]:
    if not value:
        return value, False

    plaintext = old_cipher.decrypt(value)
    return new_cipher.encrypt(plaintext), True


def rotate_provider_config(
    raw_config: dict[str, Any] | None,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> tuple[dict[str, Any] | None, bool]:
    if not raw_config:
        return raw_config, False

    changed = False
    config = copy.deepcopy(raw_config)
    provider_ops = config.get("provider_ops")
    if not isinstance(provider_ops, dict):
        return raw_config, False

    connector = provider_ops.get("connector")
    if not isinstance(connector, dict):
        return raw_config, False

    credentials = connector.get("credentials")
    if not isinstance(credentials, dict):
        return raw_config, False

    for field in SENSITIVE_CREDENTIAL_FIELDS:
        value = credentials.get(field)
        if not isinstance(value, str) or not value:
            continue
        try:
            plaintext = old_cipher.decrypt(value)
            counters["provider_config.encrypted_fields"] += 1
        except Exception:
            # Some historical imports may have stored plaintext. Normalize them.
            plaintext = value
            counters["provider_config.plaintext_fields"] += 1
        credentials[field] = new_cipher.encrypt(plaintext)
        changed = True

    return config, changed


def rotate_system_config_value(
    item: SystemConfig,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> bool:
    if item.key not in ENCRYPTED_SYSTEM_CONFIG_KEYS:
        return False
    if not isinstance(item.value, str) or not item.value:
        return False

    try:
        plaintext = old_cipher.decrypt(item.value)
        counters["system_config.encrypted"] += 1
    except Exception:
        plaintext = item.value
        counters["system_config.plaintext"] += 1

    item.value = new_cipher.encrypt(plaintext)
    return True


def run(database_url: str, old_key: str, new_key: str) -> Counter[str]:
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    old_cipher = AetherCipher(old_key)
    new_cipher = AetherCipher(new_key)
    counters: Counter[str] = Counter()

    with session_factory() as session:
        _rotate_api_keys(session, old_cipher, new_cipher, counters)
        _rotate_provider_api_keys(session, old_cipher, new_cipher, counters)
        _rotate_ldap(session, old_cipher, new_cipher, counters)
        _rotate_oauth_providers(session, old_cipher, new_cipher, counters)
        _rotate_system_configs(session, old_cipher, new_cipher, counters)
        _rotate_provider_configs(session, old_cipher, new_cipher, counters)
        session.commit()

    return counters


def _rotate_api_keys(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(ApiKey)):
        rotated, changed = rotate_encrypted_text(row.key_encrypted, old_cipher, new_cipher)
        if changed:
            row.key_encrypted = rotated
            counters["api_keys.rows"] += 1


def _rotate_provider_api_keys(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(ProviderAPIKey)):
        row_changed = False
        rotated_api_key, changed = rotate_encrypted_text(row.api_key, old_cipher, new_cipher)
        if changed:
            row.api_key = rotated_api_key or row.api_key
            row_changed = True
            counters["provider_api_keys.api_key"] += 1

        rotated_auth_config, changed = rotate_encrypted_text(row.auth_config, old_cipher, new_cipher)
        if changed:
            row.auth_config = rotated_auth_config
            row_changed = True
            counters["provider_api_keys.auth_config"] += 1

        if row_changed:
            counters["provider_api_keys.rows"] += 1


def _rotate_ldap(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(LDAPConfig)):
        rotated, changed = rotate_encrypted_text(
            row.bind_password_encrypted, old_cipher, new_cipher
        )
        if changed:
            row.bind_password_encrypted = rotated
            counters["ldap.rows"] += 1


def _rotate_oauth_providers(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(OAuthProvider)):
        rotated, changed = rotate_encrypted_text(
            row.client_secret_encrypted, old_cipher, new_cipher
        )
        if changed:
            row.client_secret_encrypted = rotated
            counters["oauth_providers.rows"] += 1


def _rotate_system_configs(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(SystemConfig)):
        if rotate_system_config_value(row, old_cipher, new_cipher, counters):
            counters["system_configs.rows"] += 1


def _rotate_provider_configs(
    session: Session,
    old_cipher: AetherCipher,
    new_cipher: AetherCipher,
    counters: Counter[str],
) -> None:
    for row in session.scalars(select(Provider)):
        rotated, changed = rotate_provider_config(row.config, old_cipher, new_cipher, counters)
        if changed:
            row.config = rotated
            counters["providers.rows"] += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate encrypted Aether database fields.")
    parser.add_argument("--database-url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("--old-key", required=True, help="Current ENCRYPTION_KEY")
    parser.add_argument("--new-key", required=True, help="Replacement ENCRYPTION_KEY")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counters = run(args.database_url, args.old_key, args.new_key)
    print(json.dumps(counters, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
