#!/usr/bin/env python

"""
Tests for Issue #11: Member enrollment via key encryption.

Covers the acceptance criteria for add_member():
- Add member to cohort
- New member can decrypt cohort key
- Existing members unaffected
- Tests: add member, verify decryption

Tests are marked with @pytest.mark.issue_11 for filtering.
These tests will FAIL until add_member() is implemented.
"""

import pytest
from typing import Optional

from peermodel.primitives import generate_keypair, deserialize_from_cbor


@pytest.fixture
def founder_identity():
    """Generate founder identity with full keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'founder',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def new_member_identity():
    """Generate new member identity with full keypair."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
    return {
        'member_id': 'new_member',
        'x25519_public': x25519_pub,
        'x25519_private': x25519_priv,
        'ed25519_public': ed25519_pub,
        'ed25519_private': ed25519_priv,
    }


@pytest.fixture
def created_cohort(founder_identity):
    """Create a cohort and return (cohort_identity, keybundle, cohort_private_key_bytes)."""
    from peermodel.delegation import create_cohort
    return create_cohort(cohort_id='test_cohort_11', founder_identity=founder_identity)


class TestAddMemberBasics:
    """Test that add_member() returns a proper KeyBundle."""

    @pytest.mark.issue_11
    def test_add_member_returns_keybundle(self, created_cohort, founder_identity, new_member_identity):
        """add_member returns a KeyBundle object."""
        from peermodel.delegation import add_member, KeyBundle

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        assert isinstance(updated_bundle, KeyBundle), (
            f"add_member must return KeyBundle, got {type(updated_bundle)}"
        )

    @pytest.mark.issue_11
    def test_add_member_keybundle_cohort_id_unchanged(self, created_cohort, founder_identity, new_member_identity):
        """Updated KeyBundle preserves the original cohort_id."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        assert updated_bundle.cohort_id == keybundle.cohort_id, (
            "Updated KeyBundle must have same cohort_id as original"
        )

    @pytest.mark.issue_11
    def test_add_member_keybundle_version_incremented(self, created_cohort, founder_identity, new_member_identity):
        """Updated KeyBundle version is greater than original."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort
        original_version = keybundle.version

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        assert updated_bundle.version == original_version + 1, (
            f"Version should be {original_version + 1}, got {updated_bundle.version}"
        )


