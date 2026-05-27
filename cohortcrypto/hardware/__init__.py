"""Hardware token operations for CohortCrypto."""

import os
from typing import List, Optional, ContextManager
from contextlib import contextmanager

from .mock import MockTokenSession, TokenInfo, PIVSlot, mock_enumerate_tokens
from .interfaces import KeyInfo, TokenSession
from ..exceptions import (
    TokenNotFoundError,
    PKCSLibraryNotFoundError,
    PINError,
    HardwareCapabilityError,
    PIVSlotError
)


__all__ = [
    'enumerate_tokens',
    'open_token',
    'credential_from_token',
    'generate_keys_on_token',
    'TokenInfo',
    'MockTokenSession',
    'PIVSlot',
    'KeyInfo',
    'TokenSession'
]


def enumerate_tokens() -> List[TokenInfo]:
    """Detect all available hardware tokens.

    In mock mode (COHORTCRYPTO_MOCK_HARDWARE=1), returns mock tokens.
    In real mode, searches for PKCS#11 libraries in standard system paths
    plus COHORTCRYPTO_PKCS11_PATH environment variable.

    Returns:
        List of TokenInfo for each detected token.

    Raises:
        PKCSLibraryNotFoundError: No PKCS#11 library found on system.
    """
    if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
        return mock_enumerate_tokens()

    # Real hardware detection (Phase 3B)
    from .detection import detect_tokens
    return detect_tokens()


@contextmanager
def open_token(
    pkcs11_lib_path: Optional[str] = None,
    slot_id: Optional[int] = None,
    pin: Optional[str] = None,
    piv_slot: PIVSlot = PIVSlot.AUTO,
    require_hardware_signing: bool = True,
    require_hardware_encryption: bool = True
) -> ContextManager[MockTokenSession]:
    """Open authenticated session with hardware token.

    In mock mode, returns MockTokenSession.
    In real mode, opens PKCS#11 session with token.

    Args:
        pkcs11_lib_path: Path to PKCS#11 .so/.dll (None = auto-detect)
        slot_id: PKCS#11 slot index (None = first slot with token)
        pin: Token PIN (None = prompt interactively)
        piv_slot: PIV slot to use (AUTO detects best)
        require_hardware_signing: Require hardware signing capability
        require_hardware_encryption: Require hardware encryption capability

    Returns:
        Context manager yielding TokenSession

    Raises:
        TokenNotFoundError: No token found
        PINError: Incorrect PIN
        PIVSlotError: Slot empty or wrong type
        HardwareCapabilityError: Token lacks required capability
    """
    if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
        # Mock mode: create mock session
        if pin is None:
            pin = "123456"

        session = MockTokenSession.create(piv_slot=piv_slot)
        try:
            session.authenticate(pin)
            yield session
        finally:
            session.close()
        return

    # Real hardware implementation (Phase 3B)
    from .pkcs11 import open_pkcs11_session
    session = open_pkcs11_session(
        pkcs11_lib_path,
        slot_id,
        pin,
        piv_slot,
        require_hardware_signing,
        require_hardware_encryption
    )
    try:
        yield session
    finally:
        session.close()


def credential_from_token(
    session: MockTokenSession,
    member_id: str
) -> 'MemberCredential':
    """Create MemberCredential from token session.

    Args:
        session: Open TokenSession
        member_id: Unique member identifier

    Returns:
        MemberCredential with hardware_backed=True
    """
    # Import here to avoid circular dependency
    from ..primitives import MemberCredential

    return MemberCredential(
        member_id=member_id,
        x25519_public=session.x25519_public,
        ed25519_public=session.ed25519_public,
        signing_algorithm=session.signing_algorithm,
        encryption_algorithm=session.encryption_algorithm,
        hardware_backed=True,
        certificate_der=session.certificate_der
    )


def generate_keys_on_token(
    session: MockTokenSession,
    overwrite: bool = False
) -> MockTokenSession:
    """Generate keypair on hardware token.

    WARNING: Irreversible. Generated private key cannot be exported.

    Args:
        session: Open TokenSession
        overwrite: Allow overwriting existing keys (requires confirmation)

    Returns:
        Updated TokenSession with new keys

    Raises:
        SlotOccupiedError: Slot contains key and overwrite=False
    """
    # Phase 3B implementation
    raise NotImplementedError("Key generation on hardware tokens")
