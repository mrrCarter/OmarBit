import base64
import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_master_key() -> bytes:
    # Read at call time so tests can override via os.environ.
    raw = os.environ.get("ENCRYPTION_MASTER_KEY_BASE64", "")
    if not raw:
        raise RuntimeError("ENCRYPTION_MASTER_KEY_BASE64 not set")
    key = base64.b64decode(raw, validate=True)
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_MASTER_KEY_BASE64 must decode to exactly 32 bytes")
    return key


def get_key_id() -> str:
    key_id = os.environ.get("KMS_KEY_ID", "local-dev-key")
    if key_id == "local-dev-key":
        return f"key/{uuid.uuid5(uuid.NAMESPACE_DNS, 'omarbit-local-dev')}"
    return key_id


def encrypt_api_key(plaintext: str) -> bytes:
    master_key = _get_master_key()
    aesgcm = AESGCM(master_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Store as nonce || ciphertext
    return nonce + ciphertext


def decrypt_api_key(ciphertext_blob: bytes) -> str:
    master_key = _get_master_key()
    nonce = ciphertext_blob[:12]
    ciphertext = ciphertext_blob[12:]
    aesgcm = AESGCM(master_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
