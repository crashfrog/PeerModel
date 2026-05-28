"""Acceptance tests for issue #6: Software ECDH primitive implementation.

This module tests the `perform_ecdh()` function in cohortcrypto.primitives,
which provides the software-based ECDH reference implementation.

The function is used by:
- Mock hardware (to simulate on-token ECDH)
- Software identity managers
- Test validation (to verify hardware ECDH matches software)

All tests should FAIL until perform_ecdh() is implemented.
"""

import pytest


class TestPerformECDHBasic:
    """Basic ECDH key agreement tests."""

    def test_perform_ecdh_exists(self):
        """perform_ecdh function is importable."""
        from cohortcrypto.primitives import perform_ecdh
        assert callable(perform_ecdh)

    def test_perform_ecdh_returns_shared_secret(self):
        """perform_ecdh returns 32-byte shared secret for X25519."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate two X25519 keypairs
        priv1_der, pub1_der, _, _ = primitives.generate_keypair()
        priv2_der, pub2_der, _, _ = primitives.generate_keypair()

        # Perform ECDH
        shared_secret = perform_ecdh(priv1_der, pub2_der)

        # Verify format
        assert isinstance(shared_secret, bytes)
        assert len(shared_secret) == 32  # X25519 shared secret

    def test_perform_ecdh_is_symmetric(self):
        """ECDH is symmetric: A->B secret equals B->A secret."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate two keypairs
        priv_a_der, pub_a_der, _, _ = primitives.generate_keypair()
        priv_b_der, pub_b_der, _, _ = primitives.generate_keypair()

        # A performs ECDH with B's public key
        secret_ab = perform_ecdh(priv_a_der, pub_b_der)

        # B performs ECDH with A's public key
        secret_ba = perform_ecdh(priv_b_der, pub_a_der)

        # Should produce same shared secret
        assert secret_ab == secret_ba

    def test_perform_ecdh_with_different_peers(self):
        """ECDH with different peers produces different secrets."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # One private key
        priv_der, _, _, _ = primitives.generate_keypair()

        # Two different peer public keys
        _, pub1_der, _, _ = primitives.generate_keypair()
        _, pub2_der, _, _ = primitives.generate_keypair()

        # ECDH with each peer
        secret1 = perform_ecdh(priv_der, pub1_der)
        secret2 = perform_ecdh(priv_der, pub2_der)

        # Should be different
        assert secret1 != secret2

    def test_perform_ecdh_is_deterministic(self):
        """ECDH with same inputs produces same output."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        priv_der, _, _, _ = primitives.generate_keypair()
        _, pub_der, _, _ = primitives.generate_keypair()

        # Perform ECDH twice
        secret1 = perform_ecdh(priv_der, pub_der)
        secret2 = perform_ecdh(priv_der, pub_der)

        # Should be identical
        assert secret1 == secret2


class TestPerformECDHX25519:
    """Test ECDH specifically with X25519 keys."""

    def test_perform_ecdh_x25519_keypairs(self):
        """perform_ecdh works with X25519 keypairs."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate X25519 keypairs (first two values from generate_keypair)
        x25519_priv, x25519_pub, _, _ = primitives.generate_keypair()
        _, peer_pub, _, _ = primitives.generate_keypair()

        shared_secret = perform_ecdh(x25519_priv, peer_pub)

        assert len(shared_secret) == 32

    def test_perform_ecdh_matches_cryptography_library(self):
        """perform_ecdh produces same result as cryptography library."""
        from cohortcrypto.primitives import perform_ecdh
        from cryptography.hazmat.primitives.asymmetric import x25519
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption
        )

        # Generate keypairs with cryptography library
        priv_a = x25519.X25519PrivateKey.generate()

        priv_b = x25519.X25519PrivateKey.generate()
        pub_b = priv_b.public_key()

        # Serialize to DER
        priv_a_der = priv_a.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )
        pub_b_der = pub_b.public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo
        )

        # Perform ECDH with our implementation
        our_secret = perform_ecdh(priv_a_der, pub_b_der)

        # Perform ECDH with cryptography library (reference)
        ref_secret = priv_a.exchange(pub_b)

        # Should match
        assert our_secret == ref_secret

    def test_perform_ecdh_interop_with_peermodel_primitives(self):
        """perform_ecdh works with peermodel.primitives generated keys."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives
        from cryptography.hazmat.primitives.serialization import (
            load_der_private_key, load_der_public_key
        )

        # Generate keypairs with peermodel
        priv_a_der, pub_a_der, _, _ = primitives.generate_keypair()
        priv_b_der, pub_b_der, _, _ = primitives.generate_keypair()

        # Perform ECDH with our implementation
        our_secret = perform_ecdh(priv_a_der, pub_b_der)

        # Verify with cryptography library
        priv_a = load_der_private_key(priv_a_der, password=None)
        pub_b = load_der_public_key(pub_b_der)

        ref_secret = priv_a.exchange(pub_b)

        # Should match cryptography library
        assert our_secret == ref_secret


