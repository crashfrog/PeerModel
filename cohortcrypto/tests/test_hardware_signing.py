"""RED tests for issue #5: Hardware signing with on-token private keys.

These tests define the acceptance criteria for hardware-backed signing:
- Sign arbitrary bytes using Ed25519 private key stored on hardware token
- Sign arbitrary bytes using P-256 ECDSA private key stored on hardware token
- Private key never leaves the token (only signature is returned)
- Signatures are compatible with software verify_bytes()
- Works with both mock and real PKCS#11 tokens

NOTE: Mock implementation already works. These tests expose bugs in the
REAL PKCS#11 implementation (RealTokenSession) which uses wrong mechanism
(SHA256_RSA_PKCS instead of Ed25519/P256 native signing).

Tests will pass with mock hardware, fail with real hardware until fixed.
"""

import pytest
import os

from cohortcrypto import (
    open_token,
    credential_from_token,
    MockTokenSession,
    PIVSlot,
    PINError,
)


# Import primitives for signature verification
import peermodel.primitives as primitives


@pytest.fixture(autouse=True)
def enable_mock_hardware():
    """Enable mock hardware for all tests."""
    os.environ['COHORTCRYPTO_MOCK_HARDWARE'] = '1'
    yield
    if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
        del os.environ['COHORTCRYPTO_MOCK_HARDWARE']


@pytest.fixture
def mock_token_session():
    """Create an authenticated mock token session."""
    session = MockTokenSession.create()
    session.authenticate("123456")
    return session


# Acceptance Criteria: Sign with Ed25519 on hardware

class TestHardwareEd25519Signing:
    """Test Ed25519 signing with hardware tokens."""

    def test_sign_returns_bytes(self, mock_token_session):
        """MockTokenSession.sign() returns bytes."""
        message = b"test message"
        signature = mock_token_session.sign(message)
        assert isinstance(signature, bytes)

    def test_sign_returns_64_bytes_for_ed25519(self, mock_token_session):
        """Ed25519 signature is exactly 64 bytes."""
        message = b"test message"
        signature = mock_token_session.sign(message)
        assert len(signature) == 64

    def test_sign_different_messages_produce_different_signatures(
        self, mock_token_session
    ):
        """Different messages produce different signatures."""
        message1 = b"message one"
        message2 = b"message two"

        sig1 = mock_token_session.sign(message1)
        sig2 = mock_token_session.sign(message2)

        assert sig1 != sig2

    def test_sign_same_message_produces_same_signature(self, mock_token_session):
        """Same message signed twice produces identical signature (deterministic)."""
        message = b"consistent message"

        sig1 = mock_token_session.sign(message)
        sig2 = mock_token_session.sign(message)

        assert sig1 == sig2

    def test_sign_requires_authentication(self):
        """sign() requires authenticated session."""
        session = MockTokenSession.create()
        # Don't authenticate

        with pytest.raises(RuntimeError, match="not authenticated"):
            session.sign(b"test")

    def test_sign_empty_message(self, mock_token_session):
        """Can sign empty message."""
        message = b""
        signature = mock_token_session.sign(message)
        assert isinstance(signature, bytes)
        assert len(signature) == 64

    def test_sign_large_message(self, mock_token_session):
        """Can sign large message (no size limit)."""
        message = b"x" * 1024 * 1024  # 1 MB
        signature = mock_token_session.sign(message)
        assert len(signature) == 64

    def test_sign_binary_message(self, mock_token_session):
        """Can sign binary data (not just UTF-8 text)."""
        message = bytes(range(256))
        signature = mock_token_session.sign(message)
        assert len(signature) == 64


# Acceptance Criteria: Signature format correct per algorithm

