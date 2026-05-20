"""CohortCrypto: Hardware-backed cryptography for PeerModel cohorts.

This module re-exports from the parent cohortcrypto package to provide
proper Python module discovery for peermodel.cohortcrypto imports.
"""

import os
import sys

# Add parent directory to path to find cohortcrypto
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Re-export everything from parent
from cohortcrypto import (  # noqa: E402, F401
    enumerate_tokens,
    open_token,
    credential_from_token,
    generate_keys_on_token,
    TokenInfo,
    MockTokenSession,
    PIVSlot,
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
    NotAuthorizedError
)

# Also make hardware submodule accessible
from cohortcrypto import hardware  # noqa: E402, F401

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
    'NotAuthorizedError',
    'hardware'
]

__version__ = '0.3.0'
