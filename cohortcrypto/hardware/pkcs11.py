"""PKCS#11 operations for real hardware tokens (Phase 3E).

Provides functions to open sessions with real PIV cards and YubiKeys
via the PKCS#11 library interface. Falls back to mock in test mode.
"""

from dataclasses import dataclass
from typing import Optional
import os

from .mock import MockTokenSession, PIVSlot, TokenInfo
from ..exceptions import TokenNotFoundError, PINError, PIVSlotError, HardwareCapabilityError


@dataclass
class RealTokenSession:
    """Session with real PKCS#11 hardware token.

    Wraps python-pkcs11 session objects for sign/ECDH operations.
    Private keys never leave the token.
    """
    slot_id: int
    token_label: str
    token_serial: str
    piv_slot: PIVSlot
    x25519_public: bytes
    ed25519_public: bytes
    signing_algorithm: str = "ed25519"
    encryption_algorithm: str = "x25519"
    certificate_der: Optional[bytes] = None

    # PKCS#11 internal state (not exposed to users)
    _pkcs11_session: Optional[object] = None
    _signing_key_object: Optional[object] = None
    _encryption_key_object: Optional[object] = None
    _authenticated: bool = False

    def sign(self, message: bytes) -> bytes:
        """Sign message using token's Ed25519 key.

        Args:
            message: Message to sign

        Returns:
            Ed25519 signature (64 bytes)

        Raises:
            RuntimeError: Session not authenticated
            HardwareCapabilityError: Token lacks signing capability
        """
        if not self._authenticated:
            raise RuntimeError("Session not authenticated")

        # If this is a mock session, delegate directly
        if hasattr(self._pkcs11_session, 'sign') and not self._signing_key_object:
            return self._pkcs11_session.sign(message)

        if not self._signing_key_object:
            raise HardwareCapabilityError("Token signing key not available")

        try:
            import pkcs11
            # Sign using token's Ed25519 key with EDDSA mechanism
            signature = self._pkcs11_session.sign(
                self._signing_key_object,
                message,
                mechanism=pkcs11.Mechanism.EDDSA
            )
            return signature
        except Exception as e:
            raise RuntimeError(f"Signing failed: {e}")

    def ecdh(self, peer_public_key_der: bytes) -> bytes:
        """Perform ECDH using token's X25519 key.

        Args:
            peer_public_key_der: Peer's DER-encoded X25519 public key

        Returns:
            Raw shared secret (32 bytes for X25519)

        Raises:
            RuntimeError: Session not authenticated
            HardwareCapabilityError: Token lacks ECDH capability
        """
        if not self._authenticated:
            raise RuntimeError("Session not authenticated")

        # If this is a mock session, delegate directly
        if hasattr(self._pkcs11_session, 'ecdh') and not self._encryption_key_object:
            return self._pkcs11_session.ecdh(peer_public_key_der)

        if not self._encryption_key_object:
            raise HardwareCapabilityError("Token encryption key not available")

        try:
            import pkcs11
            # Derive shared secret using ECDH with token's X25519 key
            # This is typically done via C_DeriveKey in PKCS#11
            shared_secret = self._pkcs11_session.derive_key(
                self._encryption_key_object,
                peer_public_key_der,
                mechanism=pkcs11.Mechanism.ECDH1_DERIVE
            )
            return shared_secret
        except Exception as e:
            raise RuntimeError(f"ECDH failed: {e}")

    def close(self) -> None:
        """Close PKCS#11 session and cleanup."""
        if self._pkcs11_session:
            try:
                self._pkcs11_session.close()
            except Exception:
                pass
        self._authenticated = False
        self._signing_key_object = None
        self._encryption_key_object = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.close()


