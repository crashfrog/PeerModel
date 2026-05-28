#!/usr/bin/env python

"""
RED tests for Issue #9: Cohort keypair generation (software).

These tests cover:
- Cohort keypair generation using existing primitives.generate_software_keypair()
- Cohort keypair structure (X25519 encryption + Ed25519 signing)
- Key storage security (private keys encrypted in KeyBundle)
- Integration with SimpleCohort
- Cohort signature operations using cohort keys

Tests will FAIL until the feature is implemented.
"""

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519


class TestCohortKeypairGeneration:
    """Test cohort-level keypair generation."""

    def test_cohort_can_generate_keypair(self):
        """Test that SimpleCohort can generate its own keypair."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort - should generate cohort keypair
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Cohort should have its own encryption and signing keys
        assert hasattr(cohort, 'cohort_x25519_private'), \
            "Cohort should have X25519 private key"
        assert hasattr(cohort, 'cohort_x25519_public'), \
            "Cohort should have X25519 public key"
        assert hasattr(cohort, 'cohort_ed25519_private'), \
            "Cohort should have Ed25519 private key"
        assert hasattr(cohort, 'cohort_ed25519_public'), \
            "Cohort should have Ed25519 public key"

    def test_cohort_keypair_uses_generate_software_keypair(self):
        """Test that cohort uses primitives.generate_software_keypair()."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Keys should be DER-encoded bytes (output of generate_software_keypair)
        assert isinstance(cohort.cohort_x25519_private, bytes), \
            "Cohort X25519 private key should be DER-encoded bytes"
        assert isinstance(cohort.cohort_x25519_public, bytes), \
            "Cohort X25519 public key should be DER-encoded bytes"
        assert isinstance(cohort.cohort_ed25519_private, bytes), \
            "Cohort Ed25519 private key should be DER-encoded bytes"
        assert isinstance(cohort.cohort_ed25519_public, bytes), \
            "Cohort Ed25519 public key should be DER-encoded bytes"

    def test_cohort_keypair_keys_are_valid_der(self):
        """Test that cohort keys are valid DER-encoded keys."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Keys should be loadable as DER keys
        x25519_priv_obj = serialization.load_der_private_key(
            cohort.cohort_x25519_private, password=None)
        x25519_pub_obj = serialization.load_der_public_key(
            cohort.cohort_x25519_public)
        ed25519_priv_obj = serialization.load_der_private_key(
            cohort.cohort_ed25519_private, password=None)
        ed25519_pub_obj = serialization.load_der_public_key(
            cohort.cohort_ed25519_public)

        # Verify key types
        assert isinstance(x25519_priv_obj, x25519.X25519PrivateKey), \
            "Should load as X25519 private key"
        assert isinstance(x25519_pub_obj, x25519.X25519PublicKey), \
            "Should load as X25519 public key"
        assert isinstance(ed25519_priv_obj, ed25519.Ed25519PrivateKey), \
            "Should load as Ed25519 private key"
        assert isinstance(ed25519_pub_obj, ed25519.Ed25519PublicKey), \
            "Should load as Ed25519 public key"

    def test_cohort_keypair_is_unique_per_cohort(self):
        """Test that each cohort generates unique keypairs."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create two cohorts
        cohort1 = SimpleCohort(
            cohort_id='test_cohort_1',
            founder_identity=founder_identity
        )
        cohort2 = SimpleCohort(
            cohort_id='test_cohort_2',
            founder_identity=founder_identity
        )

        # Cohort keys should differ
        assert cohort1.cohort_x25519_private != cohort2.cohort_x25519_private, \
            "Each cohort should have unique X25519 private key"
        assert cohort1.cohort_x25519_public != cohort2.cohort_x25519_public, \
            "Each cohort should have unique X25519 public key"
        assert cohort1.cohort_ed25519_private != cohort2.cohort_ed25519_private, \
            "Each cohort should have unique Ed25519 private key"
        assert cohort1.cohort_ed25519_public != cohort2.cohort_ed25519_public, \
            "Each cohort should have unique Ed25519 public key"

    def test_cohort_keypair_differs_from_founder_keys(self):
        """Test that cohort keys are separate from founder keys."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Cohort keys should differ from founder keys
        assert cohort.cohort_x25519_private != founder_identity['x25519_private'], \
            "Cohort X25519 private key should differ from founder's"
        assert cohort.cohort_x25519_public != founder_identity['x25519_public'], \
            "Cohort X25519 public key should differ from founder's"
        assert cohort.cohort_ed25519_private != founder_identity['ed25519_private'], \
            "Cohort Ed25519 private key should differ from founder's"
        assert cohort.cohort_ed25519_public != founder_identity['ed25519_public'], \
            "Cohort Ed25519 public key should differ from founder's"


class TestCohortKeypairStorage:
    """Test secure storage of cohort keypairs."""

    def test_cohort_private_keys_not_exported_to_plaintext(self):
        """Test that cohort private keys are never exported to plaintext.

        This is a design constraint - cohort private keys should be stored
        encrypted in KeyBundle and never exposed as plaintext outside the
        SimpleCohort class internals.
        """
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Cohort should not have public methods to export private keys
        # (Keys should only be used internally for operations)
        # Private attributes are OK (Python convention: _cohort_x25519_private)
        # but no get_cohort_private_key() or export_cohort_keys() methods

        # Check that there's no obvious export method
        assert not hasattr(cohort, 'export_cohort_private_keys'), \
            "Cohort should not expose method to export private keys"
        assert not hasattr(cohort, 'get_cohort_private_key'), \
            "Cohort should not expose method to get private keys"

    def test_cohort_public_keys_are_accessible(self):
        """Test that cohort public keys can be retrieved."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Public keys should be accessible (for distribution to members)
        public_keys = cohort.get_cohort_public_keys()
        assert 'x25519_public' in public_keys, \
            "Should return X25519 public key"
        assert 'ed25519_public' in public_keys, \
            "Should return Ed25519 public key"
        assert isinstance(public_keys['x25519_public'], bytes), \
            "X25519 public key should be bytes"
        assert isinstance(public_keys['ed25519_public'], bytes), \
            "Ed25519 public key should be bytes"


