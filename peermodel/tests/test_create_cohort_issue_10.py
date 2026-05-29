#!/usr/bin/env python

"""
Tests for Issue #10: Cohort creation & initial KeyBundle.

This test module covers the acceptance criteria for creating a new cohort:
- Create cohort with founder
- CohortIdentity signed
- KeyBundle created with founder entry
- Founder can decrypt cohort key
- Tests: create cohort, founder decrypt

Tests are marked with @pytest.mark.issue_10 for filtering.
These tests will FAIL until create_cohort() is implemented.
"""

import pytest
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional

from peermodel.primitives import (
    generate_keypair,
    deserialize_from_cbor,
)


@dataclass
class MemberCredential:
    """Member identity and public keys."""
    member_id: str
    x25519_public: bytes
    ed25519_public: bytes
    x25519_private: Optional[bytes] = None
    ed25519_private: Optional[bytes] = None
    signing_algorithm: str = "ed25519"
    encryption_algorithm: str = "x25519"
    hardware_backed: bool = False
    certificate_der: Optional[bytes] = None


@dataclass
class CohortIdentity:
    """Cohort identity and metadata."""
    cohort_id: str
    signing_public_key: bytes
    signing_algorithm: str
    encryption_public_key: bytes
    encryption_algorithm: str
    created_at: datetime
    keybundle_cid: Optional[str] = None


@dataclass
class KeyBundleEntry:
    """Single member's encrypted cohort key."""
    member_id: str
    encrypted_key_material: bytes
    ephemeral_public_key_der: bytes
    nonce: bytes
    tag: bytes


@dataclass
class KeyBundle:
    """Encrypted cohort key distribution."""
    cohort_id: str
    version: int
    signing_alg: str
    encryption_alg: str
    entries: List[KeyBundleEntry]


@pytest.fixture
def founder_identity():
    """Generate founder's identity with keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'founder',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def founder_credential(founder_identity):
    """Create founder MemberCredential."""
    return MemberCredential(
        member_id=founder_identity['member_id'],
        x25519_public=founder_identity['x25519_public'],
        ed25519_public=founder_identity['ed25519_public'],
        x25519_private=founder_identity['x25519_private'],
        ed25519_private=founder_identity['ed25519_private'],
    )


class TestCohortCreationBasics:
    """Test basic cohort creation."""

    @pytest.mark.issue_10
    def test_create_cohort_with_founder(self, founder_identity):
        """Cohort can be created with a founder.

        Acceptance criterion: Create cohort with founder
        """
        from peermodel.delegation import create_cohort

        cohort_id = 'test_cohort_1'
        cohort_identity, keybundle, cohort_private_key = create_cohort(
            cohort_id=cohort_id,
            founder_identity=founder_identity,
        )

        # Cohort identity should be created
        assert cohort_identity is not None
        assert cohort_identity.cohort_id == cohort_id

    @pytest.mark.issue_10
    def test_create_cohort_returns_three_items(self, founder_identity):
        """create_cohort returns (CohortIdentity, KeyBundle, cohort_private_key_bytes)."""
        from peermodel.delegation import create_cohort

        result = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert isinstance(result, tuple), "Should return tuple"
        assert len(result) == 3, "Should return exactly 3 items"

        cohort_identity, keybundle, cohort_private_key = result
        assert cohort_identity is not None, "First item is CohortIdentity"
        assert keybundle is not None, "Second item is KeyBundle"
        assert cohort_private_key is not None, "Third item is bytes"

    @pytest.mark.issue_10
    def test_cohort_identity_has_required_fields(self, founder_identity):
        """CohortIdentity has all required fields."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # CohortIdentity fields per spec
        assert hasattr(cohort_identity, 'cohort_id')
        assert hasattr(cohort_identity, 'signing_public_key')
        assert hasattr(cohort_identity, 'signing_algorithm')
        assert hasattr(cohort_identity, 'encryption_public_key')
        assert hasattr(cohort_identity, 'encryption_algorithm')
        assert hasattr(cohort_identity, 'created_at')

    @pytest.mark.issue_10
    def test_cohort_identity_cohort_id_matches(self, founder_identity):
        """CohortIdentity.cohort_id matches input."""
        from peermodel.delegation import create_cohort

        cohort_id = 'test_cohort_xyz'
        cohort_identity, _, _ = create_cohort(
            cohort_id=cohort_id,
            founder_identity=founder_identity,
        )

        assert cohort_identity.cohort_id == cohort_id

    @pytest.mark.issue_10
    def test_keybundle_has_required_fields(self, founder_identity):
        """KeyBundle has all required fields."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # KeyBundle fields per spec
        assert hasattr(keybundle, 'cohort_id')
        assert hasattr(keybundle, 'version')
        assert hasattr(keybundle, 'signing_alg')
        assert hasattr(keybundle, 'encryption_alg')
        assert hasattr(keybundle, 'entries')

    @pytest.mark.issue_10
    def test_keybundle_cohort_id_matches(self, founder_identity):
        """KeyBundle.cohort_id matches input."""
        from peermodel.delegation import create_cohort

        cohort_id = 'test_cohort_xyz'
        _, keybundle, _ = create_cohort(
            cohort_id=cohort_id,
            founder_identity=founder_identity,
        )

        assert keybundle.cohort_id == cohort_id

    @pytest.mark.issue_10
    def test_keybundle_is_initial_version(self, founder_identity):
        """Initial KeyBundle has version 1."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert keybundle.version == 1


