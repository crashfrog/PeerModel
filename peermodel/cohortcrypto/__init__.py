"""CohortCrypto compatibility layer for peermodel package.

This module re-exports the root-level cohortcrypto package for backwards
compatibility with tests that expect it under the peermodel package.
"""

# Re-export everything from the root cohortcrypto module
from cohortcrypto import *  # noqa: F401, F403
from cohortcrypto import (
    enumerate_tokens,
    open_token,
    credential_from_token,
    generate_keys_on_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot,
    KeyInfo,
    TokenSession,
    MemberCredential,
    CohortCryptoError,
    HardwareError,
    TokenNotFoundError,
    PKCSLibraryNotFoundError,
    PINError,
    HardwareCapabilityError,
    PIVSlotError,
    SlotOccupiedError,
    SessionExpiredError,
    DecryptionError,
    NotAuthorizedError,
)

__all__ = [
    'enumerate_tokens',
    'open_token',
    'credential_from_token',
    'generate_keys_on_token',
    'TokenInfo',
    'MockTokenSession',
    'PIVSlot',
    'KeyInfo',
    'TokenSession',
    'MemberCredential',
    'CohortCryptoError',
    'HardwareError',
    'TokenNotFoundError',
    'PKCSLibraryNotFoundError',
    'PINError',
    'HardwareCapabilityError',
    'PIVSlotError',
    'SlotOccupiedError',
    'SessionExpiredError',
    'DecryptionError',
    'NotAuthorizedError',
]
