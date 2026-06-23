#!/usr/bin/env python

"""Tests for hardware token interface abstraction (Issue #2).

RED tests that verify the hardware token interface contract:
- TokenSession dataclass with required fields
- KeyInfo dataclass for cryptographic key info
- PIVSlot enum for slot selection
- Hardware exception hierarchy

These tests must fail until implementation exists.
"""

import pytest


# Direct imports (will fail with ImportError if not implemented)
from cohortcrypto.hardware import (
    TokenSession,
    KeyInfo,
    PIVSlot
)
from cohortcrypto.exceptions import (
    TokenNotFoundError,
    PKCSLibraryNotFoundError,
    PINError,
    HardwareCapabilityError,
    PIVSlotError
)


class TestKeyInfoDataclass:
    """Test KeyInfo dataclass structure."""

    def test_keyinfo_exists(self):
        """KeyInfo dataclass should be defined."""
        assert KeyInfo is not None

    def test_keyinfo_instantiable_basic(self):
        """KeyInfo should be instantiable with basic fields."""
        key = KeyInfo(
            algorithm="ed25519",
            public_key=b"\x01" * 32,
            certificate=None,
            piv_slot=None
        )
        assert key.algorithm == "ed25519"
        assert key.public_key == b"\x01" * 32
        assert key.certificate is None
        assert key.piv_slot is None

    def test_keyinfo_with_certificate(self):
        """KeyInfo should accept certificate field."""
        cert_der = b"\x30\x82\x01\x00" + b"\x00" * 256
        key = KeyInfo(
            algorithm="x25519",
            public_key=b"\x02" * 32,
            certificate=cert_der,
            piv_slot=PIVSlot.SLOT_9A
        )
        assert key.certificate == cert_der
        assert key.piv_slot == PIVSlot.SLOT_9A

    def test_keyinfo_algorithm_required(self):
        """KeyInfo requires algorithm field."""
        # Should raise TypeError if algorithm missing
        with pytest.raises(TypeError):
            KeyInfo(public_key=b"\x01" * 32)

    def test_keyinfo_public_key_required(self):
        """KeyInfo requires public_key field."""
        # Should raise TypeError if public_key missing
        with pytest.raises(TypeError):
            KeyInfo(algorithm="ed25519")

    def test_keyinfo_algorithms_supported(self):
        """KeyInfo should support various algorithms."""
        algorithms = ["ed25519", "x25519", "p256", "rsa2048"]
        for algo in algorithms:
            key = KeyInfo(
                algorithm=algo,
                public_key=b"\x01" * 32,
                certificate=None,
                piv_slot=None
            )
            assert key.algorithm == algo


