"""Exceptions for CohortCrypto hardware operations."""


class CohortCryptoError(Exception):
    """Base exception for all CohortCrypto errors."""
    pass


class HardwareError(CohortCryptoError):
    """Base exception for hardware token errors."""
    pass


class TokenNotFoundError(HardwareError):
    """No hardware token found."""
    pass


class PKCSLibraryNotFoundError(HardwareError):
    """PKCS#11 library not found on system."""
    pass


class PINError(HardwareError):
    """Incorrect PIN or PIN required."""
    pass


class HardwareCapabilityError(HardwareError):
    """Token does not support required operation."""
    pass


class PIVSlotError(HardwareError):
    """PIV slot error (empty, wrong type, or occupied)."""
    pass


class SlotOccupiedError(PIVSlotError):
    """Slot already contains a key."""
    pass


class SessionExpiredError(HardwareError):
    """PKCS#11 session invalidated (token removed)."""
    pass


class DecryptionError(CohortCryptoError):
    """Decryption failed."""
    pass


class NotAuthorizedError(CohortCryptoError):
    """Member not authorized for this operation."""
    pass
