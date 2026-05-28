"""Cryptographic exception hierarchy for PeerModel."""


class PeerModelCryptoError(Exception):
    """Base exception for cryptographic operations."""
    pass


class DecryptionError(PeerModelCryptoError):
    """Raised when decryption fails (bad tag, invalid ciphertext, etc.)."""
    pass


class UnauthorizedAccess(PeerModelCryptoError):
    """Raised when attempting to decrypt with missing keys."""
    def __init__(self, message, encryptor_signature=None):
        super().__init__(message)
        self.encryptor_signature = encryptor_signature


class KeyGenerationError(PeerModelCryptoError):
    """Raised when keypair generation fails."""
    pass


class SignatureVerificationError(PeerModelCryptoError):
    """Raised when signature verification fails."""
    pass


class SchemaMismatchError(Exception):
    """Raised when SQLite schema doesn't match expected model schema."""
    pass


class LogIntegrityError(Exception):
    """Raised when operation log is corrupted or has integrity issues.

    This error indicates serious problems with the operation log such as:
    - Missing CIDs that cannot be fetched after retries
    - Non-contiguous sequence numbers (gaps in the chain)
    - More than 10% of operations with invalid signatures
    """
    pass
