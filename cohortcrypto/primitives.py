"""Cryptographic primitives with hardware token support."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MemberCredential:
    """Member identity and cryptographic keys."""
    member_id: str
    x25519_public: bytes
    ed25519_public: bytes
    signing_algorithm: str  # "ed25519" or "p256_ecdsa"
    encryption_algorithm: str  # "x25519" or "p256_ecdh"
    hardware_backed: bool = False
    certificate_der: Optional[bytes] = None


def perform_ecdh(private_key_der: bytes, peer_public_key_der: bytes) -> bytes:
    """Perform ECDH key agreement (software).

    Used by mock hardware and software keys.

    Args:
        private_key_der: DER-encoded X25519 or P-256 private key
        peer_public_key_der: DER-encoded peer public key

    Returns:
        Shared secret bytes
    """
    # Phase 3 implementation
    raise NotImplementedError("Software ECDH")
