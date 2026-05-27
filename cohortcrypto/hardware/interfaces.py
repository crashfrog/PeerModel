"""Hardware token interface abstractions.

This module defines the abstract interfaces for hardware token interaction,
including TokenSession and KeyInfo dataclasses that represent token capabilities
and key information.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class KeyInfo:
    """Information about a key stored on a hardware token.

    Attributes:
        algorithm: Cryptographic algorithm (e.g., 'ed25519', 'x25519', 'p256')
        public_key: DER-encoded public key bytes
        certificate: Optional DER-encoded X.509 certificate
        piv_slot: Optional PIV slot identifier (e.g., '9A', '9C')
    """
    algorithm: str
    public_key: bytes
    certificate: Optional[bytes] = None
    piv_slot: Optional[str] = None


@dataclass
class TokenSession:
    """Session information for a hardware token.

    This dataclass represents the capabilities and metadata of an open
    hardware token session. It includes key information for signing and
    encryption operations.

    Attributes:
        token_type: Type of token (e.g., 'piv', 'yubikey', 'pkcs11_generic')
        slot_id: PKCS#11 slot ID (integer)
        signing_key_info: KeyInfo for the signing/authentication key
        encryption_key_info: KeyInfo for the encryption key
        supports_x25519: Whether token supports X25519 ECDH
        supports_ed25519: Whether token supports Ed25519 signatures
        firmware_version: Optional firmware version string
    """
    token_type: str
    slot_id: int
    signing_key_info: KeyInfo
    encryption_key_info: KeyInfo
    supports_x25519: bool
    supports_ed25519: bool
    firmware_version: Optional[str] = None