def open_pkcs11_session(
    pkcs11_lib_path: Optional[str],
    slot_id: Optional[int],
    pin: Optional[str],
    piv_slot: PIVSlot,
    require_hardware_signing: bool = True,
    require_hardware_encryption: bool = True
) -> RealTokenSession:
    """Open authenticated session with real PKCS#11 hardware token.

    **Important**: This function requires a real PKCS#11 library and hardware token.
    It is called automatically when COHORTCRYPTO_MOCK_HARDWARE is not set.

    Args:
        pkcs11_lib_path: Path to PKCS#11 library (None = auto-detect via detection.py)
        slot_id: Specific slot ID (None = first token found)
        pin: Token PIN (required for authentication)
        piv_slot: Which PIV slot to use (9A/9C/9D/9E or AUTO)
        require_hardware_signing: Require Ed25519 signing capability
        require_hardware_encryption: Require X25519 encryption capability

    Returns:
        RealTokenSession with open PKCS#11 session

    Raises:
        TokenNotFoundError: No token found in requested slot
        PINError: Incorrect PIN
        PIVSlotError: Requested PIV slot not available or wrong type
        HardwareCapabilityError: Token lacks required capabilities
    """
    # Mock fallback for testing without hardware
    if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
        session = MockTokenSession.create(piv_slot=piv_slot)
        session.authenticate(pin or "123456")
        return RealTokenSession(
            slot_id=session.slot_id,
            token_label=session.token_label,
            token_serial=session.token_serial,
            piv_slot=session.piv_slot,
            x25519_public=session.x25519_public,
            ed25519_public=session.ed25519_public,
            signing_algorithm=session.signing_algorithm,
            encryption_algorithm=session.encryption_algorithm,
            _pkcs11_session=session,
            _authenticated=True
        )

    try:
        import pkcs11
    except ImportError:
        raise TokenNotFoundError(
            "python-pkcs11 not installed. "
            "Install with: pip install python-pkcs11"
        )

    from .detection import find_pkcs11_library, detect_tokens
    from .piv import detect_piv_slots, select_best_piv_slot

    # Find PKCS#11 library
    if not pkcs11_lib_path:
        pkcs11_lib_path = find_pkcs11_library()

    # Load library
    try:
        lib = pkcs11.lib(pkcs11_lib_path)
    except Exception as e:
        raise TokenNotFoundError(f"Failed to load PKCS#11 library: {e}")

    # Select slot
    if slot_id is None:
        try:
            tokens = detect_tokens()
            if not tokens:
                raise TokenNotFoundError("No hardware tokens found")
            slot_id = tokens[0].slot_id
        except TokenNotFoundError:
            raise
        except Exception as e:
            raise TokenNotFoundError(f"Failed to enumerate tokens: {e}")

    # Get slot
    try:
        slots = lib.get_slots(token_present=True)
        slot = None
        for s in slots:
            if s.slot_id == slot_id:
                slot = s
                break

        if not slot:
            raise TokenNotFoundError(f"No token in slot {slot_id}")
    except Exception as e:
        if isinstance(e, TokenNotFoundError):
            raise
        raise TokenNotFoundError(f"Failed to access slot {slot_id}: {e}")

    # Get token and open session
    try:
        token = slot.get_token()
        session = slot.open(rw=False)  # Read-only for crypto ops
    except Exception as e:
        raise TokenNotFoundError(f"Failed to open session: {e}")

    # Authenticate with PIN
    if pin:
        try:
            session.login(pin)
        except Exception as e:
            session.close()
            raise PINError(f"Incorrect PIN: {e}")
    else:
        raise PINError("PIN required for PKCS#11 authentication")

    # Detect available PIV slots on token
    try:
        available_slots = detect_piv_slots(session)
    except Exception as e:
        session.close()
        raise PIVSlotError(f"Failed to detect PIV slots: {e}")

    # Select PIV slot
    if piv_slot == PIVSlot.AUTO:
        try:
            piv_slot = select_best_piv_slot(available_slots)
        except PIVSlotError:
            session.close()
            raise
    elif piv_slot not in available_slots:
        session.close()
        raise PIVSlotError(f"PIV slot {piv_slot.value} not available on token")

    # Extract public keys from certificate
    try:
        slot_info = available_slots[piv_slot]
        x25519_public = slot_info.get('x25519_public', b'')
        ed25519_public = slot_info.get('ed25519_public', b'')
        certificate_der = slot_info.get('certificate_der')

        # Get key objects for signing/ECDH
        signing_key_object = slot_info.get('signing_key_object')
        encryption_key_object = slot_info.get('encryption_key_object')

        if require_hardware_signing and not signing_key_object:
            session.close()
            raise HardwareCapabilityError(f"Token {piv_slot.value} lacks signing capability")

        if require_hardware_encryption and not encryption_key_object:
            session.close()
            raise HardwareCapabilityError(f"Token {piv_slot.value} lacks encryption capability")

    except Exception as e:
        session.close()
        if isinstance(e, (PIVSlotError, HardwareCapabilityError)):
            raise
        raise PIVSlotError(f"Failed to extract keys from slot: {e}")

    return RealTokenSession(
        slot_id=slot_id,
        token_label=token.label.strip(),
        token_serial=token.serial.strip(),
        piv_slot=piv_slot,
        x25519_public=x25519_public,
        ed25519_public=ed25519_public,
        certificate_der=certificate_der,
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        _pkcs11_session=session,
        _signing_key_object=signing_key_object,
        _encryption_key_object=encryption_key_object,
        _authenticated=True
    )


def pkcs11_sign(session: RealTokenSession, message: bytes) -> bytes:
    """Sign message using token's Ed25519 key.

    Args:
        session: Open RealTokenSession
        message: Message to sign

    Returns:
        Ed25519 signature (64 bytes)

    Raises:
        RuntimeError: Session not authenticated
        HardwareCapabilityError: Token lacks signing capability
    """
    return session.sign(message)


def pkcs11_ecdh(session: RealTokenSession, peer_public_key_der: bytes) -> bytes:
    """Perform ECDH using token's X25519 key.

    Args:
        session: Open RealTokenSession
        peer_public_key_der: Peer's DER-encoded X25519 public key

    Returns:
        Raw shared secret (32 bytes for X25519)

    Raises:
        RuntimeError: Session not authenticated
        HardwareCapabilityError: Token lacks ECDH capability
    """
    return session.ecdh(peer_public_key_der)
