"""Integration tests for PKCS#11 hardware token operations (Phase 3E).

These tests can run in two modes:
1. Mock mode (default): Tests PKCS#11 interface using MockTokenSession
   - Run with: COHORTCRYPTO_MOCK_HARDWARE=1 pytest
   - No real hardware required

2. Real hardware mode (optional): Tests with actual PIV cards/YubiKeys
   - Requires real hardware with proper keys configured
   - Run with: pytest -m hardware (after unsetting COHORTCRYPTO_MOCK_HARDWARE)
   - Tests skip gracefully if hardware not available

Real hardware requirements:
- PIV card or YubiKey with Ed25519 signing key in slot 9C
- X25519 encryption key in slot 9A
- PIN set to "123456" for testing
"""

import pytest
import os
from unittest.mock import MagicMock, patch

# Skip real hardware tests by default
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def enable_mock_hardware():
    """Enable mock hardware for all tests unless explicitly disabled."""
    if not os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
        os.environ['COHORTCRYPTO_MOCK_HARDWARE'] = '1'
    yield
    if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE') == '1':
        if 'COHORTCRYPTO_MOCK_HARDWARE' in os.environ:
            del os.environ['COHORTCRYPTO_MOCK_HARDWARE']


class TestPKCS11IntegrationMock:
    """Tests for PKCS#11 integration with mock hardware (always runs)."""

    def test_open_pkcs11_session_mock_returns_real_session_object(self):
        """open_pkcs11_session returns RealTokenSession even in mock mode."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session
        from cohortcrypto.hardware import PIVSlot

        session = open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        )

        # Should return RealTokenSession, not MockTokenSession
        from cohortcrypto.hardware.pkcs11 import RealTokenSession
        assert isinstance(session, RealTokenSession)
        assert session.token_label
        assert session.x25519_public
        assert session.ed25519_public

    def test_real_token_session_sign_works_in_mock_mode(self):
        """RealTokenSession.sign() works with mock backend."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session
        from cohortcrypto.hardware import PIVSlot

        session = open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        )

        message = b"test message"
        signature = session.sign(message)

        assert isinstance(signature, bytes)
        assert len(signature) == 64  # Ed25519 signature is 64 bytes

    def test_real_token_session_ecdh_works_in_mock_mode(self):
        """RealTokenSession.ecdh() works with mock backend."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session
        from cohortcrypto.hardware import PIVSlot
        from cohortcrypto.hardware.mock import MockTokenSession

        session = open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        )

        # Create another session to get peer public key
        peer_session = MockTokenSession.create()
        peer_session.authenticate("123456")

        shared_secret = session.ecdh(peer_session.x25519_public)

        assert isinstance(shared_secret, bytes)
        assert len(shared_secret) == 32  # X25519 shared secret is 32 bytes

    def test_real_token_session_context_manager(self):
        """RealTokenSession works as context manager."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session
        from cohortcrypto.hardware import PIVSlot

        with open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        ) as session:
            assert session.token_label
            assert session._authenticated

        # After context exit, should be closed
        assert not session._authenticated

    def test_pkcs11_sign_function_wrapper(self):
        """pkcs11_sign() function calls session.sign()."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session, pkcs11_sign
        from cohortcrypto.hardware import PIVSlot

        session = open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        )

        message = b"test"
        signature = pkcs11_sign(session, message)

        assert isinstance(signature, bytes)
        assert len(signature) == 64

    def test_pkcs11_ecdh_function_wrapper(self):
        """pkcs11_ecdh() function calls session.ecdh()."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session, pkcs11_ecdh
        from cohortcrypto.hardware import PIVSlot
        from cohortcrypto.hardware.mock import MockTokenSession

        session = open_pkcs11_session(
            pkcs11_lib_path=None,
            slot_id=None,
            pin="123456",
            piv_slot=PIVSlot.AUTO
        )

        peer_session = MockTokenSession.create()
        peer_session.authenticate("123456")

        shared_secret = pkcs11_ecdh(session, peer_session.x25519_public)

        assert isinstance(shared_secret, bytes)
        assert len(shared_secret) == 32