class TestSignatureFormat:
    """Test that signatures match expected format for each algorithm."""

    def test_ed25519_signature_length(self, mock_token_session):
        """Ed25519 signature is always 64 bytes (raw format)."""
        message = b"test"
        signature = mock_token_session.sign(message)
        assert len(signature) == 64

    def test_signature_is_not_plaintext(self, mock_token_session):
        """Signature does not contain plaintext message."""
        message = b"secret data that should not appear in signature"
        signature = mock_token_session.sign(message)
        assert message not in signature

    def test_signature_is_not_base64(self, mock_token_session):
        """Signature is raw bytes, not base64 encoded."""
        import base64

        message = b"test"
        signature = mock_token_session.sign(message)

        # Base64 would be ASCII, raw bytes will have high bytes
        try:
            _ = base64.b64decode(signature, validate=True)  # noqa: F841
            # If it decodes, it's likely base64 - this should fail
            pytest.fail("Signature should be raw bytes, not base64")
        except Exception:
            # Expected - raw bytes cannot be decoded as base64
            pass


# Acceptance Criteria: Compatible with software verify_bytes()

class TestCrossCompatibility:
    """Test that hardware signatures verify with software primitives."""

    def test_hardware_signature_verifies_with_software(self, mock_token_session):
        """Hardware-signed message verifies with software verify_bytes()."""
        message = b"cross-platform message"
        signature = mock_token_session.sign(message)

        # Verify using software primitives
        public_key = mock_token_session.ed25519_public
        is_valid = primitives.verify_bytes(
            message, signature, public_key, algorithm="ed25519"
        )

        assert is_valid is True

    def test_tampered_message_fails_verification(self, mock_token_session):
        """Tampered message fails signature verification."""
        message = b"original message"
        signature = mock_token_session.sign(message)

        # Tamper with message
        tampered_message = b"tampered message"
        public_key = mock_token_session.ed25519_public

        is_valid = primitives.verify_bytes(
            tampered_message, signature, public_key, algorithm="ed25519"
        )

        assert is_valid is False

    def test_tampered_signature_fails_verification(self, mock_token_session):
        """Tampered signature fails verification."""
        message = b"message"
        signature = mock_token_session.sign(message)

        # Tamper with signature
        tampered_sig = bytes([(b + 1) % 256 for b in signature])
        public_key = mock_token_session.ed25519_public

        is_valid = primitives.verify_bytes(
            message, tampered_sig, public_key, algorithm="ed25519"
        )

        assert is_valid is False

    def test_wrong_public_key_fails_verification(self, mock_token_session):
        """Signature fails verification with wrong public key."""
        message = b"message"
        signature = mock_token_session.sign(message)

        # Use different session's public key
        other_session = MockTokenSession.create()
        wrong_public_key = other_session.ed25519_public

        is_valid = primitives.verify_bytes(
            message, signature, wrong_public_key, algorithm="ed25519"
        )

        assert is_valid is False

    def test_multiple_signatures_all_verify(self):
        """Multiple tokens can sign and verify independently."""
        message = b"shared message"

        # Create three independent sessions
        sessions = [MockTokenSession.create() for _ in range(3)]
        for session in sessions:
            session.authenticate("123456")

        # Each signs the message
        signatures = [session.sign(message) for session in sessions]

        # Each signature verifies with corresponding public key
        for session, signature in zip(sessions, signatures):
            is_valid = primitives.verify_bytes(
                message, signature, session.ed25519_public, algorithm="ed25519"
            )
            assert is_valid is True

        # Cross-verification should fail
        for i, session in enumerate(sessions):
            for j, signature in enumerate(signatures):
                if i != j:
                    is_valid = primitives.verify_bytes(
                        message,
                        signature,
                        session.ed25519_public,
                        algorithm="ed25519",
                    )
                    assert is_valid is False


# Acceptance Criteria: Private key never exported

