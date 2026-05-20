#!/usr/bin/env python

"""RED tests for hardware token interface abstractions.

Tests cover TokenSession, PIVSlot, KeyInfo, and exception hierarchy.
These tests should FAIL with ImportError until the implementation is complete.

Issue #2: Hardware token interface abstraction
"""

from enum import Enum


class TestPIVSlotEnum:
    """Test PIVSlot enum definition."""

    def test_pivslot_has_slot_9a(self):
        """PIVSlot should have SLOT_9A member."""
        from peermodel.cohortcrypto.hardware import PIVSlot
        assert hasattr(PIVSlot, 'SLOT_9A')

    def test_pivslot_has_slot_9c(self):
        """PIVSlot should have SLOT_9C member."""
        from peermodel.cohortcrypto.hardware import PIVSlot
        assert hasattr(PIVSlot, 'SLOT_9C')

    def test_pivslot_has_auto(self):
        """PIVSlot should have AUTO member."""
        from peermodel.cohortcrypto.hardware import PIVSlot
        assert hasattr(PIVSlot, 'AUTO')

    def test_pivslot_is_enum(self):
        """PIVSlot should be an Enum."""
        from peermodel.cohortcrypto.hardware import PIVSlot
        assert issubclass(PIVSlot, Enum)

    def test_pivslot_values_are_distinct(self):
        """PIVSlot enum values should be distinct."""
        from peermodel.cohortcrypto.hardware import PIVSlot
        values = [PIVSlot.SLOT_9A, PIVSlot.SLOT_9C, PIVSlot.AUTO]
        assert len(values) == len(set(values))


