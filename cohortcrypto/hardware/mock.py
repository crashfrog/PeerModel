"""Mock hardware token session for testing without real hardware."""

from dataclasses import dataclass
from typing import Optional
from enum import Enum

import peermodel.primitives as primitives
from ..exceptions import PINError


class PIVSlot(Enum):
    """PIV card slot identifiers."""
    AUTO = "auto"
    SLOT_9A = "9A"
    SLOT_9C = "9C"
    SLOT_9D = "9D"
    SLOT_9E = "9E"


@dataclass
class TokenInfo:
    """Information about a detected hardware token."""
    slot_id: int
    token_label: str
    token_serial: str
    manufacturer: str


@dataclass
class MockTokenSession:
    """Mock token session for testing without hardware.

    Simulates a hardware token by storing keypairs in memory
    but implementing the same API as TokenSession.
    """
    slot_id: int
    token_label: str
    token_serial: str
    piv_slot: PIVSlot

    # Public keys (exposed)
    x25519_public: bytes
    ed25519_public: bytes

    # Private keys (retained but never exposed - simulates hardware)
    _x25519_private: bytes
    _ed25519_private: bytes

    # Algorithm fields
    signing_algorithm: str = "ed25519"
    encryption_algorithm: str = "x25519"

    # Certificate (optional)
    certificate_der: Optional[bytes] = None

    # Session state
    _authenticated: bool = False
    _closed: bool = False

    @classmethod
    def create(
        cls,
        token_label: str = "Mock PIV Card",
        token_serial: str = "MOCK123456",
        piv_slot: Optional[PIVSlot] = None,
        slot_id: int = 0
    ):
        """Create a mock token with fresh keypairs.

        Args:
            token_label: Token display name
            token_serial: Token serial number
            piv_slot: PIV slot to use (defaults to SLOT_9A)
            slot_id: PKCS#11 slot ID

        Returns:
            MockTokenSession instance with valid keypairs
        """
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = primitives.generate_keypair()

        return cls(
            slot_id=slot_id,
            token_label=token_label,
            token_serial=token_serial,
            piv_slot=piv_slot or PIVSlot.SLOT_9A,
            x25519_public=x25519_pub,
            ed25519_public=ed25519_pub,
            _x25519_private=x25519_priv,
            _ed25519_private=ed25519_priv
        )

    def authenticate(self, pin: str) -> None:
        """Authenticate with PIN.

        Args:
            pin: Token PIN (default test PIN is "123456")

        Raises:
            PINError: If PIN is incorrect
        """
        if pin != "123456":
            raise PINError(f"Incorrect PIN")
        self._authenticated = True

    def sign(self, message: bytes) -> bytes:
        """Sign message with private key (simulates on-token signing).

        Args:
            message: Message to sign

        Returns:
            Ed25519 signature (64 bytes)
        """
        if not self._authenticated:
            raise RuntimeError("Session not authenticated")
        return primitives.sign_bytes(message, self._ed25519_private)

    def ecdh(self, peer_public_key_der: bytes) -> bytes:
        """Perform ECDH (simulates on-token key agreement).

        Args:
            peer_public_key_der: Peer's DER-encoded X25519 public key

        Returns:
            Shared secret bytes (32 bytes for X25519)
        """
        if not self._authenticated:
            raise RuntimeError("Session not authenticated")

        # Use cryptography library to perform ECDH
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives.serialization import load_der_public_key

        # Load peer public key
        peer_public = load_der_public_key(peer_public_key_der)

        # Load our private key
        from cryptography.hazmat.primitives.serialization import load_der_private_key
        our_private = load_der_private_key(self._x25519_private, password=None)

        # Perform ECDH
        shared_secret = our_private.exchange(peer_public)
        return shared_secret

    def close(self) -> None:
        """Close session (no-op for mock)."""
        self._closed = True
        self._authenticated = False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()


def mock_enumerate_tokens() -> list:
    """Return list of mock tokens for testing.

    Returns:
        List containing one mock token
    """
    return [
        TokenInfo(
            slot_id=0,
            token_label="Mock PIV Card",
            token_serial="MOCK123456",
            manufacturer="Mock Hardware Inc."
        )
    ]