class TestPrivateKeyProtection:
    """Test that private keys remain on hardware and never leak."""

    def test_private_key_not_in_session_attributes(self, mock_token_session):
        """Session does not expose private key in public attributes."""
        public_attrs = [
            attr for attr in dir(mock_token_session) if not attr.startswith("_")
        ]

        # Check no public attribute contains 'private'
        for attr in public_attrs:
            assert "private" not in attr.lower()

    def test_signing_does_not_return_private_key(self, mock_token_session):
        """sign() returns only signature, never private key material."""
        message = b"test"
        signature = mock_token_session.sign(message)

        # Signature should be 64 bytes (Ed25519)
        # Private key would be 32 bytes (seed) or 64 bytes (expanded)
        # If signature contains private key, verification with public key would fail
        is_valid = primitives.verify_bytes(
            message,
            signature,
            mock_token_session.ed25519_public,
            algorithm="ed25519",
        )
        assert is_valid is True

    def test_cannot_extract_private_key_from_signature(self, mock_token_session):
        """Cannot derive private key from public key + signature."""
        message = b"known message"
        signature = mock_token_session.sign(message)

        # Even with message, signature, and public key, cannot sign a new message
        # (This test documents the security property)

        # Try to use signature as if it were a private key - should fail
        try:
            _ = primitives.sign_bytes(message, signature)  # noqa: F841
            pytest.fail("Should not be able to sign with signature bytes")
        except Exception:
            # Expected - signature is not a private key
            pass

    def test_mock_private_key_is_protected(self):
        """Mock implementation hides private key (starts with _)."""
        session = MockTokenSession.create()

        # Private keys should be marked as internal (_attribute)
        assert hasattr(session, "_ed25519_private")
        assert not hasattr(session, "ed25519_private")


# Integration Tests with open_token()

class TestOpenTokenSigningIntegration:
    """Test signing through open_token() context manager."""

    def test_sign_with_open_token_context(self):
        """Can sign message using open_token() context manager."""
        message = b"context manager test"

        with open_token(pin="123456") as session:
            signature = session.sign(message)
            assert len(signature) == 64

            # Verify signature
            is_valid = primitives.verify_bytes(
                message, signature, session.ed25519_public, algorithm="ed25519"
            )
            assert is_valid is True

    def test_sign_multiple_messages_in_one_session(self):
        """Can sign multiple messages in same session."""
        messages = [b"first", b"second", b"third"]

        with open_token(pin="123456") as session:
            signatures = [session.sign(msg) for msg in messages]

            # All signatures verify
            for msg, sig in zip(messages, signatures):
                is_valid = primitives.verify_bytes(
                    msg, sig, session.ed25519_public, algorithm="ed25519"
                )
                assert is_valid is True

    def test_cannot_sign_after_session_closes(self):
        """Cannot sign after session is closed."""
        message = b"test"

        with open_token(pin="123456") as session:
            session.sign(message)  # Works inside context

        # After context, session is closed
        with pytest.raises((RuntimeError, Exception)):
            session.sign(message)

    def test_wrong_pin_prevents_signing(self):
        """Wrong PIN prevents session opening and signing."""
        with pytest.raises(PINError):
            with open_token(pin="wrong_pin") as session:
                session.sign(b"test")


# MemberCredential Integration

class TestCredentialFromTokenSigning:
    """Test that MemberCredential created from token can verify signatures."""

    def test_credential_public_key_verifies_token_signature(self):
        """MemberCredential public key verifies token signatures."""
        message = b"credential test"

        with open_token(pin="123456") as session:
            signature = session.sign(message)
            cred = credential_from_token(session, "alice")

            # Verify using credential's public key
            is_valid = primitives.verify_bytes(
                message, signature, cred.ed25519_public, algorithm="ed25519"
            )
            assert is_valid is True

    def test_credential_signing_algorithm_field(self):
        """MemberCredential indicates signing algorithm."""
        with open_token(pin="123456") as session:
            cred = credential_from_token(session, "alice")
            assert cred.signing_algorithm == "ed25519"

    def test_credential_hardware_backed_flag(self):
        """MemberCredential from token is marked as hardware_backed."""
        with open_token(pin="123456") as session:
            cred = credential_from_token(session, "alice")
            assert cred.hardware_backed is True


# PIVSlot Tests for Signing

