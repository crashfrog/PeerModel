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
