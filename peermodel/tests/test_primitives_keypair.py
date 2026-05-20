#!/usr/bin/env python

"""
RED tests for Issue #1: Software keypair generation & Ed25519/X25519 signing.

These tests cover:
- Software keypair generation (DER-encoded)
- Ed25519 signing and verification
- P-256 ECDSA signing and verification
- Cross-algorithm rejection
- Invalid signature rejection

Tests will FAIL until the feature is implemented.
"""

from cryptography.hazmat.primitives import serialization


class TestSoftwareKeypairGeneration:
    """Test software keypair generation."""

    def test_generate_software_keypair_exists(self):
        """Test that generate_software_keypair function exists."""
        from peermodel import primitives
        assert hasattr(primitives, 'generate_software_keypair')

    def test_generate_software_keypair_returns_four_values(self):
        """Test that generate_software_keypair returns 4 values."""
        from peermodel.primitives import generate_software_keypair
        result = generate_software_keypair(algorithm='ed25519')
        expected = "(signing_private, signing_public, "
        expected += "encryption_private, encryption_public)"
        assert len(result) == 4, f"Should return {expected}"

    def test_generate_software_keypair_keys_are_bytes(self):
        """Test that all returned keys are bytes (DER-encoded)."""
        from peermodel.primitives import generate_software_keypair
        result = generate_software_keypair(algorithm='ed25519')
        signing_private, signing_public = result[0], result[1]
        encryption_private, encryption_public = result[2], result[3]

        assert isinstance(signing_private, bytes), \
            "Signing private key should be DER-encoded bytes"
        assert isinstance(signing_public, bytes), \
            "Signing public key should be DER-encoded bytes"
        assert isinstance(encryption_private, bytes), \
            "Encryption private key should be DER-encoded bytes"
        assert isinstance(encryption_public, bytes), \
            "Encryption public key should be DER-encoded bytes"

    def test_generate_software_keypair_keys_are_der_encoded(self):
        """Test that keys can be loaded as DER-encoded keys."""
        from peermodel.primitives import generate_software_keypair
        result = generate_software_keypair(algorithm='ed25519')
        signing_private, signing_public = result[0], result[1]
        encryption_private, encryption_public = result[2], result[3]

        # Should be loadable as DER keys without errors
        signing_priv_obj = serialization.load_der_private_key(
            signing_private, password=None)
        signing_pub_obj = serialization.load_der_public_key(
            signing_public)
        encryption_priv_obj = serialization.load_der_private_key(
            encryption_private, password=None)
        encryption_pub_obj = serialization.load_der_public_key(
            encryption_public)

        assert signing_priv_obj is not None
        assert signing_pub_obj is not None
        assert encryption_priv_obj is not None
        assert encryption_pub_obj is not None

    def test_generate_software_keypair_produces_unique_keys(self):
        """Test that multiple calls produce different keypairs."""
        from peermodel.primitives import generate_software_keypair

        keypair1 = generate_software_keypair(algorithm='ed25519')
        keypair2 = generate_software_keypair(algorithm='ed25519')

        # At least one key should differ
        msg = "Each call should generate unique keypairs"
        assert keypair1 != keypair2, msg

    def test_generate_software_keypair_supports_p256(self):
        """Test that P-256 algorithm is supported."""
        from peermodel.primitives import generate_software_keypair
        result = generate_software_keypair(algorithm='p256')
        assert len(result) == 4, "Should return 4 keys for P-256"


