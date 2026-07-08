"""
crypto.py — AES-256-GCM Encryption Layer
==========================================
Provides authenticated encryption and decryption of arbitrary byte payloads
using AES-256 in GCM (Galois/Counter Mode).

Why GCM?
  - Confidentiality: AES-256 cipher stream XORed with plaintext.
  - Integrity:       16-byte authentication tag detects any tampering.
  - No padding:      GCM is a stream mode; payload length is preserved exactly.

Wire format of an encrypted blob:
  ┌────────────┬──────────┬────────────────┬──────────────────┐
  │  Salt      │  Nonce   │  Auth Tag      │  Ciphertext      │
  │  16 bytes  │  12 bytes│  16 bytes      │  N bytes         │
  └────────────┴──────────┴────────────────┴──────────────────┘

The salt is used to derive a unique 256-bit AES key from the user-supplied
password via PBKDF2-HMAC-SHA256 (310,000 iterations — NIST recommended 2023).

Dependencies:
    pip install cryptography
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Key-derivation parameters
_SALT_LEN       = 16    # bytes — random per encryption
_NONCE_LEN      = 12    # bytes — random per encryption (96-bit GCM nonce)
_TAG_LEN        = 16    # bytes — GCM authentication tag (fixed)
_KDF_ITERATIONS = 310_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a password and salt using PBKDF2-HMAC-SHA256.

    Args:
        password: User-supplied passphrase (any length).
        salt:     Random 16-byte salt generated at encryption time.

    Returns:
        32-byte (256-bit) AES key.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(data: bytes, password: str) -> bytes:
    """Encrypt a byte payload with AES-256-GCM.

    A fresh random salt and nonce are generated for every call, so encrypting
    the same plaintext twice produces different ciphertext (IND-CPA secure).

    Args:
        data:     Plaintext bytes to encrypt.
        password: Passphrase used to derive the AES key.

    Returns:
        Encrypted blob: salt ‖ nonce ‖ tag ‖ ciphertext.
    """
    salt  = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key   = _derive_key(password, salt)

    aesgcm     = AESGCM(key)
    # AESGCM.encrypt returns ciphertext ‖ tag (tag appended at the end)
    ciphertext = aesgcm.encrypt(nonce, data, associated_data=None)

    return salt + nonce + ciphertext   # tag is already inside ciphertext


def decrypt(blob: bytes, password: str) -> bytes:
    """Decrypt an AES-256-GCM encrypted blob produced by encrypt().

    Args:
        blob:     Encrypted bytes: salt ‖ nonce ‖ tag ‖ ciphertext.
        password: Passphrase used during encryption.

    Returns:
        Original plaintext bytes.

    Raises:
        cryptography.exceptions.InvalidTag: If the password is wrong or the
            blob has been tampered with.
    """
    salt       = blob[:_SALT_LEN]
    nonce      = blob[_SALT_LEN : _SALT_LEN + _NONCE_LEN]
    ciphertext = blob[_SALT_LEN + _NONCE_LEN:]   # includes GCM tag

    key    = _derive_key(password, salt)
    aesgcm = AESGCM(key)

    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    message  = b"Secret image payload for steganography."
    password = "hunter2"

    blob      = encrypt(message, password)
    recovered = decrypt(blob, password)

    assert recovered == message, "Round-trip failed!"
    print(f"[+] Encryption OK  — blob size: {len(blob)} bytes")
    print(f"[+] Decryption OK  — recovered: {recovered.decode()}")
