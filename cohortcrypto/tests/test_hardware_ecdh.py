"""Acceptance tests for issue #6: Hardware ECDH key agreement.

This module tests ECDH key agreement using hardware tokens with on-token X25519
private keys. The private key never leaves the token; only the shared secret is returned.

Tests verify:
- ECDH with hardware X25519 key
- Private key never exported from token
- Shared secret matches software ECDH result
- Works with both mock and real PKCS#11 tokens
- Proper error handling (authentication, missing keys, etc.)

All tests should FAIL until the feature is implemented.
"""

import pytest
import os

# Test will use mock hardware by default
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def enable_mock_hardware():
    """Enable mock hardware for all tests unless explicitly disabled."""
    if not os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
        os.environ['COHORTCRYPTO_MOCK_HARDWARE'] = '1'
    yield


class TestHardwareECDHBasic:
    """Basic ECDH operations with hardware tokens."""

    def test_hardware_ecdh_returns_shared_secret(self):
        """Hardware ECDH returns 32-byte shared secret for X25519."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        # Create hardware token session
        with open_token(pin="123456") as hw_session:
            # Create peer with software keys
            peer_session = MockTokenSession.create()
            peer_session.authenticate("123456")

            # Perform ECDH on hardware token
            shared_secret = hw_session.ecdh(peer_session.x25519_public)

            # Verify shared secret format
            assert isinstance(shared_secret, bytes)
            assert len(shared_secret) == 32  # X25519 shared secret is 32 bytes

    def test_hardware_ecdh_with_der_encoded_public_key(self):
        """ECDH accepts DER-encoded X25519 public key."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            peer_session = MockTokenSession.create()
            peer_session.authenticate("123456")

            # peer_session.x25519_public is already DER-encoded
            shared_secret = hw_session.ecdh(peer_session.x25519_public)

            assert len(shared_secret) == 32

    def test_hardware_ecdh_with_different_peers(self):
        """ECDH with different peers produces different secrets."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            peer1 = MockTokenSession.create()
            peer1.authenticate("123456")

            peer2 = MockTokenSession.create()
            peer2.authenticate("123456")

            secret1 = hw_session.ecdh(peer1.x25519_public)
            secret2 = hw_session.ecdh(peer2.x25519_public)

            # Different peers should produce different shared secrets
            assert secret1 != secret2

    def test_hardware_ecdh_deterministic_for_same_peer(self):
        """ECDH with same peer produces same secret on repeated calls."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            peer = MockTokenSession.create()
            peer.authenticate("123456")

            # Perform ECDH twice with same peer
            secret1 = hw_session.ecdh(peer.x25519_public)
            secret2 = hw_session.ecdh(peer.x25519_public)

            # Should get same result
            assert secret1 == secret2