class TestCohortSignatureOperations:
    """Test cohort-level signing operations using cohort keys."""

    def test_cohort_can_sign_with_cohort_key(self):
        """Test that cohort can sign data using its Ed25519 key."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Cohort should be able to sign data with its own key
        message = b"Test cohort message"
        signature = cohort.sign_cohort_message(message)

        assert isinstance(signature, bytes), "Signature should be bytes"
        assert len(signature) == 64, "Ed25519 signature should be 64 bytes"

    def test_cohort_signature_verifies_with_cohort_public_key(self):
        """Test that cohort signature can be verified with cohort public key."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair, verify_bytes

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Sign message with cohort key
        message = b"Test cohort message"
        signature = cohort.sign_cohort_message(message)

        # Verify with cohort public key
        public_keys = cohort.get_cohort_public_keys()
        is_valid = verify_bytes(
            message,
            signature,
            public_keys['ed25519_public'],
            algorithm='ed25519'
        )

        assert is_valid is True, \
            "Cohort signature should verify with cohort public key"

    def test_cohort_signature_differs_from_founder_signature(self):
        """Test that cohort signatures differ from founder signatures."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair, sign_bytes, verify_bytes

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Sign same message with both founder and cohort keys
        message = b"Test message"
        founder_signature = sign_bytes(message, ed25519_priv, algorithm='ed25519')
        cohort_signature = cohort.sign_cohort_message(message)

        # Signatures should differ (different keys)
        assert founder_signature != cohort_signature, \
            "Cohort signature should differ from founder signature"

        # Founder signature should NOT verify with cohort public key
        public_keys = cohort.get_cohort_public_keys()
        is_valid = verify_bytes(
            message,
            founder_signature,
            public_keys['ed25519_public'],
            algorithm='ed25519'
        )
        assert is_valid is False, \
            "Founder signature should not verify with cohort public key"

    def test_cohort_signature_property_uses_cohort_key(self):
        """Test that existing signature property uses cohort key."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair, verify_bytes

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Get cohort signature (existing property)
        signature = cohort.signature

        # Should be a valid Ed25519 signature
        assert isinstance(signature, bytes), "Signature should be bytes"
        assert len(signature) == 64, "Ed25519 signature should be 64 bytes"

        # Signature should verify with cohort public key (not founder key)
        public_keys = cohort.get_cohort_public_keys()

        # Reconstruct the message that was signed
        import json
        message = json.dumps({
            'cohort_id': cohort.cohort_id,
            'members': len(list(cohort.members)),
            'guests': len(list(cohort.guests))
        }).encode('utf-8')

        is_valid = verify_bytes(
            message,
            signature,
            public_keys['ed25519_public'],
            algorithm='ed25519'
        )
        assert is_valid is True, \
            "Cohort signature property should verify with cohort public key"


