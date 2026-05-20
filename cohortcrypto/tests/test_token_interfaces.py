"""RED tests for issue #2: Hardware token interface abstraction.

These tests define the acceptance criteria for:
- TokenSession dataclass: token_type, slot_id, signing_key_info,
  encryption_key_info, supports_x25519, supports_ed25519,
  firmware_version
- PIVSlot enum: SLOT_9A, SLOT_9C, AUTO
- KeyInfo dataclass: algorithm, public_key, certificate, piv_slot
- Hardware exceptions: TokenNotFoundError, PKCSLibraryNotFoundError,
  PINError, HardwareCapabilityError, PIVSlotError

Tests will fail until these classes/interfaces are defined and
exported from cohortcrypto.
"""

import pytest
from dataclasses import asdict, is_dataclass
from enum import Enum

from cohortcrypto import (
    PIVSlot,
    TokenNotFoundError,
    PKCSLibraryNotFoundError,
    PINError,
    HardwareCapabilityError,
    PIVSlotError,
)


class TestPIVSlotEnum:
    """PIVSlot enum tests."""

    def test_piv_slot_is_enum(self):
        """PIVSlot should be an Enum."""
        assert issubclass(PIVSlot, Enum)

    def test_piv_slot_has_auto(self):
        """PIVSlot should have AUTO value."""
        assert hasattr(PIVSlot, "AUTO")
        assert PIVSlot.AUTO.value == "auto"

    def test_piv_slot_has_slot_9a(self):
        """PIVSlot should have SLOT_9A value."""
        assert hasattr(PIVSlot, "SLOT_9A")
        assert PIVSlot.SLOT_9A.value == "9A"

    def test_piv_slot_has_slot_9c(self):
        """PIVSlot should have SLOT_9C value."""
        assert hasattr(PIVSlot, "SLOT_9C")
        assert PIVSlot.SLOT_9C.value == "9C"

    def test_piv_slot_enum_members(self):
        """PIVSlot should have at least AUTO, SLOT_9A, SLOT_9C."""
        members = {member.name for member in PIVSlot}
        assert "AUTO" in members
        assert "SLOT_9A" in members
        assert "SLOT_9C" in members

    def test_piv_slot_comparison(self):
        """PIVSlot enum members should be comparable."""
        assert PIVSlot.AUTO != PIVSlot.SLOT_9A
        assert PIVSlot.SLOT_9A != PIVSlot.SLOT_9C
        assert PIVSlot.AUTO == PIVSlot.AUTO


class TestKeyInfoDataclass:
    """KeyInfo dataclass tests."""

    def test_key_info_can_be_imported(self):
        """KeyInfo should be importable from cohortcrypto."""
        from cohortcrypto import KeyInfo

        assert KeyInfo is not None

    def test_key_info_is_dataclass(self):
        """KeyInfo should be a dataclass."""
        from cohortcrypto import KeyInfo

        assert is_dataclass(KeyInfo)

    def test_key_info_has_algorithm_field(self):
        """KeyInfo should have algorithm field."""
        from cohortcrypto import KeyInfo

        assert "algorithm" in KeyInfo.__dataclass_fields__

    def test_key_info_has_public_key_field(self):
        """KeyInfo should have public_key field."""
        from cohortcrypto import KeyInfo

        assert "public_key" in KeyInfo.__dataclass_fields__

    def test_key_info_has_certificate_field(self):
        """KeyInfo should have certificate field (optional)."""
        from cohortcrypto import KeyInfo

        assert "certificate" in KeyInfo.__dataclass_fields__

    def test_key_info_has_piv_slot_field(self):
        """KeyInfo should have piv_slot field (optional)."""
        from cohortcrypto import KeyInfo

        assert "piv_slot" in KeyInfo.__dataclass_fields__

    def test_key_info_create_minimal(self):
        """Can create KeyInfo with algorithm and public_key."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(algorithm="ed25519", public_key=b"test_public_key")
        assert key_info.algorithm == "ed25519"
        assert key_info.public_key == b"test_public_key"

    def test_key_info_create_with_all_fields(self):
        """Can create KeyInfo with all fields."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(
            algorithm="p256",
            public_key=b"test_public_key",
            certificate=b"test_cert_der",
            piv_slot="9A",
        )
        assert key_info.algorithm == "p256"
        assert key_info.public_key == b"test_public_key"
        assert key_info.certificate == b"test_cert_der"
        assert key_info.piv_slot == "9A"

    def test_key_info_certificate_defaults_to_none(self):
        """KeyInfo certificate should default to None."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(algorithm="ed25519", public_key=b"test_public_key")
        assert key_info.certificate is None

    def test_key_info_piv_slot_defaults_to_none(self):
        """KeyInfo piv_slot should default to None."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(algorithm="ed25519", public_key=b"test_public_key")
        assert key_info.piv_slot is None

    def test_key_info_supports_algorithm_values(self):
        """KeyInfo should accept various algorithm values."""
        from cohortcrypto import KeyInfo

        algorithms = ["ed25519", "p256", "p384", "rsa2048", "rsa4096"]
        for algo in algorithms:
            key_info = KeyInfo(algorithm=algo, public_key=b"test_key")
            assert key_info.algorithm == algo

    def test_key_info_serializable(self):
        """KeyInfo should be convertible to dict."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(
            algorithm="ed25519", public_key=b"test_public_key", piv_slot="9A"
        )
        d = asdict(key_info)
        assert d["algorithm"] == "ed25519"
        assert d["public_key"] == b"test_public_key"
        assert d["piv_slot"] == "9A"

    def test_key_info_with_empty_public_key(self):
        """KeyInfo accepts empty public_key bytes."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(algorithm="ed25519", public_key=b"")
        assert key_info.public_key == b""

    def test_key_info_with_empty_certificate(self):
        """KeyInfo accepts empty certificate bytes."""
        from cohortcrypto import KeyInfo

        key_info = KeyInfo(algorithm="ed25519", public_key=b"key", certificate=b"")
        assert key_info.certificate == b""