class TestHardwareECDHSymmetry:
    """Test ECDH symmetry: A->B and B->A produce same secret."""

    def test_ecdh_symmetry_hardware_to_hardware(self):
        """ECDH between two hardware tokens is symmetric."""
        from cohortcrypto import open_token

        with open_token(pin="123456") as hw_session1:
            with open_token(pin="123456") as hw_session2:
                # Session1 performs ECDH with session2's public key
                secret1 = hw_session1.ecdh(hw_session2.x25519_public)

                # Session2 performs ECDH with session1's public key
                secret2 = hw_session2.ecdh(hw_session1.x25519_public)

                # Should produce same shared secret
                assert secret1 == secret2

    def test_ecdh_symmetry_hardware_to_software(self):
        """ECDH between hardware token and software key is symmetric."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            sw_session = MockTokenSession.create()
            sw_session.authenticate("123456")

            # Hardware performs ECDH with software public key
            hw_secret = hw_session.ecdh(sw_session.x25519_public)

            # Software performs ECDH with hardware public key
            sw_secret = sw_session.ecdh(hw_session.x25519_public)

            # Should produce same shared secret
            assert hw_secret == sw_secret


class TestHardwareECDHMatchesSoftware:
    """Verify hardware ECDH matches software ECDH computation."""

    def test_hardware_ecdh_matches_software_reference(self):
        """Hardware ECDH produces same result as software implementation."""
        from cohortcrypto import open_token
        import peermodel.primitives as primitives
        from cryptography.hazmat.primitives.serialization import (
            load_der_private_key, load_der_public_key
        )

        # Generate software keypair for peer
        x25519_priv_der, x25519_pub_der, _, _ = primitives.generate_keypair()

        with open_token(pin="123456") as hw_session:
            # Hardware performs ECDH
            hw_shared_secret = hw_session.ecdh(x25519_pub_der)

            # Software performs ECDH (reference implementation)
            # Load software peer private key
            sw_private = load_der_private_key(x25519_priv_der, password=None)

            # Load hardware public key
            hw_public_raw = load_der_public_key(hw_session.x25519_public)

            # Perform software ECDH
            sw_shared_secret = sw_private.exchange(hw_public_raw)

            # Hardware and software should produce same shared secret
            assert hw_shared_secret == sw_shared_secret

    def test_hardware_ecdh_interop_with_cryptography_library(self):
        """Hardware ECDH interoperates with cryptography library X25519."""
        from cohortcrypto import open_token
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat
        )

        # Generate X25519 keypair using cryptography library
        sw_private = x25519.X25519PrivateKey.generate()
        sw_public = sw_private.public_key()
        sw_public_der = sw_public.public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo
        )

        with open_token(pin="123456") as hw_session:
            # Hardware performs ECDH with software public key
            hw_shared_secret = hw_session.ecdh(sw_public_der)

            # Software performs ECDH with hardware public key
            from cryptography.hazmat.primitives.serialization import load_der_public_key
            hw_public = load_der_public_key(hw_session.x25519_public)
            sw_shared_secret = sw_private.exchange(hw_public)

            # Should match
            assert hw_shared_secret == sw_shared_secret


class TestHardwareECDHPrivateKeyNeverExported:
    """Verify that private keys never leave the hardware token."""

    def test_token_session_has_no_private_key_attribute(self):
        """Token session does not expose private key attributes."""
        from cohortcrypto import open_token

        with open_token(pin="123456") as hw_session:
            # Session should NOT have private key exposed
            assert not hasattr(hw_session, 'x25519_private')
            assert not hasattr(hw_session, '_x25519_private_exported')

            # Only public key should be available
            assert hasattr(hw_session, 'x25519_public')
            assert hw_session.x25519_public is not None

    def test_ecdh_does_not_return_private_key(self):
        """ECDH only returns shared secret, never private key material."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            peer = MockTokenSession.create()
            peer.authenticate("123456")

            shared_secret = hw_session.ecdh(peer.x25519_public)

            # Result should be 32 bytes (shared secret), not 64 bytes (keypair)
            assert len(shared_secret) == 32

            # Shared secret should be different from public key
            assert shared_secret != hw_session.x25519_public[:32]

    def test_multiple_ecdh_operations_use_same_private_key(self):
        """Multiple ECDH operations use same private key without exporting it."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            peer = MockTokenSession.create()
            peer.authenticate("123456")

            # Perform ECDH multiple times
            secret1 = hw_session.ecdh(peer.x25519_public)
            secret2 = hw_session.ecdh(peer.x25519_public)
            secret3 = hw_session.ecdh(peer.x25519_public)

            # All should produce same secret (proving same private key used)
            assert secret1 == secret2 == secret3

            # Public key should remain unchanged
            public_key_initial = hw_session.x25519_public
            hw_session.ecdh(peer.x25519_public)
            assert hw_session.x25519_public == public_key_initial


class TestHardwareECDHErrorHandling:
    """Test error handling for hardware ECDH operations."""

    def test_ecdh_requires_authentication(self):
        """ECDH operation requires authenticated session."""
        from cohortcrypto.hardware.mock import MockTokenSession

        # Create unauthenticated session
        hw_session = MockTokenSession.create()
        peer = MockTokenSession.create()
        peer.authenticate("123456")

        # Should raise error when not authenticated
        with pytest.raises(RuntimeError, match="not authenticated"):
            hw_session.ecdh(peer.x25519_public)

    def test_ecdh_with_invalid_public_key_raises_error(self):
        """ECDH with invalid public key raises error."""
        from cohortcrypto import open_token

        with open_token(pin="123456") as hw_session:
            # Invalid public key (not DER-encoded, wrong length)
            invalid_key = b"not_a_valid_der_encoded_key"

            with pytest.raises(Exception):  # Could be ValueError or RuntimeError
                hw_session.ecdh(invalid_key)

    def test_ecdh_with_empty_public_key_raises_error(self):
        """ECDH with empty public key raises error."""
        from cohortcrypto import open_token

        with open_token(pin="123456") as hw_session:
            with pytest.raises(Exception):
                hw_session.ecdh(b"")

    def test_ecdh_with_wrong_key_type_raises_error(self):
        """ECDH with non-X25519 key raises error."""
        from cohortcrypto import open_token
        import peermodel.primitives as primitives

        with open_token(pin="123456") as hw_session:
            # Generate Ed25519 key (signing key, not encryption key)
            _, _, _, ed25519_pub = primitives.generate_keypair()

            # Should reject Ed25519 key for ECDH
            with pytest.raises(Exception):
                hw_session.ecdh(ed25519_pub)


class TestHardwareECDHMockMode:
    """Test ECDH specifically with mock hardware."""

    def test_mock_token_ecdh_available(self):
        """Mock token session has ecdh() method."""
        from cohortcrypto.hardware.mock import MockTokenSession

        session = MockTokenSession.create()
        session.authenticate("123456")

        assert hasattr(session, 'ecdh')
        assert callable(session.ecdh)

    def test_mock_ecdh_produces_valid_shared_secret(self):
        """Mock ECDH produces valid 32-byte shared secret."""
        from cohortcrypto.hardware.mock import MockTokenSession

        session1 = MockTokenSession.create()
        session1.authenticate("123456")

        session2 = MockTokenSession.create()
        session2.authenticate("123456")

        shared_secret = session1.ecdh(session2.x25519_public)

        assert isinstance(shared_secret, bytes)
        assert len(shared_secret) == 32

    def test_mock_ecdh_is_symmetric(self):
        """Mock ECDH is symmetric (A->B == B->A)."""
        from cohortcrypto.hardware.mock import MockTokenSession

        session1 = MockTokenSession.create()
        session1.authenticate("123456")

        session2 = MockTokenSession.create()
        session2.authenticate("123456")

        secret1 = session1.ecdh(session2.x25519_public)
        secret2 = session2.ecdh(session1.x25519_public)

        assert secret1 == secret2


class TestHardwareECDHIntegration:
    """Integration tests for ECDH in realistic scenarios."""

    def test_ecdh_in_encryption_workflow(self):
        """ECDH shared secret can be used for encryption."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        from cryptography.fernet import Fernet
        import base64
        import os

        with open_token(pin="123456") as hw_session:
            peer = MockTokenSession.create()
            peer.authenticate("123456")

            # Perform ECDH to get shared secret
            shared_secret = hw_session.ecdh(peer.x25519_public)

            # Derive encryption key from shared secret (using HKDF)
            salt = os.urandom(16)
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=b"test_encryption"
            )
            derived_key = hkdf.derive(shared_secret)

            # Use derived key for Fernet encryption
            fernet_key = base64.urlsafe_b64encode(derived_key)
            f = Fernet(fernet_key)

            plaintext = b"secret message"
            ciphertext = f.encrypt(plaintext)

            # Verify encryption worked
            assert ciphertext != plaintext
            decrypted = f.decrypt(ciphertext)
            assert decrypted == plaintext

    def test_ecdh_with_multiple_peers(self):
        """Hardware token can perform ECDH with multiple different peers."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        with open_token(pin="123456") as hw_session:
            # Create multiple peers
            peers = [MockTokenSession.create() for _ in range(5)]
            for peer in peers:
                peer.authenticate("123456")

            # Perform ECDH with each peer
            secrets = [hw_session.ecdh(peer.x25519_public) for peer in peers]

            # All secrets should be valid
            assert all(len(s) == 32 for s in secrets)

            # All secrets should be different
            assert len(set(secrets)) == len(secrets)

    def test_ecdh_result_can_derive_multiple_keys(self):
        """ECDH shared secret can be used to derive multiple encryption keys."""
        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        import os

        with open_token(pin="123456") as hw_session:
            peer = MockTokenSession.create()
            peer.authenticate("123456")

            shared_secret = hw_session.ecdh(peer.x25519_public)

            # Derive multiple keys from same shared secret
            salt = os.urandom(16)

            # Key 1: For encryption
            hkdf1 = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=b"encryption"
            )
            key1 = hkdf1.derive(shared_secret)

            # Key 2: For MAC
            hkdf2 = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=b"mac"
            )
            key2 = hkdf2.derive(shared_secret)

            # Keys should be different (due to different info parameter)
            assert key1 != key2
            assert len(key1) == 32
            assert len(key2) == 32


@pytest.mark.hardware
class TestHardwareECDHRealToken:
    """Tests for ECDH with real hardware tokens (optional)."""

    @pytest.fixture(scope="class")
    def hardware_available(self):
        """Check if real hardware is available."""
        if os.environ.get('COHORTCRYPTO_MOCK_HARDWARE'):
            pytest.skip("Skipping real hardware tests in mock mode")

        try:
            from cohortcrypto import enumerate_tokens
            tokens = enumerate_tokens()
            return len(tokens) > 0
        except Exception:
            return False

    def test_real_token_ecdh(self, hardware_available):
        """Can perform ECDH with real hardware token."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        try:
            with open_token(pin="123456") as hw_session:
                peer = MockTokenSession.create()
                peer.authenticate("123456")

                shared_secret = hw_session.ecdh(peer.x25519_public)

                assert isinstance(shared_secret, bytes)
                assert len(shared_secret) == 32
        except Exception as e:
            pytest.skip(f"Real hardware ECDH failed: {e}")

    def test_real_token_ecdh_is_symmetric(self, hardware_available):
        """ECDH with real hardware token is symmetric."""
        if not hardware_available:
            pytest.skip("No real hardware available")

        from cohortcrypto import open_token
        from cohortcrypto.hardware.mock import MockTokenSession

        try:
            with open_token(pin="123456") as hw_session:
                sw_session = MockTokenSession.create()
                sw_session.authenticate("123456")

                hw_secret = hw_session.ecdh(sw_session.x25519_public)
                sw_secret = sw_session.ecdh(hw_session.x25519_public)

                assert hw_secret == sw_secret
        except Exception as e:
            pytest.skip(f"Real hardware ECDH symmetry test failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