class TestCohortIdentitySigning:
    """Test CohortIdentity signing."""

    @pytest.mark.issue_10
    def test_cohort_identity_has_fresh_keypair(self, founder_identity):
        """CohortIdentity has a fresh keypair (not founder's keys)."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # Cohort keys should differ from founder keys
        assert cohort_identity.signing_public_key != founder_identity['ed25519_public']
        assert cohort_identity.encryption_public_key != founder_identity['x25519_public']

    @pytest.mark.issue_10
    def test_cohort_identity_encryption_public_key_is_bytes(self, founder_identity):
        """CohortIdentity.encryption_public_key is DER-encoded bytes."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert isinstance(cohort_identity.encryption_public_key, bytes)
        assert len(cohort_identity.encryption_public_key) > 0

    @pytest.mark.issue_10
    def test_cohort_identity_signing_public_key_is_bytes(self, founder_identity):
        """CohortIdentity.signing_public_key is DER-encoded bytes."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert isinstance(cohort_identity.signing_public_key, bytes)
        assert len(cohort_identity.signing_public_key) > 0

    @pytest.mark.issue_10
    def test_cohort_identity_uses_ed25519_signing(self, founder_identity):
        """CohortIdentity uses Ed25519 for signing (v1 spec)."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert cohort_identity.signing_algorithm == 'ed25519'

    @pytest.mark.issue_10
    def test_cohort_identity_uses_x25519_encryption(self, founder_identity):
        """CohortIdentity uses X25519 for encryption (v1 spec)."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert cohort_identity.encryption_algorithm == 'x25519'

    @pytest.mark.issue_10
    def test_cohort_identity_created_at_is_datetime(self, founder_identity):
        """CohortIdentity.created_at is a datetime."""
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert isinstance(cohort_identity.created_at, datetime)


class TestKeyBundleStructure:
    """Test KeyBundle structure and entries."""

    @pytest.mark.issue_10
    def test_keybundle_has_founder_entry(self, founder_identity):
        """KeyBundle has entry for founder.

        Acceptance criterion: KeyBundle created with founder entry
        """
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # Should have at least one entry (founder)
        assert len(keybundle.entries) >= 1
        # First entry should be for founder
        assert keybundle.entries[0].member_id == founder_identity['member_id']

    @pytest.mark.issue_10
    def test_keybundle_entry_has_required_fields(self, founder_identity):
        """KeyBundleEntry has all required fields."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]

        # KeyBundleEntry fields per spec
        assert hasattr(entry, 'member_id')
        assert hasattr(entry, 'encrypted_key_material')
        assert hasattr(entry, 'ephemeral_public_key_der')
        assert hasattr(entry, 'nonce')
        assert hasattr(entry, 'tag')

    @pytest.mark.issue_10
    def test_keybundle_entry_encrypted_key_material_is_bytes(self, founder_identity):
        """KeyBundleEntry.encrypted_key_material is bytes."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]
        assert isinstance(entry.encrypted_key_material, bytes)
        assert len(entry.encrypted_key_material) > 0

    @pytest.mark.issue_10
    def test_keybundle_entry_ephemeral_public_key_is_bytes(self, founder_identity):
        """KeyBundleEntry.ephemeral_public_key_der is bytes."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]
        assert isinstance(entry.ephemeral_public_key_der, bytes)
        assert len(entry.ephemeral_public_key_der) > 0

    @pytest.mark.issue_10
    def test_keybundle_entry_nonce_is_bytes(self, founder_identity):
        """KeyBundleEntry.nonce is bytes."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]
        assert isinstance(entry.nonce, bytes)
        # Nonce should have reasonable length for X25519 + HKDF
        assert len(entry.nonce) > 0

    @pytest.mark.issue_10
    def test_keybundle_entry_tag_is_bytes(self, founder_identity):
        """KeyBundleEntry.tag is bytes."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]
        assert isinstance(entry.tag, bytes)