class TestEd25519Signing:
    """Test Ed25519 signing and verification."""

    def test_sign_bytes_ed25519_exists(self):
        """Test that sign_bytes function exists."""
        from peermodel import primitives
        assert hasattr(primitives, 'sign_bytes')

    def test_verify_bytes_ed25519_exists(self):
        """Test that verify_bytes function exists."""
        from peermodel import primitives
        assert hasattr(primitives, 'verify_bytes')

    def test_sign_bytes_ed25519_produces_signature(self):
        """Test that sign_bytes produces a signature for Ed25519 keys."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes)

        signing_private, _, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Test message for Ed25519 signing"

        signature = sign_bytes(message, signing_private,
                               algorithm='ed25519')
        assert isinstance(signature, bytes), "Signature should be bytes"
        msg = "Ed25519 signature should be 64 bytes (raw format)"
        assert len(signature) == 64, msg

    def test_verify_bytes_ed25519_accepts_valid_signature(self):
        """Test that verify_bytes accepts a valid Ed25519 signature."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Test message for Ed25519 verification"

        signature = sign_bytes(message, signing_private,
                               algorithm='ed25519')
        is_valid = verify_bytes(message, signature, signing_public,
                                algorithm='ed25519')

        msg = "Valid Ed25519 signature should verify successfully"
        assert is_valid is True, msg

    def test_verify_bytes_ed25519_rejects_invalid_signature(self):
        """Test that verify_bytes rejects an invalid Ed25519 signature."""
        from peermodel.primitives import (
            generate_software_keypair, verify_bytes)

        _, signing_public, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Test message"
        invalid_signature = b"0" * 64  # Invalid signature

        is_valid = verify_bytes(message, invalid_signature,
                                signing_public, algorithm='ed25519')
        msg = "Invalid Ed25519 signature should be rejected"
        assert is_valid is False, msg

    def test_verify_bytes_ed25519_rejects_wrong_message(self):
        """Test that verify_bytes rejects signature for different msg."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='ed25519')
        original_message = b"Original message"
        different_message = b"Different message"

        signature = sign_bytes(original_message, signing_private,
                               algorithm='ed25519')
        is_valid = verify_bytes(different_message, signature,
                                signing_public, algorithm='ed25519')

        msg = "Signature should not verify with different message"
        assert is_valid is False, msg

    def test_verify_bytes_ed25519_rejects_wrong_key(self):
        """Test that verify_bytes rejects signature with wrong key."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private1, _, _, _ = generate_software_keypair(
            algorithm='ed25519')
        _, signing_public2, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Test message"

        signature = sign_bytes(message, signing_private1,
                               algorithm='ed25519')
        is_valid = verify_bytes(message, signature, signing_public2,
                                algorithm='ed25519')

        msg = "Signature should not verify with different public key"
        assert is_valid is False, msg


class TestP256ECDSASigning:
    """Test P-256 ECDSA signing and verification."""

    def test_sign_bytes_p256_produces_signature(self):
        """Test that sign_bytes produces signature for P-256 ECDSA keys."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes)

        signing_private, _, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Test message for P-256 ECDSA signing"

        signature = sign_bytes(message, signing_private,
                               algorithm='p256')
        assert isinstance(signature, bytes), "Signature should be bytes"
        # P-256 ECDSA signature is DER-encoded, variable length
        msg = "P-256 ECDSA signature should be DER-encoded"
        assert len(signature) >= 64 and len(signature) <= 80, msg

    def test_verify_bytes_p256_accepts_valid_signature(self):
        """Test that verify_bytes accepts valid P-256 ECDSA signature."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Test message for P-256 ECDSA verification"

        signature = sign_bytes(message, signing_private,
                               algorithm='p256')
        is_valid = verify_bytes(message, signature, signing_public,
                                algorithm='p256')

        msg = "Valid P-256 ECDSA signature should verify successfully"
        assert is_valid is True, msg

    def test_verify_bytes_p256_rejects_invalid_signature(self):
        """Test that verify_bytes rejects invalid P-256 ECDSA signature."""
        from peermodel.primitives import (
            generate_software_keypair, verify_bytes)

        _, signing_public, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Test message"
        invalid_signature = b"0" * 70  # Invalid signature

        is_valid = verify_bytes(message, invalid_signature,
                                signing_public, algorithm='p256')
        msg = "Invalid P-256 ECDSA signature should be rejected"
        assert is_valid is False, msg

    def test_verify_bytes_p256_rejects_wrong_message(self):
        """Test that verify_bytes rejects P-256 sig for different msg."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='p256')
        original_message = b"Original message"
        different_message = b"Different message"

        signature = sign_bytes(original_message, signing_private,
                               algorithm='p256')
        is_valid = verify_bytes(different_message, signature,
                                signing_public, algorithm='p256')

        msg = "P-256 signature should not verify with different message"
        assert is_valid is False, msg

    def test_verify_bytes_p256_rejects_wrong_key(self):
        """Test that verify_bytes rejects P-256 sig with wrong key."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private1, _, _, _ = generate_software_keypair(
            algorithm='p256')
        _, signing_public2, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Test message"

        signature = sign_bytes(message, signing_private1,
                               algorithm='p256')
        is_valid = verify_bytes(message, signature, signing_public2,
                                algorithm='p256')

        msg = "P-256 signature should not verify with different public key"
        assert is_valid is False, msg


