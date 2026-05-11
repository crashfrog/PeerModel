"""Low-level cryptographic primitives for PeerModel.

Uses only audited, well-maintained libraries (cryptography library).
No custom crypto implementations.
"""

import os
import base64
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet, InvalidToken
from peermodel.exceptions import DecryptionError, KeyGenerationError, SignatureVerificationError


def generate_keypair():
    """Generate X25519 and Ed25519 keypairs for a new identity.

    Returns:
        tuple: (x25519_private_der, x25519_public_der, ed25519_private_der, ed25519_public_der)
        All DER-encoded as bytes.
    """
    try:
        x25519_private = x25519.X25519PrivateKey.generate()
        x25519_public = x25519_private.public_key()

        ed25519_private = ed25519.Ed25519PrivateKey.generate()
        ed25519_public = ed25519_private.public_key()

        x25519_private_der = x25519_private.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        x25519_public_der = x25519_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        ed25519_private_der = ed25519_private.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        ed25519_public_der = ed25519_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return (x25519_private_der, x25519_public_der, ed25519_private_der, ed25519_public_der)
    except Exception as e:
        raise KeyGenerationError(f"Failed to generate keypair: {e}")


def _load_x25519_private(private_key_der):
    """Load X25519 private key from DER bytes."""
    return x25519.X25519PrivateKey.from_private_bytes(
        serialization.load_der_private_key(private_key_der, password=None).private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    )


def _load_x25519_public(public_key_der):
    """Load X25519 public key from DER bytes."""
    key = serialization.load_der_public_key(public_key_der)
    return x25519.X25519PublicKey.from_public_bytes(
        key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    )


def _load_ed25519_private(private_key_der):
    """Load Ed25519 private key from DER bytes."""
    return serialization.load_der_private_key(private_key_der, password=None)


def _load_ed25519_public(public_key_der):
    """Load Ed25519 public key from DER bytes."""
    return serialization.load_der_public_key(public_key_der)


def derive_symmetric_key(shared_secret, salt, info, length=32):
    """Derive a symmetric key from a shared secret using HKDF-SHA256.

    Args:
        shared_secret: Bytes from ECDH key agreement
        salt: Random salt bytes
        info: Context-specific info bytes
        length: Output key length (default 32 for AES-256)

    Returns:
        bytes: Derived key
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info
    )
    return hkdf.derive(shared_secret)


def encrypt_to_recipient(plaintext, recipient_public_key_der):
    """Encrypt plaintext to a recipient's X25519 public key.

    Uses ephemeral X25519 keypair + HKDF + Fernet (AES-128-CBC + HMAC-SHA256).

    Args:
        plaintext: bytes to encrypt
        recipient_public_key_der: DER-encoded X25519 public key

    Returns:
        tuple: (ciphertext, salt, tag, ephemeral_public_key_der)
        - ciphertext: Fernet token encrypted with derived key
        - salt: Random salt used for HKDF (needed for decryption)
        - tag: Empty bytes (Fernet includes GCM-like authentication)
        - ephemeral_public_key_der: DER-encoded ephemeral X25519 public key

    Note: Symmetric encryption key is derived from ECDH shared secret via HKDF-SHA256.
          This enables decryption with only recipient private key + ephemeral public key.
    """
    ephemeral_private = x25519.X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key()

    recipient_public = _load_x25519_public(recipient_public_key_der)
    shared_secret = ephemeral_private.exchange(recipient_public)

    salt = os.urandom(16)
    symmetric_key_bytes = derive_symmetric_key(shared_secret, salt, b'encrypt', 32)
    fernet_key = base64.urlsafe_b64encode(symmetric_key_bytes)

    f = Fernet(fernet_key)
    ciphertext = f.encrypt(plaintext)

    ephemeral_public_der = ephemeral_public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return (ciphertext, salt, b'', ephemeral_public_der)


def decrypt_from_sender(ciphertext, nonce, tag, ephemeral_public_key_der, recipient_private_key_der):
    """Decrypt ciphertext from sender's ephemeral key.

    Performs ECDH with sender's ephemeral public key to recover shared secret,
    derives the symmetric key using HKDF, then decrypts using Fernet.

    Args:
        ciphertext: Fernet token (from encrypt_to_recipient)
        nonce: Salt bytes used for HKDF (from encrypt_to_recipient)
        tag: Empty bytes (ignored - Fernet has built-in authentication)
        ephemeral_public_key_der: DER-encoded ephemeral X25519 public key
        recipient_private_key_der: DER-encoded recipient X25519 private key

    Returns:
        bytes: Decrypted plaintext

    Raises:
        DecryptionError: If decryption fails
    """
    try:
        recipient_private = _load_x25519_private(recipient_private_key_der)
        ephemeral_public = _load_x25519_public(ephemeral_public_key_der)
        shared_secret = recipient_private.exchange(ephemeral_public)

        symmetric_key_bytes = derive_symmetric_key(shared_secret, nonce, b'encrypt', 32)
        fernet_key = base64.urlsafe_b64encode(symmetric_key_bytes)
        f = Fernet(fernet_key)
        plaintext = f.decrypt(ciphertext)

        return plaintext
    except (InvalidToken, Exception) as e:
        raise DecryptionError(f"Decryption failed: {e}")


def sign_bytes(message, ed25519_private_key_der):
    """Sign arbitrary bytes with Ed25519 private key.

    Args:
        message: bytes to sign
        ed25519_private_key_der: DER-encoded Ed25519 private key

    Returns:
        bytes: Ed25519 signature (64 bytes)

    Raises:
        SignatureVerificationError: If signing fails
    """
    try:
        private_key = _load_ed25519_private(ed25519_private_key_der)
        signature = private_key.sign(message)
        return signature
    except Exception as e:
        raise SignatureVerificationError(f"Signing failed: {e}")


def verify_bytes(message, signature, ed25519_public_key_der):
    """Verify a signature using Ed25519 public key.

    Args:
        message: bytes that were signed
        signature: Ed25519 signature (64 bytes)
        ed25519_public_key_der: DER-encoded Ed25519 public key

    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        public_key = _load_ed25519_public(ed25519_public_key_der)
        public_key.verify(signature, message)
        return True
    except Exception:
        return False
