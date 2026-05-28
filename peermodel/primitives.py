"""Low-level cryptographic primitives for PeerModel.

Uses only audited, well-maintained libraries (cryptography library).
No custom crypto implementations.
"""

import os
import base64
from dataclasses import dataclass, asdict, fields
from datetime import datetime
from typing import Optional, Type, TypeVar
import cbor2
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519, ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet, InvalidToken
from peermodel.exceptions import (
    DecryptionError,
    KeyGenerationError,
    SignatureVerificationError,
)

T = TypeVar('T')


@dataclass
class MemberCredential:
    """Member identity and cryptographic keys."""

    member_id: str
    x25519_public: bytes
    ed25519_public: bytes
    signing_algorithm: str = "ed25519"
    encryption_algorithm: str = "x25519"
    hardware_backed: bool = False
    certificate_der: Optional[bytes] = None


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
            encryption_algorithm=serialization.NoEncryption(),
        )
        x25519_public_der = x25519_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        ed25519_private_der = ed25519_private.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        ed25519_public_der = ed25519_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return (
            x25519_private_der,
            x25519_public_der,
            ed25519_private_der,
            ed25519_public_der,
        )
    except Exception as e:
        raise KeyGenerationError(f"Failed to generate keypair: {e}")


def generate_software_keypair(algorithm="ed25519"):
    """Generate software keypairs for signing and encryption.

    Args:
        algorithm: Signing algorithm to use ('ed25519' or 'p256')

    Returns:
        tuple: (signing_private, signing_public, encryption_private, encryption_public)
        All keys are DER-encoded as bytes.
        - For 'ed25519': Ed25519 signing keys + X25519 encryption keys
        - For 'p256': P-256 ECDSA signing keys + P-256 ECDH encryption keys

    Raises:
        KeyGenerationError: If keypair generation fails
        ValueError: If algorithm is not supported
    """
    if algorithm not in ("ed25519", "p256"):
        raise ValueError(
            f"Unsupported algorithm: {algorithm}. Must be 'ed25519' or 'p256'"
        )

    try:
        if algorithm == "ed25519":
            # Generate Ed25519 signing keys
            signing_private = ed25519.Ed25519PrivateKey.generate()
            signing_public = signing_private.public_key()

            # Generate X25519 encryption keys
            encryption_private = x25519.X25519PrivateKey.generate()
            encryption_public = encryption_private.public_key()

        elif algorithm == "p256":
            # Generate P-256 signing keys
            signing_private = ec.generate_private_key(ec.SECP256R1())
            signing_public = signing_private.public_key()

            # Generate P-256 encryption keys (separate keypair for ECDH)
            encryption_private = ec.generate_private_key(ec.SECP256R1())
            encryption_public = encryption_private.public_key()

        # Serialize to DER
        signing_private_der = signing_private.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        signing_public_der = signing_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        encryption_private_der = encryption_private.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        encryption_public_der = encryption_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return (
            signing_private_der,
            signing_public_der,
            encryption_private_der,
            encryption_public_der,
        )

    except Exception as e:
        raise KeyGenerationError(f"Failed to generate {algorithm} keypair: {e}")