class TestTokenSessionDataclass:
    """Test TokenSession dataclass structure."""

    def test_tokensession_exists(self):
        """TokenSession dataclass should be defined."""
        assert TokenSession is not None

    def test_tokensession_instantiable_full(self):
        """TokenSession should be instantiable with all fields."""
        signing_key = KeyInfo(
            algorithm="ed25519",
            public_key=b"\x01" * 32,
            certificate=None,
            piv_slot=PIVSlot.SLOT_9C
        )
        encryption_key = KeyInfo(
            algorithm="x25519",
            public_key=b"\x02" * 32,
            certificate=None,
            piv_slot=PIVSlot.SLOT_9A
        )
        session = TokenSession(
            token_type="YubiKey",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="5.4.3"
        )
        assert session.token_type == "YubiKey"
        assert session.slot_id == 0
        assert session.signing_key_info == signing_key
        assert session.encryption_key_info == encryption_key
        assert session.supports_x25519 is True
        assert session.supports_ed25519 is True
        assert session.firmware_version == "5.4.3"

    def test_tokensession_firmware_version_optional(self):
        """TokenSession.firmware_version should be optional."""
        signing_key = KeyInfo(algorithm="p256", public_key=b"\x03" * 64, certificate=None, piv_slot=None)
        encryption_key = KeyInfo(algorithm="p256", public_key=b"\x04" * 64, certificate=None, piv_slot=None)
        session = TokenSession(
            token_type="PIV Card",
            slot_id=1,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version=None  # Optional field
        )
        assert session.firmware_version is None
        assert session.token_type == "PIV Card"

    def test_tokensession_required_fields(self):
        """TokenSession should require all core fields."""
        signing_key = KeyInfo(algorithm="ed25519", public_key=b"\x01" * 32, certificate=None, piv_slot=None)
        encryption_key = KeyInfo(algorithm="x25519", public_key=b"\x02" * 32, certificate=None, piv_slot=None)

        # Missing token_type should raise TypeError
        with pytest.raises(TypeError):
            TokenSession(
                slot_id=0,
                signing_key_info=signing_key,
                encryption_key_info=encryption_key,
                supports_x25519=True,
                supports_ed25519=True,
                firmware_version="1.0"
            )

    def test_tokensession_slot_id_integer(self):
        """TokenSession.slot_id should be integer."""
        signing_key = KeyInfo(algorithm="ed25519", public_key=b"\x01" * 32, certificate=None, piv_slot=None)
        encryption_key = KeyInfo(algorithm="x25519", public_key=b"\x02" * 32, certificate=None, piv_slot=None)
        session = TokenSession(
            token_type="YubiKey",
            slot_id=5,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="1.0"
        )
        assert isinstance(session.slot_id, int)
        assert session.slot_id == 5

    def test_tokensession_boolean_support_flags(self):
        """TokenSession support flags should be boolean."""
        signing_key = KeyInfo(algorithm="ed25519", public_key=b"\x01" * 32, certificate=None, piv_slot=None)
        encryption_key = KeyInfo(algorithm="x25519", public_key=b"\x02" * 32, certificate=None, piv_slot=None)
        session = TokenSession(
            token_type="YubiKey",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=False,
            firmware_version="1.0"
        )
        assert isinstance(session.supports_x25519, bool)
        assert isinstance(session.supports_ed25519, bool)
        assert session.supports_x25519 is True
        assert session.supports_ed25519 is False


class TestPIVSlotEnum:
    """Test PIVSlot enum structure."""

    def test_pivslot_exists(self):
        """PIVSlot enum should be defined."""
        assert PIVSlot is not None

    def test_pivslot_has_slot_9a(self):
        """PIVSlot should have SLOT_9A member."""
        assert hasattr(PIVSlot, "SLOT_9A")
        assert PIVSlot.SLOT_9A is not None

    def test_pivslot_has_slot_9c(self):
        """PIVSlot should have SLOT_9C member."""
        assert hasattr(PIVSlot, "SLOT_9C")
        assert PIVSlot.SLOT_9C is not None

    def test_pivslot_has_auto(self):
        """PIVSlot should have AUTO member."""
        assert hasattr(PIVSlot, "AUTO")
        assert PIVSlot.AUTO is not None

    def test_pivslot_members_distinct(self):
        """PIVSlot enum members should be distinct."""
        assert PIVSlot.SLOT_9A != PIVSlot.SLOT_9C
        assert PIVSlot.SLOT_9A != PIVSlot.AUTO
        assert PIVSlot.SLOT_9C != PIVSlot.AUTO

    def test_pivslot_members_have_values(self):
        """PIVSlot enum members should have values."""
        assert PIVSlot.SLOT_9A.value is not None
        assert PIVSlot.SLOT_9C.value is not None
        assert PIVSlot.AUTO.value is not None

    def test_pivslot_can_be_used_in_keyinfo(self):
        """PIVSlot enum values should be usable in KeyInfo."""
        for slot in [PIVSlot.SLOT_9A, PIVSlot.SLOT_9C, PIVSlot.AUTO]:
            key = KeyInfo(
                algorithm="ed25519",
                public_key=b"\x01" * 32,
                certificate=None,
                piv_slot=slot
            )
            assert key.piv_slot == slot