class TestTokenSessionDataclass:
    """TokenSession dataclass tests."""

    def test_token_session_can_be_imported(self):
        """TokenSession should be importable from cohortcrypto."""
        from cohortcrypto import TokenSession

        assert TokenSession is not None

    def test_token_session_is_dataclass(self):
        """TokenSession should be a dataclass."""
        from cohortcrypto import TokenSession

        assert is_dataclass(TokenSession)

    def test_token_session_has_token_type_field(self):
        """TokenSession should have token_type field."""
        from cohortcrypto import TokenSession

        assert "token_type" in TokenSession.__dataclass_fields__

    def test_token_session_has_slot_id_field(self):
        """TokenSession should have slot_id field."""
        from cohortcrypto import TokenSession

        assert "slot_id" in TokenSession.__dataclass_fields__

    def test_token_session_has_signing_key_info_field(self):
        """TokenSession should have signing_key_info field."""
        from cohortcrypto import TokenSession

        assert "signing_key_info" in TokenSession.__dataclass_fields__

    def test_token_session_has_encryption_key_info_field(self):
        """TokenSession should have encryption_key_info field."""
        from cohortcrypto import TokenSession

        assert "encryption_key_info" in TokenSession.__dataclass_fields__

    def test_token_session_has_supports_x25519_field(self):
        """TokenSession should have supports_x25519 field."""
        from cohortcrypto import TokenSession

        assert "supports_x25519" in TokenSession.__dataclass_fields__

    def test_token_session_has_supports_ed25519_field(self):
        """TokenSession should have supports_ed25519 field."""
        from cohortcrypto import TokenSession

        assert "supports_ed25519" in TokenSession.__dataclass_fields__

    def test_token_session_has_firmware_version_field(self):
        """TokenSession should have firmware_version field."""
        from cohortcrypto import TokenSession

        assert "firmware_version" in TokenSession.__dataclass_fields__

    def test_token_session_create_with_all_fields(self):
        """Can create TokenSession with all required fields."""
        from cohortcrypto import TokenSession, KeyInfo

        signing_key = KeyInfo(algorithm="ed25519", public_key=b"signing_key")
        encryption_key = KeyInfo(algorithm="x25519", public_key=b"encryption_key")

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="1.0.0",
        )

        assert session.token_type == "piv"
        assert session.slot_id == 0
        assert session.signing_key_info == signing_key
        assert session.encryption_key_info == encryption_key
        assert session.supports_x25519 is True
        assert session.supports_ed25519 is True
        assert session.firmware_version == "1.0.0"

    def test_token_session_token_type_values(self):
        """TokenSession should accept various token_type values."""
        from cohortcrypto import TokenSession, KeyInfo

        key = KeyInfo(algorithm="ed25519", public_key=b"key")

        for token_type in ["piv", "yubikey", "pkcs11_generic"]:
            session = TokenSession(
                token_type=token_type,
                slot_id=0,
                signing_key_info=key,
                encryption_key_info=key,
                supports_x25519=True,
                supports_ed25519=True,
                firmware_version=None,
            )
            assert session.token_type == token_type

    def test_token_session_firmware_version_optional(self):
        """TokenSession firmware_version can be None."""
        from cohortcrypto import TokenSession, KeyInfo

        key = KeyInfo(algorithm="ed25519", public_key=b"key")

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=key,
            encryption_key_info=key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None,
        )

        assert session.firmware_version is None

    def test_token_session_with_none_fields(self):
        """TokenSession can have None for optional fields."""
        from cohortcrypto import TokenSession, KeyInfo

        key = KeyInfo(algorithm="ed25519", public_key=b"key")

        session = TokenSession(
            token_type="piv",
            slot_id=1,
            signing_key_info=key,
            encryption_key_info=key,
            supports_x25519=False,
            supports_ed25519=True,
            firmware_version=None,
        )

        assert session.firmware_version is None
        assert session.supports_x25519 is False
        assert session.supports_ed25519 is True

    def test_token_session_different_slot_ids(self):
        """TokenSession supports different slot_id values."""
        from cohortcrypto import TokenSession, KeyInfo

        key = KeyInfo(algorithm="ed25519", public_key=b"key")

        for slot_id in [0, 1, 5, 255]:
            session = TokenSession(
                token_type="piv",
                slot_id=slot_id,
                signing_key_info=key,
                encryption_key_info=key,
                supports_x25519=True,
                supports_ed25519=True,
                firmware_version=None,
            )
            assert session.slot_id == slot_id

    def test_token_session_serializable(self):
        """TokenSession should be serializable to dict."""
        from cohortcrypto import TokenSession, KeyInfo

        key = KeyInfo(algorithm="ed25519", public_key=b"key")
        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=key,
            encryption_key_info=key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version="1.0",
        )

        d = asdict(session)
        assert d["token_type"] == "piv"
        assert d["slot_id"] == 0
        assert d["firmware_version"] == "1.0"


