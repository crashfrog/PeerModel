"""Exceptions for CohortCrypto hardware operations.

This module re-exports from the parent cohortcrypto.exceptions to provide
proper Python module discovery for peermodel.cohortcrypto.exceptions imports.
"""

import os
import sys

# Add parent directory to path to find cohortcrypto
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import exceptions from parent
from cohortcrypto.exceptions import (  # noqa: E402, F401
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

__all__ = [
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