class TestPerformECDHP256:
    """Test ECDH with P-256 keys."""

    def test_perform_ecdh_p256_keypairs(self):
        """perform_ecdh works with P-256 keypairs."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate P-256 keypairs
        _, _, priv_der, pub_der = primitives.generate_software_keypair(algorithm="p256")

        # Generate peer keypair
        _, _, peer_priv_der, peer_pub_der = primitives.generate_software_keypair(algorithm="p256")

        # Perform ECDH
        shared_secret = perform_ecdh(priv_der, peer_pub_der)

        # P-256 ECDH produces 32-byte shared secret
        assert isinstance(shared_secret, bytes)
        assert len(shared_secret) == 32

    def test_perform_ecdh_p256_is_symmetric(self):
        """P-256 ECDH is symmetric."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate two P-256 keypairs
        _, _, priv_a_der, pub_a_der = primitives.generate_software_keypair(algorithm="p256")
        _, _, priv_b_der, pub_b_der = primitives.generate_software_keypair(algorithm="p256")

        # A->B
        secret_ab = perform_ecdh(priv_a_der, pub_b_der)

        # B->A
        secret_ba = perform_ecdh(priv_b_der, pub_a_der)

        # Should match
        assert secret_ab == secret_ba

    def test_perform_ecdh_p256_matches_cryptography_library(self):
        """P-256 ECDH matches cryptography library implementation."""
        from cohortcrypto.primitives import perform_ecdh
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat, PrivateFormat, NoEncryption
        )

        # Generate P-256 keypairs with cryptography library
        priv_a = ec.generate_private_key(ec.SECP256R1())

        priv_b = ec.generate_private_key(ec.SECP256R1())
        pub_b = priv_b.public_key()

        # Serialize to DER
        priv_a_der = priv_a.private_bytes(
            encoding=Encoding.DER,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )
        pub_b_der = pub_b.public_bytes(
            encoding=Encoding.DER,
            format=PublicFormat.SubjectPublicKeyInfo
        )

        # Perform ECDH with our implementation
        our_secret = perform_ecdh(priv_a_der, pub_b_der)

        # Perform ECDH with cryptography library (reference)
        ref_secret = priv_a.exchange(ec.ECDH(), pub_b)

        # Should match
        assert our_secret == ref_secret


class TestPerformECDHErrorHandling:
    """Test error handling for perform_ecdh."""

    def test_perform_ecdh_with_invalid_private_key(self):
        """perform_ecdh raises error for invalid private key."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Valid public key
        _, pub_der, _, _ = primitives.generate_keypair()

        # Invalid private key
        invalid_priv = b"not_a_valid_key"

        with pytest.raises(Exception):  # Could be ValueError or TypeError
            perform_ecdh(invalid_priv, pub_der)

    def test_perform_ecdh_with_invalid_public_key(self):
        """perform_ecdh raises error for invalid public key."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Valid private key
        priv_der, _, _, _ = primitives.generate_keypair()

        # Invalid public key
        invalid_pub = b"not_a_valid_key"

        with pytest.raises(Exception):
            perform_ecdh(priv_der, invalid_pub)

    def test_perform_ecdh_with_empty_keys(self):
        """perform_ecdh raises error for empty keys."""
        from cohortcrypto.primitives import perform_ecdh

        with pytest.raises(Exception):
            perform_ecdh(b"", b"")

    def test_perform_ecdh_with_mismatched_key_types(self):
        """perform_ecdh raises error when key types don't match."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # X25519 private key
        x25519_priv, _, _, _ = primitives.generate_keypair()

        # Ed25519 public key (wrong type - signing not encryption)
        _, _, _, ed25519_pub = primitives.generate_keypair()

        with pytest.raises(Exception):
            perform_ecdh(x25519_priv, ed25519_pub)

    def test_perform_ecdh_x25519_with_p256_key_fails(self):
        """perform_ecdh fails when mixing X25519 and P-256 keys."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # X25519 private key
        x25519_priv, _, _, _ = primitives.generate_keypair()

        # P-256 public key
        _, _, _, p256_pub = primitives.generate_software_keypair(algorithm="p256")

        with pytest.raises(Exception):
            perform_ecdh(x25519_priv, p256_pub)


class TestPerformECDHIntegration:
    """Integration tests for perform_ecdh in realistic scenarios."""

    def test_perform_ecdh_for_key_derivation(self):
        """perform_ecdh shared secret can be used for key derivation."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        from cryptography.hazmat.primitives import hashes
        import os as os_module

        # Generate keypairs
        priv_a_der, _, _, _ = primitives.generate_keypair()
        _, pub_b_der, _, _ = primitives.generate_keypair()

        # Perform ECDH
        shared_secret = perform_ecdh(priv_a_der, pub_b_der)

        # Derive encryption key from shared secret
        salt = os_module.urandom(16)
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"test"
        )
        derived_key = hkdf.derive(shared_secret)

        # Should produce valid 32-byte key
        assert len(derived_key) == 32
        assert derived_key != shared_secret  # HKDF transforms the secret

    def test_perform_ecdh_multiple_peers(self):
        """perform_ecdh produces unique secrets for different peers."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # One sender
        sender_priv, _, _, _ = primitives.generate_keypair()

        # Multiple recipients
        secrets = []
        for _ in range(5):
            _, recipient_pub, _, _ = primitives.generate_keypair()
            secret = perform_ecdh(sender_priv, recipient_pub)
            secrets.append(secret)

        # All secrets should be unique
        assert len(set(secrets)) == len(secrets)

    def test_perform_ecdh_matches_encrypt_to_recipient_behavior(self):
        """perform_ecdh behavior matches peermodel.primitives.encrypt_to_recipient ECDH."""
        from cohortcrypto.primitives import perform_ecdh
        import peermodel.primitives as primitives

        # Generate recipient keypair
        recipient_priv_der, recipient_pub_der, _, _ = primitives.generate_keypair()

        # Generate ephemeral keypair (like encrypt_to_recipient does)
        ephemeral_priv_der, ephemeral_pub_der, _, _ = primitives.generate_keypair()

        # Perform ECDH: ephemeral private + recipient public
        # (This is what encrypt_to_recipient does internally)
        shared_secret = perform_ecdh(ephemeral_priv_der, recipient_pub_der)

        # Verify recipient can recover same secret
        recipient_secret = perform_ecdh(recipient_priv_der, ephemeral_pub_der)

        # Secrets should match (ECDH symmetry)
        assert shared_secret == recipient_secret


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