class TestHardwareExceptions:
    """Hardware exception tests."""

    def test_token_not_found_error_exists(self):
        """TokenNotFoundError should be importable."""
        assert TokenNotFoundError is not None

    def test_token_not_found_error_is_exception(self):
        """TokenNotFoundError should be an Exception."""
        assert issubclass(TokenNotFoundError, Exception)

    def test_token_not_found_error_instantiation(self):
        """Can instantiate TokenNotFoundError."""
        error = TokenNotFoundError("No token found")
        assert str(error) == "No token found"

    def test_pkcs_library_not_found_error_exists(self):
        """PKCSLibraryNotFoundError should be importable."""
        assert PKCSLibraryNotFoundError is not None

    def test_pkcs_library_not_found_error_is_exception(self):
        """PKCSLibraryNotFoundError should be an Exception."""
        assert issubclass(PKCSLibraryNotFoundError, Exception)

    def test_pkcs_library_not_found_error_instantiation(self):
        """Can instantiate PKCSLibraryNotFoundError."""
        error = PKCSLibraryNotFoundError("PKCS#11 library not found")
        assert str(error) == "PKCS#11 library not found"

    def test_pin_error_exists(self):
        """PINError should be importable."""
        assert PINError is not None

    def test_pin_error_is_exception(self):
        """PINError should be an Exception."""
        assert issubclass(PINError, Exception)

    def test_pin_error_instantiation(self):
        """Can instantiate PINError."""
        error = PINError("Incorrect PIN")
        assert str(error) == "Incorrect PIN"

    def test_hardware_capability_error_exists(self):
        """HardwareCapabilityError should be importable."""
        assert HardwareCapabilityError is not None

    def test_hardware_capability_error_is_exception(self):
        """HardwareCapabilityError should be an Exception."""
        assert issubclass(HardwareCapabilityError, Exception)

    def test_hardware_capability_error_instantiation(self):
        """Can instantiate HardwareCapabilityError."""
        error = HardwareCapabilityError("X25519 not supported")
        assert str(error) == "X25519 not supported"

    def test_piv_slot_error_exists(self):
        """PIVSlotError should be importable."""
        assert PIVSlotError is not None

    def test_piv_slot_error_is_exception(self):
        """PIVSlotError should be an Exception."""
        assert issubclass(PIVSlotError, Exception)

    def test_piv_slot_error_instantiation(self):
        """Can instantiate PIVSlotError."""
        error = PIVSlotError("Slot 9A is empty")
        assert str(error) == "Slot 9A is empty"

    def test_exception_inheritance_chain(self):
        """Exceptions should inherit from CohortCryptoError."""
        from cohortcrypto import CohortCryptoError, HardwareError

        assert issubclass(TokenNotFoundError, HardwareError)
        assert issubclass(PKCSLibraryNotFoundError, HardwareError)
        assert issubclass(PINError, HardwareError)
        assert issubclass(HardwareCapabilityError, HardwareError)
        assert issubclass(PIVSlotError, HardwareError)
        assert issubclass(HardwareError, CohortCryptoError)


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_token_session_with_piv_slot_info(self):
        """KeyInfo can include PIVSlot info."""
        from cohortcrypto import TokenSession, KeyInfo

        signing_key = KeyInfo(algorithm="ed25519", public_key=b"signing", piv_slot="9C")
        encryption_key = KeyInfo(
            algorithm="x25519", public_key=b"encryption", piv_slot="9A"
        )

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None,
        )

        assert session.signing_key_info.piv_slot == "9C"
        assert session.encryption_key_info.piv_slot == "9A"

    def test_keyinfo_with_certificate(self):
        """KeyInfo can store DER certificate."""
        from cohortcrypto import KeyInfo

        # Mock DER certificate (in reality would be X.509 DER bytes)
        mock_cert = b"\x30\x82\x02\x1a"  # DER SEQUENCE tag

        key_info = KeyInfo(
            algorithm="p256", public_key=b"public", certificate=mock_cert
        )

        assert key_info.certificate == mock_cert

    def test_exception_with_context(self):
        """Exceptions can be raised with contextual information."""
        with pytest.raises(PIVSlotError) as exc_info:
            raise PIVSlotError(
                "Slot 9C does not support X25519. Found algorithms: [ed25519]"
            )

        assert "Slot 9C" in str(exc_info.value)
        assert "X25519" in str(exc_info.value)

    def test_token_session_fields_are_separate_instances(self):
        """TokenSession signing_key_info and encryption_key_info are independent."""
        from cohortcrypto import TokenSession, KeyInfo

        signing_key = KeyInfo(algorithm="ed25519", public_key=b"signing")
        encryption_key = KeyInfo(algorithm="x25519", public_key=b"encryption")

        session = TokenSession(
            token_type="piv",
            slot_id=0,
            signing_key_info=signing_key,
            encryption_key_info=encryption_key,
            supports_x25519=True,
            supports_ed25519=True,
            firmware_version=None,
        )

        # Modifying one should not affect the other (since they're separate instances)
        assert session.signing_key_info is not session.encryption_key_info
        assert (
            session.signing_key_info.algorithm != session.encryption_key_info.algorithm
        )

    def test_piv_slot_auto_special_case(self):
        """PIVSlot.AUTO is a special case for automatic slot selection."""
        # Verify AUTO is distinct from other slots
        assert PIVSlot.AUTO.value == "auto"
        assert PIVSlot.AUTO != PIVSlot.SLOT_9A
        assert PIVSlot.AUTO != PIVSlot.SLOT_9C

    def test_multiple_token_sessions(self):
        """Can create multiple independent TokenSession instances."""
        from cohortcrypto import TokenSession, KeyInfo

        sessions = []
        for i in range(3):
            key = KeyInfo(algorithm="ed25519", public_key=f"key_{i}".encode())
            session = TokenSession(
                token_type="piv",
                slot_id=i,
                signing_key_info=key,
                encryption_key_info=key,
                supports_x25519=True,
                supports_ed25519=True,
                firmware_version=f"1.{i}",
            )
            sessions.append(session)

        # Verify all sessions are independent
        assert len(sessions) == 3
        assert sessions[0].slot_id == 0
        assert sessions[1].slot_id == 1
        assert sessions[2].slot_id == 2