class TestTokenNotFoundError:
    """Test TokenNotFoundError exception."""

    def test_tokennotfound_exists(self):
        """TokenNotFoundError should be defined."""
        assert TokenNotFoundError is not None

    def test_tokennotfound_is_exception(self):
        """TokenNotFoundError should inherit from Exception."""
        assert issubclass(TokenNotFoundError, Exception)

    def test_tokennotfound_instantiable(self):
        """TokenNotFoundError should be instantiable."""
        exc = TokenNotFoundError("No token found")
        assert str(exc) == "No token found"

    def test_tokennotfound_inheritance(self):
        """TokenNotFoundError should be instance of Exception."""
        exc = TokenNotFoundError("test message")
        assert isinstance(exc, Exception)


class TestPKCSLibraryNotFoundError:
    """Test PKCSLibraryNotFoundError exception."""

    def test_pkcs11library_exists(self):
        """PKCSLibraryNotFoundError should be defined."""
        assert PKCSLibraryNotFoundError is not None

    def test_pkcs11library_is_exception(self):
        """PKCSLibraryNotFoundError should inherit from Exception."""
        assert issubclass(PKCSLibraryNotFoundError, Exception)

    def test_pkcs11library_instantiable(self):
        """PKCSLibraryNotFoundError should be instantiable."""
        exc = PKCSLibraryNotFoundError("PKCS#11 library not found")
        assert isinstance(exc, Exception)


class TestPINError:
    """Test PINError exception."""

    def test_pinerror_exists(self):
        """PINError should be defined."""
        assert PINError is not None

    def test_pinerror_is_exception(self):
        """PINError should inherit from Exception."""
        assert issubclass(PINError, Exception)

    def test_pinerror_instantiable(self):
        """PINError should be instantiable."""
        exc = PINError("Invalid PIN")
        assert str(exc) == "Invalid PIN"

    def test_pinerror_inheritance(self):
        """PINError should be instance of Exception."""
        exc = PINError("PIN verification failed")
        assert isinstance(exc, Exception)


class TestHardwareCapabilityError:
    """Test HardwareCapabilityError exception."""

    def test_hardwarecapability_exists(self):
        """HardwareCapabilityError should be defined."""
        assert HardwareCapabilityError is not None

    def test_hardwarecapability_is_exception(self):
        """HardwareCapabilityError should inherit from Exception."""
        assert issubclass(HardwareCapabilityError, Exception)

    def test_hardwarecapability_instantiable(self):
        """HardwareCapabilityError should be instantiable."""
        exc = HardwareCapabilityError("Token does not support X25519")
        assert isinstance(exc, Exception)


class TestPIVSlotError:
    """Test PIVSlotError exception."""

    def test_pivslot_error_exists(self):
        """PIVSlotError should be defined."""
        assert PIVSlotError is not None

    def test_pivslot_error_is_exception(self):
        """PIVSlotError should inherit from Exception."""
        assert issubclass(PIVSlotError, Exception)

    def test_pivslot_error_instantiable(self):
        """PIVSlotError should be instantiable."""
        exc = PIVSlotError("Invalid PIV slot")
        assert isinstance(exc, Exception)


class TestExceptionHierarchy:
    """Test exception inheritance relationships."""

    def test_all_exceptions_inherit_from_exception(self):
        """All hardware exceptions should inherit from Exception."""
        exceptions = [
            TokenNotFoundError,
            PKCSLibraryNotFoundError,
            PINError,
            HardwareCapabilityError,
            PIVSlotError
        ]
        for exc_class in exceptions:
            assert issubclass(exc_class, Exception), f"{exc_class.__name__} should inherit from Exception"

    def test_exception_instantiation(self):
        """All exceptions should be instantiable with messages."""
        exceptions = [
            (TokenNotFoundError, "Token not found"),
            (PKCSLibraryNotFoundError, "Library not found"),
            (PINError, "Wrong PIN"),
            (HardwareCapabilityError, "Capability missing"),
            (PIVSlotError, "Invalid slot")
        ]
        for exc_class, message in exceptions:
            exc = exc_class(message)
            assert isinstance(exc, Exception)
            assert str(exc) == message