class TestNewMemberEntry:
    """Test that the new member's KeyBundleEntry is created correctly."""

    @pytest.mark.issue_11
    def test_add_member_new_entry_present(self, created_cohort, founder_identity, new_member_identity):
        """Updated KeyBundle contains an entry for the new member.

        Acceptance criterion: Add member to cohort
        """
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        member_ids = [e.member_id for e in updated_bundle.entries]
        assert new_member_identity['member_id'] in member_ids, (
            f"New member '{new_member_identity['member_id']}' not found in entries: {member_ids}"
        )

    @pytest.mark.issue_11
    def test_add_member_entry_has_encrypted_key_material(self, created_cohort, founder_identity, new_member_identity):
        """New member's entry has non-empty encrypted_key_material."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_entry = next(
            e for e in updated_bundle.entries
            if e.member_id == new_member_identity['member_id']
        )

        assert isinstance(new_entry.encrypted_key_material, bytes), (
            "encrypted_key_material must be bytes"
        )
        assert len(new_entry.encrypted_key_material) > 0, (
            "encrypted_key_material must not be empty"
        )

    @pytest.mark.issue_11
    def test_add_member_entry_has_ephemeral_public_key(self, created_cohort, founder_identity, new_member_identity):
        """New member's entry has a valid DER-encoded ephemeral public key."""
        from peermodel.delegation import add_member
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import x25519

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_entry = next(
            e for e in updated_bundle.entries
            if e.member_id == new_member_identity['member_id']
        )

        pub_key = serialization.load_der_public_key(new_entry.ephemeral_public_key_der)
        assert isinstance(pub_key, x25519.X25519PublicKey), (
            "ephemeral_public_key_der must be a valid DER-encoded X25519 public key"
        )

    @pytest.mark.issue_11
    def test_add_member_entry_has_nonce(self, created_cohort, founder_identity, new_member_identity):
        """New member's entry has non-empty nonce bytes."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_entry = next(
            e for e in updated_bundle.entries
            if e.member_id == new_member_identity['member_id']
        )

        assert isinstance(new_entry.nonce, bytes), "nonce must be bytes"
        assert len(new_entry.nonce) > 0, "nonce must not be empty"


class TestNewMemberDecryption:
    """Test that the new member can decrypt the cohort key.

    Acceptance criterion: New member can decrypt cohort key
    """

    @pytest.mark.issue_11
    def test_new_member_can_decrypt_cohort_key(self, created_cohort, founder_identity, new_member_identity):
        """New member can use get_cohort_private_key() to decrypt the cohort key.

        Acceptance criterion: New member can decrypt cohort key
        """
        from peermodel.delegation import add_member, get_cohort_private_key

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=new_member_identity['member_id'],
            member_x25519_private=new_member_identity['x25519_private'],
            member_ed25519_private=new_member_identity['ed25519_private'],
        )

        assert isinstance(decrypted, bytes), "Decrypted cohort key must be bytes"
        assert len(decrypted) > 0, "Decrypted cohort key must not be empty"

    @pytest.mark.issue_11
    def test_new_member_decrypts_same_key_as_founder(self, created_cohort, founder_identity, new_member_identity):
        """New member decrypts the same cohort key material as the founder.

        Verifies that both members share access to identical key material.
        """
        from peermodel.delegation import add_member, get_cohort_private_key

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        founder_decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        new_member_decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=new_member_identity['member_id'],
            member_x25519_private=new_member_identity['x25519_private'],
            member_ed25519_private=new_member_identity['ed25519_private'],
        )

        assert new_member_decrypted == founder_decrypted, (
            "New member must decrypt the same cohort key material as the founder"
        )

    @pytest.mark.issue_11
    def test_new_member_decrypted_key_matches_original_cohort_key(self, created_cohort, founder_identity, new_member_identity):
        """New member decrypts the same bytes that create_cohort returned as cohort_private_key_bytes."""
        from peermodel.delegation import add_member, get_cohort_private_key

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_member_decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=new_member_identity['member_id'],
            member_x25519_private=new_member_identity['x25519_private'],
            member_ed25519_private=new_member_identity['ed25519_private'],
        )

        assert new_member_decrypted == cohort_private_key_bytes, (
            "New member must decrypt the exact cohort key bytes from create_cohort"
        )

    @pytest.mark.issue_11
    def test_new_member_decrypted_key_contains_private_key_material(self, created_cohort, founder_identity, new_member_identity):
        """New member's decrypted cohort key is valid CBOR with private key fields."""
        from peermodel.delegation import add_member, get_cohort_private_key

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_member_decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=new_member_identity['member_id'],
            member_x25519_private=new_member_identity['x25519_private'],
            member_ed25519_private=new_member_identity['ed25519_private'],
        )

        key_dict = deserialize_from_cbor(new_member_decrypted, dict)

        has_signing_key = 'signing_private_key' in key_dict or 'ed25519_private' in key_dict
        has_encryption_key = 'encryption_private_key' in key_dict or 'x25519_private' in key_dict

        assert has_signing_key, f"Cohort key material must contain signing private key, got keys: {list(key_dict.keys())}"
        assert has_encryption_key, f"Cohort key material must contain encryption private key, got keys: {list(key_dict.keys())}"