def _load_x25519_private(private_key_der):
    """Load X25519 private key from DER bytes."""
    return x25519.X25519PrivateKey.from_private_bytes(
        serialization.load_der_private_key(
            private_key_der, password=None
        ).private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def _load_x25519_public(public_key_der):
    """Load X25519 public key from DER bytes."""
    key = serialization.load_der_public_key(public_key_der)
    return x25519.X25519PublicKey.from_public_bytes(
        key.public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
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
    hkdf = HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info)
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
    symmetric_key_bytes = derive_symmetric_key(shared_secret, salt, b"encrypt", 32)
    fernet_key = base64.urlsafe_b64encode(symmetric_key_bytes)

    f = Fernet(fernet_key)
    ciphertext = f.encrypt(plaintext)

    ephemeral_public_der = ephemeral_public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return (ciphertext, salt, b"", ephemeral_public_der)


def decrypt_from_sender(
    ciphertext,
    nonce,
    tag,
    ephemeral_public_key_der,
    recipient_private_key_der,
):
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

        symmetric_key_bytes = derive_symmetric_key(shared_secret, nonce, b"encrypt", 32)
        fernet_key = base64.urlsafe_b64encode(symmetric_key_bytes)
        f = Fernet(fernet_key)
        plaintext = f.decrypt(ciphertext)

        return plaintext
    except (InvalidToken, Exception) as e:
        raise DecryptionError(f"Decryption failed: {e}")


def sign_bytes(message, private_key_der, algorithm="ed25519"):
    """Sign arbitrary bytes with a private key.

    Args:
        message: bytes to sign
        private_key_der: DER-encoded private key
        algorithm: Signing algorithm ('ed25519' or 'p256')

    Returns:
        bytes: Signature
        - Ed25519: 64 bytes (raw format)
        - P-256: DER-encoded ECDSA signature (variable length, typically 70-72 bytes)

    Raises:
        SignatureVerificationError: If signing fails
        ValueError: If algorithm is not supported or key type doesn't match
    """
    if algorithm not in ("ed25519", "p256"):
        raise ValueError(
            f"Unsupported algorithm: {algorithm}. Must be 'ed25519' or 'p256'"
        )

    try:
        private_key = serialization.load_der_private_key(private_key_der, password=None)

        if algorithm == "ed25519":
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                key_type = type(private_key).__name__
                raise ValueError(
                    f"Key type mismatch: expected Ed25519 key for "
                    f"algorithm 'ed25519', got {key_type}"
                )
            signature = private_key.sign(message)

        elif algorithm == "p256":
            if not isinstance(private_key, ec.EllipticCurvePrivateKey):
                key_type = type(private_key).__name__
                raise ValueError(
                    f"Key type mismatch: expected EC key for "
                    f"algorithm 'p256', got {key_type}"
                )
            # Verify it's actually P-256
            if not isinstance(private_key.curve, ec.SECP256R1):
                curve_type = type(private_key.curve).__name__
                raise ValueError(
                    f"Key curve mismatch: expected P-256 (SECP256R1), "
                    f"got {curve_type}"
                )
            # Sign with ECDSA using SHA-256
            signature = private_key.sign(message, ec.ECDSA(hashes.SHA256()))

        return signature

    except ValueError:
        raise
    except Exception as e:
        raise SignatureVerificationError(f"Signing failed: {e}")


def verify_bytes(message, signature, public_key_der, algorithm="ed25519"):
    """Verify a signature using a public key.

    Args:
        message: bytes that were signed
        signature: Signature bytes
        public_key_der: DER-encoded public key
        algorithm: Signing algorithm ('ed25519' or 'p256')

    Returns:
        bool: True if signature is valid, False otherwise
    """
    if algorithm not in ("ed25519", "p256"):
        return False

    try:
        public_key = serialization.load_der_public_key(public_key_der)

        if algorithm == "ed25519":
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                return False
            public_key.verify(signature, message)

        elif algorithm == "p256":
            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                return False
            # Verify it's actually P-256
            if not isinstance(public_key.curve, ec.SECP256R1):
                return False
            # Verify with ECDSA using SHA-256
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))

        return True

    except Exception:
        return False


