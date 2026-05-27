"""Exceptions module for peermodel.cohortcrypto compatibility layer.

Re-exports all exception classes from the root cohortcrypto.exceptions module.
"""

from cohortcrypto.exceptions import (
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