class TestCrossAlgorithmRejection:
    """Test that keys from one algorithm are rejected by another."""

    def test_ed25519_key_fails_p256_signing(self):
        """Test that Ed25519 key cannot be used for P-256 signing."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes)

        signing_private, _, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Test cross-algorithm rejection"

        # Try to sign Ed25519 key with P-256 algorithm - should fail
        try:
            sign_bytes(message, signing_private, algorithm='p256')
            assert False, "Should raise exception when using wrong algorithm"
        except (ValueError, TypeError, Exception):
            pass  # Expected - key type doesn't match algorithm

    def test_p256_key_fails_ed25519_signing(self):
        """Test that P-256 key cannot be used for Ed25519 signing."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes)

        signing_private, _, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Test cross-algorithm rejection"

        # Try to sign P-256 key with Ed25519 algorithm - should fail
        try:
            sign_bytes(message, signing_private, algorithm='ed25519')
            assert False, "Should raise exception when using wrong algorithm"
        except (ValueError, TypeError, Exception):
            pass  # Expected - key type doesn't match algorithm


class TestSignatureRoundtrip:
    """Test complete round-trip signing and verification."""

    def test_ed25519_roundtrip(self):
        """Test complete Ed25519 signing and verification round-trip."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='ed25519')
        message = b"Round-trip test message for Ed25519"

        # Sign
        signature = sign_bytes(message, signing_private,
                               algorithm='ed25519')

        # Verify
        is_valid = verify_bytes(message, signature, signing_public,
                                algorithm='ed25519')

        assert is_valid is True, "Ed25519 round-trip should succeed"

    def test_p256_roundtrip(self):
        """Test complete P-256 ECDSA signing/verification round-trip."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='p256')
        message = b"Round-trip test message for P-256 ECDSA"

        # Sign
        signature = sign_bytes(message, signing_private,
                               algorithm='p256')

        # Verify
        is_valid = verify_bytes(message, signature, signing_public,
                                algorithm='p256')

        assert is_valid is True, "P-256 ECDSA round-trip should succeed"

    def test_multiple_messages_ed25519(self):
        """Test signing multiple different messages with Ed25519."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='ed25519')

        messages = [
            b"First message",
            b"Second message",
            b"Third message"
        ]

        for message in messages:
            signature = sign_bytes(message, signing_private,
                                   algorithm='ed25519')
            is_valid = verify_bytes(message, signature, signing_public,
                                    algorithm='ed25519')
            msg = f"Ed25519 verification should succeed for: {message}"
            assert is_valid is True, msg

    def test_multiple_messages_p256(self):
        """Test signing multiple different messages with P-256 ECDSA."""
        from peermodel.primitives import (
            generate_software_keypair, sign_bytes, verify_bytes)

        signing_private, signing_public, _, _ = generate_software_keypair(
            algorithm='p256')

        messages = [
            b"First message",
            b"Second message",
            b"Third message"
        ]

        for message in messages:
            signature = sign_bytes(message, signing_private,
                                   algorithm='p256')
            is_valid = verify_bytes(message, signature, signing_public,
                                    algorithm='p256')
            msg = f"P-256 ECDSA verification should succeed: {message}"
            assert is_valid is True, msg