def _object_to_dict(obj):
    """Convert a dataclass or dict to a canonical dict representation.

    For dataclasses:
    - Converts to dict via asdict()
    - Recursively handles nested dataclasses and lists
    - Handles datetime fields (convert to ISO format string)

    For dicts:
    - Returns as-is (will be sorted by cbor2 encoder)

    For lists:
    - Recursively converts elements
    """
    if isinstance(obj, dict):
        # Recursively convert dict values
        return {k: _object_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        # Recursively convert list elements
        return [_object_to_dict(item) for item in obj]
    elif isinstance(obj, datetime):
        # Convert datetime to ISO format string for canonical representation
        return obj.isoformat()
    elif hasattr(obj, '__dataclass_fields__'):
        # It's a dataclass - convert to dict and recursively handle fields
        obj_dict = asdict(obj)
        return {k: _object_to_dict(v) for k, v in obj_dict.items()}
    else:
        # Return primitives as-is (bytes, str, int, bool, None)
        return obj


def serialize_to_cbor(obj) -> bytes:
    """Serialize an object to canonical CBOR (RFC 7049 section 3.9).

    Supports:
    - Dataclasses (MemberCredential, MembershipProposal, MembershipVote)
    - Dicts with nested structures
    - Lists and nested containers
    - Binary data (bytes)
    - Primitive types (str, int, bool, None)
    - Datetime objects (converted to ISO format strings)

    The output is canonical CBOR: deterministic encoding suitable for signing.
    Same object serialized twice produces identical bytes.

    Args:
        obj: Object to serialize (dataclass, dict, list, or primitive)

    Returns:
        bytes: Canonical CBOR encoding
    """
    # Convert object to canonical dict/list representation
    canonical_obj = _object_to_dict(obj)

    # Encode to CBOR with canonical=True for deterministic output
    return cbor2.dumps(canonical_obj, canonical=True)


def deserialize_from_cbor(data: bytes, target_type: Type[T]) -> T:
    """Deserialize CBOR bytes back to an object.

    Supports:
    - Dataclasses (MemberCredential, MembershipProposal, MembershipVote)
    - Built-in types (dict, list)
    - Nested structures

    For dataclasses:
    - Decodes CBOR to dict first
    - Reconstructs dataclass from dict fields
    - Handles nested dataclass fields recursively
    - Converts ISO format strings back to datetime
    - Preserves None values for optional fields

    Args:
        data: CBOR bytes to deserialize
        target_type: Target type to deserialize into (dataclass or dict)

    Returns:
        Instance of target_type

    Raises:
        ValueError: If deserialization fails
        TypeError: If target_type is not supported
    """
    try:
        # Decode CBOR to dict/list/primitive
        decoded = cbor2.loads(data)

        # If target is dict or list, return directly
        if target_type in (dict, list):
            return decoded

        # If target is a dataclass, reconstruct it
        if hasattr(target_type, '__dataclass_fields__'):
            return _dict_to_dataclass(decoded, target_type)

        # Otherwise return decoded value as-is
        return decoded

    except Exception as e:
        raise ValueError(f"Failed to deserialize CBOR: {e}")


def _dict_to_dataclass(data: dict, target_type: Type[T]) -> T:
    """Reconstruct a dataclass from a dict.

    Handles:
    - Nested dataclass fields (reconstructs recursively)
    - Lists of dataclass objects
    - Datetime fields (converts from ISO format string)
    - Optional fields (preserves None values)
    - Missing fields (uses dataclass defaults)
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict for dataclass, got {type(data)}")

    # Get field info from dataclass
    field_types = {f.name: f.type for f in fields(target_type)}

    # Reconstruct each field
    kwargs = {}
    for field_name, field_type in field_types.items():
        if field_name not in data:
            # Field not in data, skip it (dataclass default will be used)
            continue

        value = data[field_name]

        # Handle None values
        if value is None:
            kwargs[field_name] = None
            continue

        # Handle datetime conversion from ISO string
        if field_type is datetime and isinstance(value, str):
            kwargs[field_name] = datetime.fromisoformat(value)
        # Handle list of dataclasses
        elif hasattr(field_type, '__origin__') and field_type.__origin__ is list:
            # Extract the inner type from List[T]
            inner_type = field_type.__args__[0] if field_type.__args__ else dict
            if isinstance(value, list):
                kwargs[field_name] = [
                    _dict_to_dataclass(item, inner_type) if isinstance(item, dict) and hasattr(inner_type, '__dataclass_fields__')
                    else item
                    for item in value
                ]
            else:
                kwargs[field_name] = value
        # Handle nested dataclass fields
        elif hasattr(field_type, '__dataclass_fields__') and isinstance(value, dict):
            kwargs[field_name] = _dict_to_dataclass(value, field_type)
        # Handle optional/union types
        elif hasattr(field_type, '__origin__') and field_type.__origin__ is type(None):
            kwargs[field_name] = None
        else:
            # Primitive types or unknown - pass through
            kwargs[field_name] = value

    return target_type(**kwargs)


def canonical_cbor_bytes(obj) -> bytes:
    """Serialize an object to canonical CBOR bytes suitable for cryptographic signing.

    This is an alias for serialize_to_cbor() provided for explicit intent
    when the output will be used for signing/verification.

    Args:
        obj: Object to serialize

    Returns:
        bytes: Canonical CBOR encoding (deterministic)
    """
    return serialize_to_cbor(obj)