class TestKeyInfoDataclass:
    """Test KeyInfo dataclass definition."""

    def test_keyinfo_can_be_created(self):
        """KeyInfo should be instantiable with all required fields."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        key_info = KeyInfo(
            algorithm="p256",
            public_key=b"test_public_key",
            certificate=b"test_certificate",
            piv_slot="9A"
        )
        assert key_info is not None

    def test_keyinfo_algorithm_field(self):
        """KeyInfo should have algorithm field."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        key_info = KeyInfo(
            algorithm="ed25519",
            public_key=b"test_public_key",
            certificate=None,
            piv_slot=None
        )
        assert key_info.algorithm == "ed25519"

    def test_keyinfo_public_key_field(self):
        """KeyInfo should have public_key field."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        public_key_bytes = b"DER-encoded-public-key-bytes"
        key_info = KeyInfo(
            algorithm="p256",
            public_key=public_key_bytes,
            certificate=None,
            piv_slot=None
        )
        assert key_info.public_key == public_key_bytes

    def test_keyinfo_certificate_field_optional(self):
        """KeyInfo certificate field should be optional (None allowed)."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        key_info = KeyInfo(
            algorithm="x25519",
            public_key=b"public_key",
            certificate=None,
            piv_slot="9A"
        )
        assert key_info.certificate is None

    def test_keyinfo_piv_slot_field_optional(self):
        """KeyInfo piv_slot field should be optional (None allowed)."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        key_info = KeyInfo(
            algorithm="p256",
            public_key=b"public_key",
            certificate=b"cert",
            piv_slot=None
        )
        assert key_info.piv_slot is None

    def test_keyinfo_all_fields_accessible(self):
        """All KeyInfo fields should be accessible."""
        from peermodel.cohortcrypto.hardware import KeyInfo

        key_info = KeyInfo(
            algorithm="p384",
            public_key=b"pk_bytes",
            certificate=b"cert_bytes",
            piv_slot="9C"
        )
        assert key_info.algorithm == "p384"
        assert key_info.public_key == b"pk_bytes"
        assert key_info.certificate == b"cert_bytes"
        assert key_info.piv_slot == "9C"


class TestTokenSessionDataclass:
    """Test TokenSession dataclass definition."""

    def test_tokensession_can_be_created(self):
        """TokenSession should be instantiable with all required fields."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo(
            algorithm="ed25519",
            public_key=b"signing_pk",
            certificate=None,
            piv_slot="9C"
        )
        encryption_key = KeyInfo(
            algorithm="x25519",
            public_key=b"encryption_pk",
            certificate=None,
            piv_slot="9A"
        )

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None
        )
        assert session is not None

    def test_tokensession_token_type_piv(self):
        """TokenSession should accept 'piv' as token_type."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("ed25519", b"pk", None, None)
        encryption_key = KeyInfo("x25519", b"pk", None, None)

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None
        )
        assert session.token_type == "piv"

    def test_tokensession_token_type_yubikey(self):
        """TokenSession should accept 'yubikey' as token_type."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("p256", b"pk", None, None)
        encryption_key = KeyInfo("p256", b"pk", None, None)

        session = TokenSession(
            token_type="yubikey",
            slot_id=1,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version="5.2.3"
        )
        assert session.token_type == "yubikey"

    def test_tokensession_token_type_pkcs11_generic(self):
        """TokenSession should accept 'pkcs11_generic' as token_type."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("p256", b"pk", None, None)
        encryption_key = KeyInfo("p256", b"pk", None, None)

        session = TokenSession(
            token_type="pkcs11_generic",
            slot_id=2,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version=None
        )
        assert session.token_type == "pkcs11_generic"

    def test_tokensession_slot_id_field(self):
        """TokenSession should have slot_id field."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("ed25519", b"pk", None, None)
        encryption_key = KeyInfo("x25519", b"pk", None, None)

        session = TokenSession(
            token_type="piv",
            slot_id=42,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None
        )
        assert session.slot_id == 42

    def test_tokensession_signing_key_info_is_keyinfo(self):
        """TokenSession signing_key_info should be a KeyInfo instance."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("ed25519", b"signing_pk", None, "9C")
        encryption_key = KeyInfo("x25519", b"encryption_pk", None, "9A")

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None
        )
        assert isinstance(session.signing_key_info, KeyInfo)
        assert session.signing_key_info.algorithm == "ed25519"

    def test_tokensession_encryption_key_info_is_keyinfo(self):
        """TokenSession encryption_key_info should be a KeyInfo instance."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("p256", b"signing_pk", None, "9C")
        encryption_key = KeyInfo("p256", b"encryption_pk", None, "9A")

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version=None
        )
        assert isinstance(session.encryption_key_info, KeyInfo)
        assert session.encryption_key_info.public_key == b"encryption_pk"

    def test_tokensession_supports_x25519_flag(self):
        """TokenSession should have supports_x25519 boolean field."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("ed25519", b"pk", None, None)
        encryption_key = KeyInfo("x25519", b"pk", None, None)

        session = TokenSession(
            token_type="yubikey",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="5.4.0"
        )
        assert session.supports_x25519 is True

    def test_tokensession_supports_ed25519_flag(self):
        """TokenSession should have supports_ed25519 boolean field."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("p256", b"pk", None, None)
        encryption_key = KeyInfo("p256", b"pk", None, None)

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version=None
        )
        assert session.supports_ed25519 is False

    def test_tokensession_firmware_version_optional(self):
        """TokenSession firmware_version should be optional (None allowed)."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("p256", b"pk", None, None)
        encryption_key = KeyInfo("p256", b"pk", None, None)

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=False,
            supports_ed25519=False,
            firmware_version=None
        )
        assert session.firmware_version is None

    def test_tokensession_firmware_version_present(self):
        """TokenSession should store firmware_version when provided."""
        from peermodel.cohortcrypto.hardware import TokenSession, KeyInfo

        signing_key = KeyInfo("ed25519", b"pk", None, None)
        encryption_key = KeyInfo("x25519", b"pk", None, None)

        session = TokenSession(
            token_type="yubikey",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="5.2.3"
        )
        assert session.firmware_version == "5.2.3"


class TestHardwareExceptionHierarchy:
    """Test hardware exception class definitions and hierarchy."""

    def test_hardware_error_base_exists(self):
        """HardwareError base exception should exist."""
        from peermodel.cohortcrypto.exceptions import HardwareError
        assert issubclass(HardwareError, Exception)

    def test_token_not_found_error_exists(self):
        """TokenNotFoundError should exist and inherit from HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            TokenNotFoundError, HardwareError
        )
        assert issubclass(TokenNotFoundError, HardwareError)

    def test_pkcs_library_not_found_error_exists(self):
        """PKCSLibraryNotFoundError should inherit from HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            PKCSLibraryNotFoundError, HardwareError
        )
        assert issubclass(PKCSLibraryNotFoundError, HardwareError)

    def test_pin_error_exists(self):
        """PINError should exist and inherit from HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            PINError, HardwareError
        )
        assert issubclass(PINError, HardwareError)

    def test_hardware_capability_error_exists(self):
        """HardwareCapabilityError should inherit from HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            HardwareCapabilityError, HardwareError
        )
        assert issubclass(HardwareCapabilityError, HardwareError)

    def test_piv_slot_error_exists(self):
        """PIVSlotError should exist and inherit from HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            PIVSlotError, HardwareError
        )
        assert issubclass(PIVSlotError, HardwareError)

    def test_token_not_found_error_instantiable(self):
        """TokenNotFoundError should be instantiable with a message."""
        from peermodel.cohortcrypto.exceptions import TokenNotFoundError
        error = TokenNotFoundError("No token found in slot 0")
        assert str(error) == "No token found in slot 0"

    def test_pkcs_library_not_found_error_instantiable(self):
        """PKCSLibraryNotFoundError should be instantiable with message."""
        from peermodel.cohortcrypto.exceptions import (
            PKCSLibraryNotFoundError
        )
        msg = "PKCS#11 library not found at /usr/lib/opensc-pkcs11.so"
        error = PKCSLibraryNotFoundError(msg)
        assert "PKCS#11 library not found" in str(error)

    def test_pin_error_instantiable(self):
        """PINError should be instantiable with a message."""
        from peermodel.cohortcrypto.exceptions import PINError
        error = PINError("Invalid PIN: 3 attempts remaining")
        assert "Invalid PIN" in str(error)

    def test_hardware_capability_error_instantiable(self):
        """HardwareCapabilityError should be instantiable with a message."""
        from peermodel.cohortcrypto.exceptions import HardwareCapabilityError
        error = HardwareCapabilityError("Token does not support X25519")
        assert "X25519" in str(error)

    def test_piv_slot_error_instantiable(self):
        """PIVSlotError should be instantiable with a message."""
        from peermodel.cohortcrypto.exceptions import PIVSlotError
        error = PIVSlotError("Slot 9A is empty")
        assert "Slot 9A" in str(error)

    def test_all_hardware_errors_catchable_as_hardware_error(self):
        """All hardware exceptions should be catchable with HardwareError."""
        from peermodel.cohortcrypto.exceptions import (
            HardwareError,
            TokenNotFoundError,
            PKCSLibraryNotFoundError,
            PINError,
            HardwareCapabilityError,
            PIVSlotError
        )

        exceptions = [
            TokenNotFoundError("test"),
            PKCSLibraryNotFoundError("test"),
            PINError("test"),
            HardwareCapabilityError("test"),
            PIVSlotError("test")
        ]

        for exc in exceptions:
            assert isinstance(exc, HardwareError)
