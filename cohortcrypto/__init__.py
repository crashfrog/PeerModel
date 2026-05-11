"""CohortCrypto: Hardware-backed cryptography for PeerModel cohorts."""

from .hardware import (
    enumerate_tokens,
    open_token,
    credential_from_token,
    generate_keys_on_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot
)

from .exceptions import (
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
    NotAuthorizedError
)

from .primitives import MemberCredential

__all__ = [
    'enumerate_tokens',
    'open_token',
    'credential_from_token',
    'generate_keys_on_token',
    'TokenInfo',
    'MockTokenSession',
    'PIVSlot',
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
    'NotAuthorizedError'
]

__version__ = '0.3.0'
