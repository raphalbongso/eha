"""Token encryption service using libsodium (PyNaCl)."""

import base64
import logging

import nacl.secret
import nacl.utils

from app.config import Settings

logger = logging.getLogger(__name__)


class CryptoService:
    """Symmetric encryption using NaCl SecretBox (XSalsa20-Poly1305).

    In production, the encryption key should be fetched from a KMS
    (e.g., AWS KMS, GCP KMS) and rotated periodically.
    """

    def __init__(self, settings: Settings) -> None:
        key_b64 = settings.encryption_key.get_secret_value()
        if not key_b64:
            # Generate a deterministic dev key (NOT for production)
            logger.warning("No encryption key configured; using dev key. DO NOT use in production.")
            self._key = nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)
        else:
            self._key = base64.b64decode(key_b64)
        self._box = nacl.secret.SecretBox(self._key)

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a string and return ciphertext bytes (nonce prepended)."""
        return self._box.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext bytes and return the original string."""
        return self._box.decrypt(ciphertext).decode("utf-8")


_crypto_service: CryptoService | None = None


def get_crypto_service(settings: Settings) -> CryptoService:
    global _crypto_service
    if _crypto_service is None:
        _crypto_service = CryptoService(settings)
    return _crypto_service
