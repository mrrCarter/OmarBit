import base64
import os

import pytest

os.environ["ENCRYPTION_MASTER_KEY_BASE64"] = base64.b64encode(b"0" * 32).decode()
os.environ["KMS_KEY_ID"] = "key/00000000-0000-0000-0000-000000000000"

from encryption import decrypt_api_key, encrypt_api_key, get_key_id


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-test-key-12345"
    ciphertext = encrypt_api_key(plaintext)
    assert isinstance(ciphertext, bytes)
    assert len(ciphertext) > len(plaintext.encode())
    result = decrypt_api_key(ciphertext)
    assert result == plaintext


def test_different_ciphertexts_for_same_input():
    plaintext = "sk-test-key-12345"
    ct1 = encrypt_api_key(plaintext)
    ct2 = encrypt_api_key(plaintext)
    # Different nonces produce different ciphertexts
    assert ct1 != ct2


def test_get_key_id_returns_valid_format():
    key_id = get_key_id()
    assert key_id.startswith("key/")


def test_decrypt_wrong_key_fails():
    plaintext = "sk-test-key-12345"
    ciphertext = encrypt_api_key(plaintext)
    with pytest.raises(Exception):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        wrong_key = b"1" * 32
        aesgcm = AESGCM(wrong_key)
        nonce = ciphertext[:12]
        ct = ciphertext[12:]
        aesgcm.decrypt(nonce, ct, None)