class TestCohortEncryptionOperations:
    """Test cohort-level encryption operations using cohort keys."""

    def test_cohort_can_encrypt_to_member(self):
        """Test that cohort can encrypt data for a member."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create member identity
        keypair = generate_keypair()
        member_x25519_priv, member_x25519_pub = keypair[0], keypair[1]
        member_ed25519_priv, member_ed25519_pub = keypair[2], keypair[3]
        member_identity = {
            'identity_id': 'test_member',
            'x25519_private': member_x25519_priv,
            'x25519_public': member_x25519_pub,
            'ed25519_private': member_ed25519_priv,
            'ed25519_public': member_ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Cohort should be able to encrypt data for a member
        plaintext = b"Cohort secret data"
        encrypted = cohort.encrypt_for_member(
            plaintext, member_identity['x25519_public']
        )

        assert encrypted is not None, "Should return encrypted envelope"
        expected = "[ciphertext, nonce, tag, ephemeral_public]"
        assert len(encrypted) == 4, f"Should return {expected}"

    def test_member_can_decrypt_cohort_encrypted_data(self):
        """Test that member can decrypt data encrypted by cohort."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair, decrypt_from_sender

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create member identity
        keypair = generate_keypair()
        member_x25519_priv, member_x25519_pub = keypair[0], keypair[1]
        member_ed25519_priv, member_ed25519_pub = keypair[2], keypair[3]
        member_identity = {
            'identity_id': 'test_member',
            'x25519_private': member_x25519_priv,
            'x25519_public': member_x25519_pub,
            'ed25519_private': member_ed25519_priv,
            'ed25519_public': member_ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Encrypt data for member
        plaintext = b"Cohort secret data"
        ciphertext, nonce, tag, ephemeral_public = cohort.encrypt_for_member(
            plaintext,
            member_identity['x25519_public']
        )

        # Member should be able to decrypt
        decrypted = decrypt_from_sender(
            ciphertext,
            nonce,
            tag,
            ephemeral_public,
            member_identity['x25519_private']
        )

        assert decrypted == plaintext, \
            "Member should be able to decrypt cohort-encrypted data"


class TestCohortKeypairRegeneration:
    """Test cohort key regeneration for forward secrecy."""

    def test_cohort_can_regenerate_keypair(self):
        """Test that cohort can regenerate its keypair."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Save original keys
        original_x25519_public = cohort.cohort_x25519_public
        original_ed25519_public = cohort.cohort_ed25519_public

        # Regenerate cohort keypair
        cohort.regenerate_cohort_keypair()

        # Keys should have changed
        assert cohort.cohort_x25519_public != original_x25519_public, \
            "X25519 public key should change after regeneration"
        assert cohort.cohort_ed25519_public != original_ed25519_public, \
            "Ed25519 public key should change after regeneration"

    def test_regenerate_invalidates_old_signatures(self):
        """Test that old signatures don't verify after key regeneration."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair, verify_bytes

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Sign message with original cohort key
        message = b"Test message"
        old_signature = cohort.sign_cohort_message(message)
        old_public_key = cohort.get_cohort_public_keys()['ed25519_public']

        # Regenerate cohort keypair
        cohort.regenerate_cohort_keypair()

        # Get new public key
        new_public_key = cohort.get_cohort_public_keys()['ed25519_public']

        # Old signature should NOT verify with new public key
        is_valid = verify_bytes(
            message,
            old_signature,
            new_public_key,
            algorithm='ed25519'
        )
        assert is_valid is False, \
            "Old signature should not verify with new public key"

        # Old signature should still verify with old public key
        is_valid = verify_bytes(
            message,
            old_signature,
            old_public_key,
            algorithm='ed25519'
        )
        assert is_valid is True, \
            "Old signature should still verify with old public key"


class TestCohortKeypairIntegration:
    """Test integration with existing SimpleCohort functionality."""

    def test_cohort_with_existing_signing_key_der(self):
        """Test backward compatibility with existing signing_key_der parameter."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Generate separate signing key
        _, _, custom_signing_key, _ = generate_keypair()

        # Create cohort with custom signing key
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
            signing_key_der=custom_signing_key
        )

        # Should use custom signing key (backward compatibility)
        # But should also generate cohort encryption key
        msg = "Should generate cohort encryption key even with custom signing key"
        assert hasattr(cohort, 'cohort_x25519_private'), msg
        assert hasattr(cohort, 'cohort_ed25519_private'), \
            "Should have cohort signing key (may be custom or generated)"

    def test_cohort_operations_work_with_cohort_keypair(self):
        """Test that existing cohort operations work with cohort keypair."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create second member identity
        alice_keypair = generate_keypair()
        alice_x25519_priv, alice_x25519_pub = alice_keypair[0], alice_keypair[1]
        alice_ed25519_priv, alice_ed25519_pub = alice_keypair[2], alice_keypair[3]
        alice_identity = {
            'identity_id': 'alice',
            'x25519_private': alice_x25519_priv,
            'x25519_public': alice_x25519_pub,
            'ed25519_private': alice_ed25519_priv,
            'ed25519_public': alice_ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Test add member proposal (uses cohort signature)
        proposal = cohort.create_add_member_proposal(
            alice_identity, founder_identity
        )
        assert proposal is not None, \
            "Should create proposal with cohort keypair"

        # Test signature property (should use cohort key now)
        signature = cohort.signature
        assert signature is not None, "Should generate signature with cohort key"
        assert len(signature) == 64, "Should be valid Ed25519 signature"

    def test_cohort_regenerate_method_updates_cohort_keys(self):
        """Test that regenerate() method updates cohort keypair."""
        from peermodel.delegation import SimpleCohort
        from peermodel.primitives import generate_keypair

        # Create founder identity
        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        founder_identity = {
            'identity_id': 'test_founder',
            'x25519_private': x25519_priv,
            'x25519_public': x25519_pub,
            'ed25519_private': ed25519_priv,
            'ed25519_public': ed25519_pub
        }

        # Create cohort
        cohort = SimpleCohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity
        )

        # Save original cohort public keys
        original_public_keys = cohort.get_cohort_public_keys()

        # Call regenerate (existing method)
        cohort.regenerate()

        # Cohort keys should have changed
        new_public_keys = cohort.get_cohort_public_keys()
        assert new_public_keys['ed25519_public'] != original_public_keys['ed25519_public'], \
            "regenerate() should update cohort Ed25519 key"
        # Note: regenerate() currently only updates signing_key_der
        # This test documents expected behavior after implementation
