"""PKCS#11 operations (Phase 3B stub)."""

from typing import Optional
from .mock import MockTokenSession, PIVSlot


def open_pkcs11_session(
    pkcs11_lib_path: Optional[str],
    slot_id: Optional[int],
    pin: Optional[str],
    piv_slot: PIVSlot,
    require_hardware_signing: bool,
    require_hardware_encryption: bool
) -> MockTokenSession:
    """Open PKCS#11 session with token (Phase 3B stub).

    This is a Phase 3E implementation task.
    For now, raise NotImplementedError.

    Returns:
        TokenSession connected to hardware token

    Raises:
        NotImplementedError: Real PKCS#11 not yet implemented
    """
    raise NotImplementedError("PKCS#11 session management (Phase 3B/3E)")


def pkcs11_sign(session: MockTokenSession, message: bytes) -> bytes:
    """Sign message using token's signing key (Phase 3B stub).

    Args:
        session: Open TokenSession
        message: Message to sign

    Returns:
        Signature bytes
    """
    raise NotImplementedError("PKCS#11 signing (Phase 3B/3E)")


def pkcs11_ecdh(session: MockTokenSession, peer_public_key_der: bytes) -> bytes:
    """Perform ECDH key agreement on token (Phase 3B stub).

    Args:
        session: Open TokenSession
        peer_public_key_der: Peer's public key (DER-encoded)

    Returns:
        Raw shared secret bytes
    """
    raise NotImplementedError("PKCS#11 ECDH (Phase 3B/3E)")