class TestExistingMembersUnaffected:
    """Test that existing members are unaffected by adding a new member.

    Acceptance criterion: Existing members unaffected
    """

    @pytest.mark.issue_11
    def test_founder_entry_still_present_after_add_member(self, created_cohort, founder_identity, new_member_identity):
        """Founder's KeyBundleEntry is still in the updated KeyBundle.

        Acceptance criterion: Existing members unaffected
        """
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        member_ids = [e.member_id for e in updated_bundle.entries]
        assert founder_identity['member_id'] in member_ids, (
            f"Founder entry missing from updated KeyBundle entries: {member_ids}"
        )

    @pytest.mark.issue_11
    def test_founder_can_still_decrypt_after_add_member(self, created_cohort, founder_identity, new_member_identity):
        """Founder can still decrypt cohort key from updated KeyBundle.

        Acceptance criterion: Existing members unaffected
        """
        from peermodel.delegation import add_member, get_cohort_private_key

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        founder_decrypted = get_cohort_private_key(
            keybundle=updated_bundle,
            member_id=founder_identity['member_id'],
            member_x25519_private=founder_identity['x25519_private'],
            member_ed25519_private=founder_identity['ed25519_private'],
        )

        assert founder_decrypted == cohort_private_key_bytes, (
            "Founder's decrypted cohort key must match original after adding new member"
        )

    @pytest.mark.issue_11
    def test_updated_keybundle_has_two_entries(self, created_cohort, founder_identity, new_member_identity):
        """Updated KeyBundle has exactly two entries: founder and new member."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        assert len(updated_bundle.entries) == 2, (
            f"Updated KeyBundle must have 2 entries (founder + new member), got {len(updated_bundle.entries)}"
        )

    @pytest.mark.issue_11
    def test_add_second_member_preserves_first_member_entry(self, created_cohort, founder_identity):
        """Adding a second new member still preserves the first new member's entry."""
        from peermodel.delegation import add_member, get_cohort_private_key

        x25519_priv1, x25519_pub1, ed25519_priv1, ed25519_pub1 = generate_keypair()
        member1_identity = {
            'member_id': 'member_one',
            'x25519_public': x25519_pub1,
            'x25519_private': x25519_priv1,
            'ed25519_public': ed25519_pub1,
            'ed25519_private': ed25519_priv1,
        }

        x25519_priv2, x25519_pub2, ed25519_priv2, ed25519_pub2 = generate_keypair()
        member2_identity = {
            'member_id': 'member_two',
            'x25519_public': x25519_pub2,
            'x25519_private': x25519_priv2,
            'ed25519_public': ed25519_pub2,
            'ed25519_private': ed25519_priv2,
        }

        _, keybundle, cohort_private_key_bytes = created_cohort

        bundle_with_one = add_member(
            keybundle=keybundle,
            new_member_identity=member1_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        bundle_with_two = add_member(
            keybundle=bundle_with_one,
            new_member_identity=member2_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        member_ids = [e.member_id for e in bundle_with_two.entries]
        assert 'member_one' in member_ids, (
            f"member_one entry missing after adding member_two: {member_ids}"
        )
        assert 'member_two' in member_ids, (
            f"member_two entry missing from final bundle: {member_ids}"
        )
        assert founder_identity['member_id'] in member_ids, (
            f"Founder entry missing after adding two members: {member_ids}"
        )

        # member_one must still be able to decrypt
        m1_decrypted = get_cohort_private_key(
            keybundle=bundle_with_two,
            member_id='member_one',
            member_x25519_private=member1_identity['x25519_private'],
            member_ed25519_private=member1_identity['ed25519_private'],
        )
        assert m1_decrypted == cohort_private_key_bytes, (
            "member_one's decrypted key must match original after adding member_two"
        )


class TestAddMemberErrorCases:
    """Test error handling for invalid inputs."""

    @pytest.mark.issue_11
    def test_add_member_initiator_not_in_keybundle_raises_error(self, created_cohort, new_member_identity):
        """add_member raises ValueError when initiator is not in the KeyBundle."""
        from peermodel.delegation import add_member

        x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = generate_keypair()
        nonmember_identity = {
            'member_id': 'not_a_member',
            'x25519_public': x25519_pub,
            'x25519_private': x25519_priv,
            'ed25519_public': ed25519_pub,
            'ed25519_private': ed25519_priv,
        }

        _, keybundle, cohort_private_key_bytes = created_cohort

        with pytest.raises(ValueError) as exc_info:
            add_member(
                keybundle=keybundle,
                new_member_identity=new_member_identity,
                initiator_identity=nonmember_identity,
                cohort_private_key_bytes=cohort_private_key_bytes,
            )

        assert 'not_a_member' in str(exc_info.value), (
            f"Error message must identify the unauthorized initiator, got: {exc_info.value}"
        )

    @pytest.mark.issue_11
    def test_add_member_duplicate_member_raises_error(self, created_cohort, founder_identity):
        """add_member raises ValueError when new member is already in the KeyBundle."""
        from peermodel.delegation import add_member

        _, keybundle, cohort_private_key_bytes = created_cohort

        # Attempt to re-add the founder who is already a member
        with pytest.raises(ValueError) as exc_info:
            add_member(
                keybundle=keybundle,
                new_member_identity=founder_identity,
                initiator_identity=founder_identity,
                cohort_private_key_bytes=cohort_private_key_bytes,
            )

        assert 'founder' in str(exc_info.value), (
            f"Error message must identify the duplicate member, got: {exc_info.value}"
        )


class TestAddMemberInitiatorSigns:
    """Test that the initiator's signature is captured in the enrollment."""

    @pytest.mark.issue_11
    def test_add_member_new_entry_encrypted_to_new_member_not_initiator(
        self, created_cohort, founder_identity, new_member_identity
    ):
        """New member entry cannot be decrypted using initiator's private key.

        Verifies that the entry is encrypted to the new member's public key,
        not to the initiator's public key.
        """
        from peermodel.delegation import add_member
        from peermodel.exceptions import DecryptionError
        from peermodel.primitives import decrypt_from_sender

        _, keybundle, cohort_private_key_bytes = created_cohort

        updated_bundle = add_member(
            keybundle=keybundle,
            new_member_identity=new_member_identity,
            initiator_identity=founder_identity,
            cohort_private_key_bytes=cohort_private_key_bytes,
        )

        new_entry = next(
            e for e in updated_bundle.entries
            if e.member_id == new_member_identity['member_id']
        )

        # Trying to decrypt the new member's entry with the initiator's key should fail
        with pytest.raises(DecryptionError):
            decrypt_from_sender(
                ciphertext=new_entry.encrypted_key_material,
                nonce=new_entry.nonce,
                tag=new_entry.tag,
                ephemeral_public_key_der=new_entry.ephemeral_public_key_der,
                recipient_private_key_der=founder_identity['x25519_private'],
            )