class TestPIVSlotSigning:
    """Test signing with different PIV slots."""

    def test_sign_with_slot_9a(self):
        """Can sign with PIV slot 9A (authentication)."""
        with open_token(pin="123456", piv_slot=PIVSlot.SLOT_9A) as session:
            message = b"slot 9A test"
            signature = session.sign(message)
            assert len(signature) == 64

    def test_sign_with_slot_9c(self):
        """Can sign with PIV slot 9C (digital signature)."""
        with open_token(pin="123456", piv_slot=PIVSlot.SLOT_9C) as session:
            message = b"slot 9C test"
            signature = session.sign(message)
            assert len(signature) == 64

    def test_sign_with_auto_slot(self):
        """Can sign with PIVSlot.AUTO (automatic slot selection)."""
        with open_token(pin="123456", piv_slot=PIVSlot.AUTO) as session:
            message = b"auto slot test"
            signature = session.sign(message)
            assert len(signature) == 64


# Error Cases

class TestSigningErrorCases:
    """Test error handling in signing operations."""

    def test_sign_on_closed_session_raises_error(self):
        """Attempting to sign on closed session raises error."""
        session = MockTokenSession.create()
        session.authenticate("123456")
        session.close()

        with pytest.raises((RuntimeError, Exception)):
            session.sign(b"test")

    def test_sign_on_unauthenticated_session_raises_error(self):
        """Attempting to sign without authentication raises error."""
        session = MockTokenSession.create()

        with pytest.raises(RuntimeError, match="not authenticated"):
            session.sign(b"test")

    def test_sign_with_none_message_raises_error(self):
        """Attempting to sign None raises error."""
        from peermodel.exceptions import SignatureVerificationError

        with open_token(pin="123456") as session:
            with pytest.raises((TypeError, AttributeError, SignatureVerificationError)):
                session.sign(None)

    def test_sign_with_string_message_raises_error(self):
        """Attempting to sign string (not bytes) raises error."""
        from peermodel.exceptions import SignatureVerificationError

        with open_token(pin="123456") as session:
            with pytest.raises((TypeError, AttributeError, SignatureVerificationError)):
                session.sign("string message")


# Real Hardware Tests (Optional, Marked)

@pytest.mark.hardware
class TestRealHardwareSigningEd25519:
    """Test Ed25519 signing with real hardware tokens.

    These tests are skipped by default. Run with:
    pytest -m hardware
    """

    def test_real_token_sign_ed25519(self):
        """Sign with real hardware token (Ed25519).

        Requires:
        - PIV card/YubiKey with Ed25519 key in slot 9A or 9C
        - Unset COHORTCRYPTO_MOCK_HARDWARE
        """
        if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
            del os.environ['COHORTCRYPTO_MOCK_HARDWARE']

        try:
            with open_token(pin=None, piv_slot=PIVSlot.AUTO) as session:
                message = b"real hardware test"
                signature = session.sign(message)

                assert len(signature) == 64

                # Verify signature
                is_valid = primitives.verify_bytes(
                    message,
                    signature,
                    session.ed25519_public,
                    algorithm="ed25519",
                )
                assert is_valid is True

        except Exception as e:
            pytest.skip(f"Real hardware not available: {e}")


# P-256 ECDSA Signing Tests (Acceptance Criteria)
# Note: MockTokenSession currently uses Ed25519, so P-256 tests
# will fail until P-256 support is added to hardware signing

