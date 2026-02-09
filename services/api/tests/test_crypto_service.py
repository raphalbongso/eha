"""Unit tests for the crypto service (libsodium encryption)."""

import base64

import nacl.utils
import pytest

from app.config import Settings
from app.services.crypto_service import CryptoService


@pytest.fixture
def encryption_key() -> str:
    """Generate a valid base64-encoded 32-byte key."""
    key = nacl.utils.random(32)
    return base64.b64encode(key).decode()


@pytest.fixture
def settings(encryption_key):
    return Settings(
        app_env="development",
        encryption_key=encryption_key,
        database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
    )


@pytest.fixture
def crypto(settings):
    return CryptoService(settings)


class TestEncryptDecrypt:
    def test_roundtrip(self, crypto):
        plaintext = "my-secret-token-12345"
        ciphertext = crypto.encrypt(plaintext)
        decrypted = crypto.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_ciphertext_differs_from_plaintext(self, crypto):
        plaintext = "visible-text"
        ciphertext = crypto.encrypt(plaintext)
        assert plaintext.encode() not in ciphertext

    def test_different_encryptions_produce_different_ciphertext(self, crypto):
        plaintext = "same-text"
        ct1 = crypto.encrypt(plaintext)
        ct2 = crypto.encrypt(plaintext)
        assert ct1 != ct2  # NaCl SecretBox uses random nonces

    def test_empty_string(self, crypto):
        ciphertext = crypto.encrypt("")
        assert crypto.decrypt(ciphertext) == ""

    def test_unicode(self, crypto):
        plaintext = "Hello 世界 🌍"
        ciphertext = crypto.encrypt(plaintext)
        assert crypto.decrypt(ciphertext) == plaintext

    def test_long_string(self, crypto):
        plaintext = "x" * 10000
        ciphertext = crypto.encrypt(plaintext)
        assert crypto.decrypt(ciphertext) == plaintext


class TestDecryptionFailure:
    def test_tampered_ciphertext_raises(self, crypto):
        ciphertext = crypto.encrypt("secret")
        tampered = bytearray(ciphertext)
        tampered[-1] ^= 0xFF
        with pytest.raises(Exception):
            crypto.decrypt(bytes(tampered))

    def test_wrong_key_raises(self, encryption_key):
        settings1 = Settings(
            app_env="development",
            encryption_key=encryption_key,
            database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        )
        other_key = base64.b64encode(nacl.utils.random(32)).decode()
        settings2 = Settings(
            app_env="development",
            encryption_key=other_key,
            database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        )
        crypto1 = CryptoService(settings1)
        crypto2 = CryptoService(settings2)

        ciphertext = crypto1.encrypt("secret")
        with pytest.raises(Exception):
            crypto2.decrypt(ciphertext)


class TestDevKeyFallback:
    def test_no_key_uses_dev_fallback(self):
        settings = Settings(
            app_env="development",
            encryption_key="",
            database_url="postgresql+asyncpg://test:test@localhost:5432/eha_test",
        )
        crypto = CryptoService(settings)
        ciphertext = crypto.encrypt("test")
        assert crypto.decrypt(ciphertext) == "test"
