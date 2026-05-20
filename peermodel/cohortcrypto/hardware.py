"""Hardware token operations for CohortCrypto.

This module re-exports from the parent cohortcrypto.hardware to provide
proper Python module discovery for peermodel.cohortcrypto.hardware imports.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional

# Add parent directory to path to find cohortcrypto
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import hardware module from parent
from cohortcrypto.hardware import (  # noqa: E402, F401
    enumerate_tokens,
    open_token,
    credential_from_token,
    generate_keys_on_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot
)

__all__ = [
    'enumerate_tokens',
    'open_token',
    'credential_from_token',
    'generate_keys_on_token',
    'TokenInfo',
    'MockTokenSession',
    'PIVSlot',
    'TokenSession',
    'KeyInfo'
]


@dataclass
class KeyInfo:
    """Information about a cryptographic key on a hardware token.

    Attributes:
        algorithm: The cryptographic algorithm (e.g., 'ed25519', 'x25519', 'p256')
        public_key: DER-encoded public key bytes
        certificate: Optional DER-encoded X.509 certificate bytes
        piv_slot: Optional PIV slot identifier (e.g., '9A', '9C')
    """
    algorithm: str
    public_key: bytes
    certificate: Optional[bytes] = None
    piv_slot: Optional[str] = None


@dataclass
class TokenSession:
    """Hardware token session information and capabilities.

    Represents an authenticated session with a hardware token, including
    information about available keys and token capabilities.

    Attributes:
        token_type: Type of token ('piv', 'yubikey', 'pkcs11_generic')
        slot_id: PKCS#11 slot identifier
        signing_key_info: KeyInfo for the signing key
        encryption_key_info: KeyInfo for the encryption key
        supports_x25519: Whether token supports X25519 encryption
        supports_ed25519: Whether token supports Ed25519 signing
        firmware_version: Optional firmware version string
    """
    token_type: str
    slot_id: int
    signing_key_info: KeyInfo
    encryption_key_info: KeyInfo
    supports_x25519: bool
    supports_ed25519: bool
    firmware_version: Optional[str] = None