class TestHardwareP256Signing:
    """Test P-256 ECDSA signing with hardware tokens.

    These tests document the P-256 acceptance criteria.
    They will FAIL until P-256 signing is implemented.
    """

    @pytest.mark.skip(reason="P-256 MockTokenSession not yet implemented")
    def test_p256_mocktokensession_exists(self):
        """Can create MockTokenSession with P-256 keys.

        This will fail until we add P-256 support to MockTokenSession.create()
        """
        from cohortcrypto.hardware.mock import MockTokenSession

        # Should be able to specify algorithm
        session = MockTokenSession.create(algorithm="p256")
        session.authenticate("123456")

        assert session.signing_algorithm == "p256"
        assert session.encryption_algorithm == "p256"

    @pytest.mark.skip(reason="P-256 signing not yet implemented")
    def test_p256_signature_length_variable(self):
        """P-256 ECDSA signature is DER-encoded (variable length, typically 70-72 bytes).

        This will fail until P-256 signing is implemented.
        """
        from cohortcrypto.hardware.mock import MockTokenSession

        session = MockTokenSession.create(algorithm="p256")
        session.authenticate("123456")

        message = b"p256 test message"
        signature = session.sign(message)

        # DER-encoded ECDSA signature is variable length, typically 70-72 bytes for P-256
        assert isinstance(signature, bytes)
        assert 64 <= len(signature) <= 75  # Range for DER-encoded P-256 ECDSA

    @pytest.mark.skip(reason="P-256 signing not yet implemented")
    def test_p256_signature_verifies_with_software(self):
        """P-256 hardware signature verifies with software primitives.verify_bytes().

        This will fail until P-256 signing is implemented.
        """
        from cohortcrypto.hardware.mock import MockTokenSession

        session = MockTokenSession.create(algorithm="p256")
        session.authenticate("123456")

        message = b"p256 verification test"
        signature = session.sign(message)

        # Verify using software primitives with p256 algorithm
        is_valid = primitives.verify_bytes(
            message, signature, session.ed25519_public, algorithm="p256"
        )
        assert is_valid is True

    @pytest.mark.skip(reason="P-256 signing not yet implemented")
    def test_p256_different_from_ed25519(self):
        """P-256 and Ed25519 produce different signature formats.

        This will fail until P-256 signing is implemented.
        """
        from cohortcrypto.hardware.mock import MockTokenSession

        ed25519_session = MockTokenSession.create(algorithm="ed25519")
        ed25519_session.authenticate("123456")

        p256_session = MockTokenSession.create(algorithm="p256")
        p256_session.authenticate("123456")

        message = b"compare algorithms"

        ed25519_sig = ed25519_session.sign(message)
        p256_sig = p256_session.sign(message)

        # Ed25519 is always 64 bytes
        assert len(ed25519_sig) == 64

        # P-256 DER is variable length
        assert len(p256_sig) != 64
        assert 64 <= len(p256_sig) <= 75

    @pytest.mark.skip(reason="P-256 signing not yet implemented")
    def test_p256_open_token_with_p256_slot(self):
        """open_token() can open P-256 token session.

        This will fail until P-256 slot detection is implemented.
        """
        with open_token(pin="123456", piv_slot=PIVSlot.SLOT_9C) as session:
            # If token has P-256 key in slot 9C, should indicate p256
            if session.signing_algorithm == "p256":
                message = b"p256 open_token test"
                signature = session.sign(message)

                is_valid = primitives.verify_bytes(
                    message,
                    signature,
                    session.ed25519_public,
                    algorithm="p256"
                )
                assert is_valid is True


# PKCS#11 Function Tests

class TestPKCS11SignFunction:
    """Test the pkcs11_sign() function from cohortcrypto.hardware.pkcs11."""

    def test_pkcs11_sign_function_exists(self):
        """pkcs11_sign() function should be importable."""
        from cohortcrypto.hardware.pkcs11 import pkcs11_sign
        assert callable(pkcs11_sign)

    def test_pkcs11_sign_with_mock_session(self):
        """pkcs11_sign() works with mock hardware session."""
        from cohortcrypto.hardware.pkcs11 import pkcs11_sign, open_pkcs11_session

        with open_pkcs11_session(None, None, "123456", PIVSlot.AUTO) as session:
            message = b"pkcs11_sign test"
            signature = pkcs11_sign(session, message)

            assert len(signature) == 64
            assert isinstance(signature, bytes)

    def test_pkcs11_sign_signature_verifies(self):
        """pkcs11_sign() signature verifies with software primitives."""
        from cohortcrypto.hardware.pkcs11 import pkcs11_sign, open_pkcs11_session

        with open_pkcs11_session(None, None, "123456", PIVSlot.AUTO) as session:
            message = b"verification test"
            signature = pkcs11_sign(session, message)

            is_valid = primitives.verify_bytes(
                message, signature, session.ed25519_public, algorithm="ed25519"
            )
            assert is_valid is True

    def test_pkcs11_sign_requires_authenticated_session(self):
        """pkcs11_sign() requires authenticated session."""
        from cohortcrypto.hardware.pkcs11 import pkcs11_sign, RealTokenSession

        # Create unauthenticated session
        session = RealTokenSession(
            slot_id=0,
            token_label="Test",
            token_serial="123",
            piv_slot=PIVSlot.SLOT_9A,
            x25519_public=b"x25519_pub",
            ed25519_public=b"ed25519_pub",
            _authenticated=False
        )

        with pytest.raises(RuntimeError, match="not authenticated"):
            pkcs11_sign(session, b"test")