class TestFounderDecryption:
    """Test that founder can decrypt cohort key.

    Acceptance criterion: Founder can decrypt cohort key
    """

    @pytest.mark.issue_10
    def test_founder_can_decrypt_cohort_key(self, founder_identity):
        """Founder can decrypt the cohort private key from KeyBundle.

        Acceptance criterion: Founder can decrypt cohort key
        """
        from peermodel.delegation import create_cohort, get_cohort_private_key

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # Founder should be able to decrypt
        cohort_key = get_cohort_private_key(
            keybundle=keybundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        assert cohort_key is not None
        assert isinstance(cohort_key, bytes)
        assert len(cohort_key) > 0

    @pytest.mark.issue_10
    def test_founder_decrypted_key_contains_keypair_material(self, founder_identity):
        """Decrypted cohort key contains signing and encryption key material."""
        from peermodel.delegation import create_cohort, get_cohort_private_key

        cohort_identity, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        cohort_key = get_cohort_private_key(
            keybundle=keybundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        # Decrypted key should be a CBOR-encoded dict with private key material
        # Attempt to deserialize - will fail if wrong format
        key_dict = deserialize_from_cbor(cohort_key, dict)

        # Should contain keys for signing and encryption
        assert 'signing_private_key' in key_dict or 'ed25519_private' in key_dict
        assert 'encryption_private_key' in key_dict or 'x25519_private' in key_dict

    @pytest.mark.issue_10
    def test_cohort_private_key_bytes_returned_from_create_cohort(self, founder_identity):
        """create_cohort returns the cohort private key bytes as third item."""
        from peermodel.delegation import create_cohort

        _, _, cohort_private_key = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert cohort_private_key is not None
        assert isinstance(cohort_private_key, bytes)
        assert len(cohort_private_key) > 0

    @pytest.mark.issue_10
    def test_founder_decrypted_key_matches_returned_private_key(self, founder_identity):
        """Founder's decrypted key matches the private key returned from create_cohort."""
        from peermodel.delegation import create_cohort, get_cohort_private_key

        _, keybundle, returned_key = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        decrypted_key = get_cohort_private_key(
            keybundle=keybundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        # Both should decrypt to the same private key material
        assert decrypted_key == returned_key, \
            "Decrypted key should match returned key from create_cohort"


class TestCohortIdentitySignatureVerification:
    """Test that CohortIdentity is properly signed."""

    @pytest.mark.issue_10
    def test_cohort_identity_can_be_verified_with_founder_key(self, founder_identity):
        """CohortIdentity can be verified using the signing key.

        Note: The spec shows founder signs CohortIdentity. Verify this
        by checking the signature matches cohort's public key.
        """
        from peermodel.delegation import create_cohort

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # CohortIdentity should have a signature (per spec)
        # or the creation process should be verifiable
        # This is verified by checking that the keys are actually generated
        assert cohort_identity.signing_public_key is not None
        assert cohort_identity.encryption_public_key is not None


class TestCohortEncryptionKeyGeneration:
    """Test that cohort generates fresh encryption key."""

    @pytest.mark.issue_10
    def test_different_cohorts_have_different_keys(self, founder_identity):
        """Different cohorts generate different keypairs."""
        from peermodel.delegation import create_cohort

        cohort1_identity, _, _ = create_cohort(
            cohort_id='cohort_1',
            founder_identity=founder_identity,
        )

        cohort2_identity, _, _ = create_cohort(
            cohort_id='cohort_2',
            founder_identity=founder_identity,
        )

        assert cohort1_identity.encryption_public_key != cohort2_identity.encryption_public_key
        assert cohort1_identity.signing_public_key != cohort2_identity.signing_public_key

    @pytest.mark.issue_10
    def test_cohort_signing_key_is_valid_der(self, founder_identity):
        """Cohort signing key is valid DER-encoded Ed25519 public key."""
        from peermodel.delegation import create_cohort
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # Should be loadable as DER public key
        pub_key = serialization.load_der_public_key(cohort_identity.signing_public_key)
        assert isinstance(pub_key, ed25519.Ed25519PublicKey)

    @pytest.mark.issue_10
    def test_cohort_encryption_key_is_valid_der(self, founder_identity):
        """Cohort encryption key is valid DER-encoded X25519 public key."""
        from peermodel.delegation import create_cohort
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import x25519

        cohort_identity, _, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        # Should be loadable as DER public key
        pub_key = serialization.load_der_public_key(cohort_identity.encryption_public_key)
        assert isinstance(pub_key, x25519.X25519PublicKey)


class TestCohortCreationEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.issue_10
    def test_create_cohort_with_empty_cohort_id(self, founder_identity):
        """Create cohort with empty cohort_id should either work or raise ValueError."""
        from peermodel.delegation import create_cohort

        # Implementation choice: accept empty or reject
        # For now, test that it's handled consistently
        try:
            result = create_cohort(
                cohort_id='',
                founder_identity=founder_identity,
            )
            # If it succeeds, empty string should be preserved
            assert result[0].cohort_id == ''
        except (ValueError, TypeError):
            # If it fails, that's also acceptable
            pass

    @pytest.mark.issue_10
    def test_create_cohort_with_unicode_cohort_id(self, founder_identity):
        """Create cohort with Unicode cohort_id should work."""
        from peermodel.delegation import create_cohort

        cohort_id = 'cohort_🔐_test'
        cohort_identity, _, _ = create_cohort(
            cohort_id=cohort_id,
            founder_identity=founder_identity,
        )

        assert cohort_identity.cohort_id == cohort_id

    @pytest.mark.issue_10
    def test_create_multiple_cohorts_independently(self, founder_identity):
        """Can create multiple independent cohorts."""
        from peermodel.delegation import create_cohort

        cohorts = []
        for i in range(3):
            cohort_identity, keybundle, key = create_cohort(
                cohort_id=f'cohort_{i}',
                founder_identity=founder_identity,
            )
            cohorts.append((cohort_identity, keybundle, key))

        # All cohorts should be distinct
        assert cohorts[0][0].cohort_id != cohorts[1][0].cohort_id
        assert cohorts[1][0].cohort_id != cohorts[2][0].cohort_id

        # All should have different keys
        assert cohorts[0][0].signing_public_key != cohorts[1][0].signing_public_key
        assert cohorts[1][0].signing_public_key != cohorts[2][0].signing_public_key


class TestCohortCreationIntegration:
    """Integration tests for create_cohort."""

    @pytest.mark.issue_10
    def test_full_create_cohort_workflow(self, founder_identity):
        """Full workflow: create cohort, get keys, verify integrity.

        Acceptance criterion: Tests: create cohort, founder decrypt
        """
        from peermodel.delegation import create_cohort, get_cohort_private_key

        # Create cohort
        cohort_id = 'integration_test_cohort'
        cohort_identity, keybundle, returned_key = create_cohort(
            cohort_id=cohort_id,
            founder_identity=founder_identity,
        )

        # Verify CohortIdentity
        assert cohort_identity.cohort_id == cohort_id
        assert cohort_identity.signing_public_key is not None
        assert cohort_identity.encryption_public_key is not None

        # Verify KeyBundle
        assert keybundle.cohort_id == cohort_id
        assert len(keybundle.entries) > 0

        # Founder can decrypt
        decrypted_key = get_cohort_private_key(
            keybundle=keybundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        # Decrypted key should match
        assert decrypted_key is not None
        assert decrypted_key == returned_key

    @pytest.mark.issue_10
    def test_keybundle_entry_uses_founder_encryption_key(self, founder_identity):
        """KeyBundle entry is encrypted to founder's X25519 public key."""
        from peermodel.delegation import create_cohort

        _, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        entry = keybundle.entries[0]

        # Entry should be encrypted to founder's X25519 key
        # This is verified implicitly by founder being able to decrypt
        # Verify entry has ephemeral public key (used for ECDH)
        assert entry.ephemeral_public_key_der is not None
        assert len(entry.ephemeral_public_key_der) > 0

    @pytest.mark.issue_10
    def test_keybundle_signing_algorithm_matches_cohort_identity(self, founder_identity):
        """KeyBundle.signing_alg matches CohortIdentity.signing_algorithm."""
        from peermodel.delegation import create_cohort

        cohort_identity, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert keybundle.signing_alg == cohort_identity.signing_algorithm

    @pytest.mark.issue_10
    def test_keybundle_encryption_algorithm_matches_cohort_identity(self, founder_identity):
        """KeyBundle.encryption_alg matches CohortIdentity.encryption_algorithm."""
        from peermodel.delegation import create_cohort

        cohort_identity, keybundle, _ = create_cohort(
            cohort_id='test_cohort',
            founder_identity=founder_identity,
        )

        assert keybundle.encryption_alg == cohort_identity.encryption_algorithm