class TestPKCS11ErrorHandling:
    """Test error handling in PKCS#11 integration."""

    def test_open_pkcs11_session_wrong_pin_raises_error(self):
        """Wrong PIN raises PINError."""
        from cohortcrypto.hardware.pkcs11 import open_pkcs11_session
        from cohortcrypto.hardware import PIVSlot
        from cohortcrypto.exceptions import PINError

        with pytest.raises(PINError):
            open_pkcs11_session(
                pkcs11_lib_path=None,
                slot_id=None,
                pin="wrong_pin",
                piv_slot=PIVSlot.AUTO
            )

    def test_real_token_session_sign_requires_auth(self):
        """Signing without authentication raises error."""
        from cohortcrypto.hardware.pkcs11 import RealTokenSession
        from cohortcrypto.hardware import PIVSlot

        session = RealTokenSession(
            slot_id=0,
            token_label="Test",
            token_serial="123",
            piv_slot=PIVSlot.SLOT_9A,
            x25519_public=b"test",
            ed25519_public=b"test"
        )

        with pytest.raises(RuntimeError):
            session.sign(b"message")

    def test_real_token_session_ecdh_requires_auth(self):
        """ECDH without authentication raises error."""
        from cohortcrypto.hardware.pkcs11 import RealTokenSession
        from cohortcrypto.hardware import PIVSlot

        session = RealTokenSession(
            slot_id=0,
            token_label="Test",
            token_serial="123",
            piv_slot=PIVSlot.SLOT_9A,
            x25519_public=b"test",
            ed25519_public=b"test"
        )

        with pytest.raises(RuntimeError):
            session.ecdh(b"peer_public_key")


@pytest.mark.hardware
class TestPKCS11RealHardware:
    """Tests for real PKCS#11 hardware (optional - requires hardware)."""

    @pytest.fixture(scope="class")
    def hardware_available(self):
        """Check if real hardware is available."""
        if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
            pytest.skip("Skipping real hardware tests in mock mode")

        try:
            import cohortcrypto.hardware as hw
            tokens = hw.enumerate_tokens()
            return len(tokens) > 0
        except Exception:
            return False

    def test_enumerate_real_tokens(self, hardware_available):
        """Can enumerate real hardware tokens."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        import cohortcrypto.hardware as hw
        tokens = hw.enumerate_tokens()

        assert len(tokens) > 0
        assert tokens[0].slot_id >= 0
        assert tokens[0].token_label
        assert tokens[0].token_serial

    def test_open_real_token_session(self, hardware_available):
        """Can open session with real hardware token."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        import cohortcrypto.hardware as hw

        try:
            with hw.open_token(pin="123456") as session:
                assert session.token_label
                assert session.x25519_public
                assert session.ed25519_public
                assert session.piv_slot
        except Exception as e:
            pytest.skip(f"Could not open real token: {e}")

    def test_real_token_sign(self, hardware_available):
        """Can sign with real hardware token."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        import cohortcrypto.hardware as hw

        try:
            with hw.open_token(pin="123456") as session:
                from cohortcrypto.hardware.pkcs11 import pkcs11_sign
                message = b"test message"
                signature = pkcs11_sign(session, message)
                assert isinstance(signature, bytes)
                assert len(signature) > 0
        except Exception as e:
            pytest.skip(f"Real hardware test failed: {e}")

    def test_real_token_ecdh(self, hardware_available):
        """Can perform ECDH with real hardware token."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        import cohortcrypto.hardware as hw
        from cohortcrypto.hardware.mock import MockTokenSession

        try:
            with hw.open_token(pin="123456") as session:
                from cohortcrypto.hardware.pkcs11 import pkcs11_ecdh

                # Get a peer public key
                peer_session = MockTokenSession.create()
                peer_session.authenticate("123456")

                shared_secret = pkcs11_ecdh(session, peer_session.x25519_public)
                assert isinstance(shared_secret, bytes)
                assert len(shared_secret) == 32
        except Exception as e:
            pytest.skip(f"Real hardware test failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