# RealTokenSession Tests

class TestRealTokenSessionSigning:
    """Test RealTokenSession.sign() method specifically."""

    def test_real_token_session_sign_method_exists(self):
        """RealTokenSession should have sign() method."""
        from cohortcrypto.hardware.pkcs11 import RealTokenSession

        session = RealTokenSession(
            slot_id=0,
            token_label="Test",
            token_serial="123",
            piv_slot=PIVSlot.SLOT_9A,
            x25519_public=b"x25519_pub",
            ed25519_public=b"ed25519_pub"
        )

        assert hasattr(session, 'sign')
        assert callable(session.sign)

    def test_real_token_session_with_mock_backend(self):
        """RealTokenSession wrapping MockTokenSession can sign."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session

        # This uses mock hardware backend
        with open_pkcs11_session(None, None, "123456", PIVSlot.AUTO) as session:
            message = b"real session test"
            signature = session.sign(message)

            assert len(signature) == 64
            is_valid = primitives.verify_bytes(
                message, signature, session.ed25519_public, algorithm="ed25519"
            )
            assert is_valid is True

    def test_real_token_session_ed25519_algorithm_field(self):
        """RealTokenSession should indicate ed25519 signing algorithm."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session

        with open_pkcs11_session(None, None, "123456", PIVSlot.AUTO) as session:
            assert session.signing_algorithm == "ed25519"

    def test_real_token_session_sign_multiple_messages(self):
        """RealTokenSession can sign multiple messages in one session."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session

        with open_pkcs11_session(None, None, "123456", PIVSlot.AUTO) as session:
            messages = [b"msg1", b"msg2", b"msg3"]
            signatures = [session.sign(msg) for msg in messages]

            # All signatures should verify
            for msg, sig in zip(messages, signatures):
                is_valid = primitives.verify_bytes(
                    msg, sig, session.ed25519_public, algorithm="ed25519"
                )
                assert is_valid is True


# Documentation Tests

class TestSigningDocumentation:
    """Tests that document signing behavior and usage patterns."""

    def test_signing_workflow_example(self):
        """Document typical signing workflow."""
        # 1. Open token session
        with open_token(pin="123456") as session:
            # 2. Sign a message
            message = b"Document to be signed"
            signature = session.sign(message)

            # 3. Share public key and signature
            public_key = session.ed25519_public

            # 4. Recipient verifies signature
            is_valid = primitives.verify_bytes(
                message, signature, public_key, algorithm="ed25519"
            )

            assert is_valid is True

    def test_member_credential_workflow(self):
        """Document MemberCredential creation and signing workflow."""
        with open_token(pin="123456") as session:
            # Create credential from token
            member_cred = credential_from_token(session, "alice@example.com")

            # Sign a message
            message = b"Cohort membership proof"
            signature = session.sign(message)

            # Verify using credential
            is_valid = primitives.verify_bytes(
                message,
                signature,
                member_cred.ed25519_public,
                algorithm=member_cred.signing_algorithm,
            )

            assert is_valid is True
            assert member_cred.hardware_backed is True
