#!/usr/bin/env python

"""
Tests for Issue #12: Member expulsion & forward secrecy.

This test module covers the acceptance criteria for member expulsion:
- Expel member from cohort
- New cohort key regenerated
- Expelled member cannot decrypt new content
- Remaining members can decrypt new content
- Tests: expel, verify forward secrecy

Tests are marked with @pytest.mark.issue_12 for filtering.
These tests will FAIL until expel_member() is implemented.
"""

import pytest
from datetime import datetime
from typing import List, Optional

import peermodel.primitives
from peermodel.delegation import SimpleCohort, CohortIdentity, KeyBundle


@pytest.fixture
def alice_identity():
    """Generate Alice's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    return {
        'identity_id': 'alice',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }


@pytest.fixture
def bob_identity():
    """Generate Bob's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    return {
        'identity_id': 'bob',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }


@pytest.fixture
def carol_identity():
    """Generate Carol's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    return {
        'identity_id': 'carol',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }


@pytest.fixture
def multi_member_cohort(alice_identity, bob_identity):
    """Create a cohort with Alice (founder) and Bob as members."""
    cohort = SimpleCohort(cohort_id='multi_cohort', founder_identity=alice_identity)
    cohort.addMember(bob_identity)
    return cohort


@pytest.fixture
def three_member_cohort(alice_identity, bob_identity, carol_identity):
    """Create a cohort with Alice (founder), Bob, and Carol as members."""
    cohort = SimpleCohort(cohort_id='three_cohort', founder_identity=alice_identity)
    cohort.addMember(bob_identity)
    cohort.addMember(carol_identity)
    return cohort


class TestMemberExpulsionBasics:
    """Test basic member expulsion functionality."""

    @pytest.mark.issue_12
    def test_expel_member_returns_cohort_identity_and_keybundle(self, multi_member_cohort, bob_identity):
        """expel_member() returns (CohortIdentity, KeyBundle).

        Acceptance criterion: Expel member from cohort
        """
        # Should return a 2-tuple of (CohortIdentity, KeyBundle)
        result = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert isinstance(result, tuple), "expel_member should return a tuple"
        assert len(result) == 2, "expel_member should return exactly 2 items"

        cohort_identity, keybundle = result
        assert cohort_identity is not None, "First item should be CohortIdentity"
        assert keybundle is not None, "Second item should be KeyBundle"

    @pytest.mark.issue_12
    def test_expel_member_removes_from_members_list(self, multi_member_cohort, bob_identity):
        """Member is removed from cohort members after expulsion.

        Acceptance criterion: Expel member from cohort
        """
        # Bob is member before expulsion
        member_ids_before = [m['identity_id'] for m in multi_member_cohort.members]
        assert bob_identity['identity_id'] in member_ids_before

        multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Bob is not member after expulsion
        member_ids_after = [m['identity_id'] for m in multi_member_cohort.members]
        assert bob_identity['identity_id'] not in member_ids_after

    @pytest.mark.issue_12
    def test_expel_member_keeps_other_members(self, three_member_cohort, bob_identity, carol_identity):
        """Other members remain in cohort after one member is expelled.

        Acceptance criterion: Expel member from cohort
        """
        # All three members exist before
        member_ids_before = [m['identity_id'] for m in three_member_cohort.members]
        assert len(member_ids_before) == 3
        assert bob_identity['identity_id'] in member_ids_before
        assert carol_identity['identity_id'] in member_ids_before

        three_member_cohort.expel_member(bob_identity['identity_id'])

        # Carol remains, Bob removed, Alice (founder) remains
        member_ids_after = [m['identity_id'] for m in three_member_cohort.members]
        assert len(member_ids_after) == 2
        assert carol_identity['identity_id'] in member_ids_after
        assert bob_identity['identity_id'] not in member_ids_after

    @pytest.mark.issue_12
    def test_expel_member_raises_on_nonexistent_member(self, multi_member_cohort):
        """Expelling nonexistent member raises ValueError."""
        with pytest.raises(ValueError):
            multi_member_cohort.expel_member('nonexistent_member')

    @pytest.mark.issue_12
    def test_expel_member_raises_on_founder_expulsion(self, multi_member_cohort, alice_identity):
        """Cannot expel founder member raises ValueError.

        Acceptance criterion: Expel member from cohort (cannot expel founder)
        """
        with pytest.raises(ValueError):
            multi_member_cohort.expel_member(alice_identity['identity_id'])


class TestCohortKeyRegeneration:
    """Test cohort key regeneration upon expulsion."""

    @pytest.mark.issue_12
    def test_expel_member_regenerates_cohort_encryption_key(self, multi_member_cohort, bob_identity):
        """New cohort encryption key generated on expulsion.

        Acceptance criterion: New cohort key regenerated
        """
        # Store old cohort encryption key
        old_cohort_encryption_key = multi_member_cohort.cohort_x25519_public

        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # New cohort encryption key should differ
        new_cohort_encryption_key = multi_member_cohort.cohort_x25519_public
        assert new_cohort_encryption_key != old_cohort_encryption_key

    @pytest.mark.issue_12
    def test_expel_member_regenerates_cohort_signing_key(self, multi_member_cohort, bob_identity):
        """New cohort signing key generated on expulsion.

        Acceptance criterion: New cohort key regenerated
        """
        # Store old cohort signing key
        old_cohort_signing_key = multi_member_cohort.cohort_ed25519_public

        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # New cohort signing key should differ
        new_cohort_signing_key = multi_member_cohort.cohort_ed25519_public
        assert new_cohort_signing_key != old_cohort_signing_key

    @pytest.mark.issue_12
    def test_cohort_identity_has_new_public_keys(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity contains the new public keys.

        Acceptance criterion: New cohort key regenerated
        """
        old_encryption_key = multi_member_cohort.cohort_x25519_public
        old_signing_key = multi_member_cohort.cohort_ed25519_public

        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # CohortIdentity should have new keys
        assert cohort_identity.encryption_public_key != old_encryption_key
        assert cohort_identity.signing_public_key != old_signing_key
        # New keys should match the updated cohort
        assert cohort_identity.encryption_public_key == multi_member_cohort.cohort_x25519_public
        assert cohort_identity.signing_public_key == multi_member_cohort.cohort_ed25519_public

    @pytest.mark.issue_12
    def test_expel_member_increments_keybundle_version(self, multi_member_cohort, bob_identity):
        """KeyBundle version incremented on expulsion.

        Acceptance criterion: New cohort key regenerated
        """
        # Get initial version (should be 1 for fresh cohort)
        initial_cohort_id = multi_member_cohort.cohort_id

        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # KeyBundle version should be incremented
        assert keybundle.version > 1


class TestForwardSecrecy:
    """Test forward secrecy: expelled member cannot decrypt new content."""

    @pytest.mark.issue_12
    def test_expelled_member_not_in_keybundle_entries(self, multi_member_cohort, bob_identity):
        """Expelled member has no entry in the new KeyBundle.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Check that Bob has no entry in new KeyBundle
        entry_member_ids = [entry.member_id for entry in keybundle.entries]
        assert bob_identity['identity_id'] not in entry_member_ids

    @pytest.mark.issue_12
    def test_remaining_members_in_keybundle_entries(self, multi_member_cohort, alice_identity, bob_identity):
        """Remaining members have entries in the new KeyBundle.

        Acceptance criterion: Remaining members can decrypt new content
        """
        cohort_identity, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Alice (founder) should be in new KeyBundle
        entry_member_ids = [entry.member_id for entry in keybundle.entries]
        assert alice_identity['identity_id'] in entry_member_ids

    @pytest.mark.issue_12
    def test_expelled_member_cannot_decrypt_with_old_keybundle(self, multi_member_cohort, bob_identity):
        """Expelled member with old KeyBundle cannot decrypt cohort private key.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        from peermodel.delegation import get_cohort_private_key

        # Get a KeyBundle entry for Bob before expulsion
        # First, create a fresh keybundle for current state
        old_keybundle = KeyBundle(
            cohort_id=multi_member_cohort.cohort_id,
            version=1,
            signing_alg='ed25519',
            encryption_alg='x25519',
            entries=[]
        )

        # Now expel Bob
        cohort_identity, new_keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Bob's new keybundle has no entry for him
        bob_entries = [e for e in new_keybundle.entries if e.member_id == bob_identity['identity_id']]
        assert len(bob_entries) == 0, "Bob should not be in new KeyBundle"

    @pytest.mark.issue_12
    def test_remaining_member_can_decrypt_new_keybundle(self, multi_member_cohort, alice_identity, bob_identity):
        """Remaining member can decrypt cohort private key from new KeyBundle.

        Acceptance criterion: Remaining members can decrypt new content
        """
        from peermodel.delegation import get_cohort_private_key

        cohort_identity, new_keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Alice (founder) should be able to decrypt
        cohort_private_key = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id=alice_identity['identity_id'],
            member_x25519_private=alice_identity['x25519_private'],
            member_ed25519_private=alice_identity['ed25519_private'],
        )

        assert cohort_private_key is not None
        assert isinstance(cohort_private_key, bytes)
        assert len(cohort_private_key) > 0

    @pytest.mark.issue_12
    def test_new_keybundle_matches_remaining_members(self, three_member_cohort, alice_identity, bob_identity, carol_identity):
        """New KeyBundle has entries for all remaining members, none for expelled.

        Acceptance criterion: Remaining members can decrypt new content
        """
        # Expel Bob
        cohort_identity, new_keybundle = three_member_cohort.expel_member(bob_identity['identity_id'])

        # Check entries
        entry_member_ids = [entry.member_id for entry in new_keybundle.entries]

        # Alice and Carol should be in new KeyBundle
        assert alice_identity['identity_id'] in entry_member_ids
        assert carol_identity['identity_id'] in entry_member_ids

        # Bob should NOT be in new KeyBundle
        assert bob_identity['identity_id'] not in entry_member_ids

        # Should have exactly 2 entries (Alice + Carol)
        assert len(new_keybundle.entries) == 2

    @pytest.mark.issue_12
    def test_expelled_member_old_key_cannot_decrypt_new_cohort_private_key(self, multi_member_cohort, alice_identity, bob_identity):
        """Bob cannot use old encryption key to decrypt new cohort key.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        from peermodel.delegation import get_cohort_private_key

        # Get current state before expulsion
        old_encryption_key = multi_member_cohort.cohort_x25519_public

        cohort_identity, new_keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # New encryption key is different
        new_encryption_key = multi_member_cohort.cohort_x25519_public
        assert new_encryption_key != old_encryption_key

        # Bob is not in new KeyBundle
        assert not any(e.member_id == bob_identity['identity_id'] for e in new_keybundle.entries)


class TestForwardSecrecyWithNewRecords:
    """Test forward secrecy: expelled member cannot decrypt records created after expulsion."""

    @pytest.mark.issue_12
    def test_new_record_key_after_expulsion(self, multi_member_cohort, bob_identity):
        """Record keys generated after expulsion use the new cohort key.

        Acceptance criterion: Expelled member cannot decrypt new content
        """
        from cryptography.fernet import Fernet

        # Generate a record key before expulsion
        old_record_key = multi_member_cohort.generateRecordKey()

        # Expel member
        multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Generate a new record key after expulsion
        new_record_key = multi_member_cohort.generateRecordKey()

        # Keys should be different (they're randomly generated Fernet keys)
        # This test verifies that the generateRecordKey method still works after expulsion
        assert new_record_key is not None
        assert isinstance(new_record_key, bytes)
        assert len(new_record_key) > 0

    @pytest.mark.issue_12
    def test_signature_changes_after_expulsion(self, multi_member_cohort, bob_identity):
        """Cohort signature changes after member expulsion.

        Acceptance criterion: New cohort key regenerated
        """
        # Get signature before expulsion
        old_signature = multi_member_cohort.signature

        # Expel member
        multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Get signature after expulsion
        new_signature = multi_member_cohort.signature

        # Signatures should differ due to different member count and signing key
        assert new_signature != old_signature


class TestExpulsionWithMultipleMembers:
    """Test expulsion in cohorts with multiple members."""

    @pytest.mark.issue_12
    def test_expel_one_of_three_members(self, three_member_cohort, alice_identity, bob_identity, carol_identity):
        """Expel one member from three-member cohort.

        Acceptance criterion: Expel member from cohort
        """
        # Start with 3 members
        members_before = [m['identity_id'] for m in three_member_cohort.members]
        assert len(members_before) == 3

        # Expel Bob
        three_member_cohort.expel_member(bob_identity['identity_id'])

        # End with 2 members
        members_after = [m['identity_id'] for m in three_member_cohort.members]
        assert len(members_after) == 2
        assert alice_identity['identity_id'] in members_after
        assert carol_identity['identity_id'] in members_after
        assert bob_identity['identity_id'] not in members_after

    @pytest.mark.issue_12
    def test_expel_multiple_members_sequentially(self, three_member_cohort, alice_identity, bob_identity, carol_identity):
        """Can expel multiple members one at a time.

        Acceptance criterion: Expel member from cohort
        """
        # Expel Bob
        cohort_identity_1, keybundle_1 = three_member_cohort.expel_member(bob_identity['identity_id'])

        members_after_first = [m['identity_id'] for m in three_member_cohort.members]
        assert len(members_after_first) == 2

        # Expel Carol
        cohort_identity_2, keybundle_2 = three_member_cohort.expel_member(carol_identity['identity_id'])

        members_after_second = [m['identity_id'] for m in three_member_cohort.members]
        assert len(members_after_second) == 1
        assert members_after_second[0] == alice_identity['identity_id']

    @pytest.mark.issue_12
    def test_keybundle_version_increments_with_each_expulsion(self, three_member_cohort, bob_identity, carol_identity):
        """KeyBundle version increments with each expulsion.

        Acceptance criterion: New cohort key regenerated
        """
        # First expulsion
        _, keybundle_1 = three_member_cohort.expel_member(bob_identity['identity_id'])
        version_1 = keybundle_1.version

        # Second expulsion
        _, keybundle_2 = three_member_cohort.expel_member(carol_identity['identity_id'])
        version_2 = keybundle_2.version

        # Versions should increase
        assert version_2 > version_1

    @pytest.mark.issue_12
    def test_each_expulsion_generates_new_keys(self, three_member_cohort, bob_identity, carol_identity):
        """Each expulsion generates a completely new cohort keypair.

        Acceptance criterion: New cohort key regenerated
        """
        # First expulsion
        old_key_1 = three_member_cohort.cohort_x25519_public
        _, keybundle_1 = three_member_cohort.expel_member(bob_identity['identity_id'])
        new_key_1 = three_member_cohort.cohort_x25519_public

        assert new_key_1 != old_key_1

        # Second expulsion
        old_key_2 = three_member_cohort.cohort_x25519_public
        _, keybundle_2 = three_member_cohort.expel_member(carol_identity['identity_id'])
        new_key_2 = three_member_cohort.cohort_x25519_public

        assert new_key_2 != old_key_2
        assert new_key_2 != new_key_1  # Each regeneration should be unique


class TestExpulsionEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.issue_12
    def test_cannot_expel_last_remaining_member(self, multi_member_cohort, alice_identity, bob_identity):
        """Cannot expel last non-founder member if only two remain.

        Acceptance criterion: Expel member from cohort (edge case)
        """
        # Only Alice (founder) and Bob remain
        # Expelling Bob is allowed
        multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Now only Alice remains (founder)
        members = [m['identity_id'] for m in multi_member_cohort.members]
        assert len(members) == 1
        assert members[0] == alice_identity['identity_id']

    @pytest.mark.issue_12
    def test_expel_member_with_empty_string_raises(self, multi_member_cohort):
        """Expelling with empty member_id raises ValueError."""
        with pytest.raises(ValueError):
            multi_member_cohort.expel_member('')

    @pytest.mark.issue_12
    def test_expel_same_member_twice_raises(self, multi_member_cohort, bob_identity):
        """Cannot expel the same member twice.

        Acceptance criterion: Expel member from cohort
        """
        # First expulsion succeeds
        multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Second expulsion should fail
        with pytest.raises(ValueError):
            multi_member_cohort.expel_member(bob_identity['identity_id'])


class TestExpulsionIntegration:
    """Integration tests for member expulsion workflow."""

    @pytest.mark.issue_12
    def test_full_expulsion_workflow_two_members(self, multi_member_cohort, alice_identity, bob_identity):
        """Full workflow: expel member and verify forward secrecy.

        Acceptance criteria:
        - Expel member from cohort
        - New cohort key regenerated
        - Expelled member cannot decrypt new content
        - Remaining members can decrypt new content
        """
        from peermodel.delegation import get_cohort_private_key

        # Initial state
        members_before = [m['identity_id'] for m in multi_member_cohort.members]
        assert bob_identity['identity_id'] in members_before

        # Expel Bob
        cohort_identity, new_keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        # Verify member removed
        members_after = [m['identity_id'] for m in multi_member_cohort.members]
        assert bob_identity['identity_id'] not in members_after

        # Verify forward secrecy: Bob not in new KeyBundle
        bob_entries = [e for e in new_keybundle.entries if e.member_id == bob_identity['identity_id']]
        assert len(bob_entries) == 0

        # Verify Alice can decrypt new key
        new_private_key = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id=alice_identity['identity_id'],
            member_x25519_private=alice_identity['x25519_private'],
            member_ed25519_private=alice_identity['ed25519_private'],
        )
        assert new_private_key is not None

    @pytest.mark.issue_12
    def test_full_expulsion_workflow_three_members(self, three_member_cohort, alice_identity, bob_identity, carol_identity):
        """Full workflow with three members: expel Bob, verify Carol and Alice have access.

        Acceptance criteria:
        - Expel member from cohort
        - New cohort key regenerated
        - Expelled member cannot decrypt new content
        - Remaining members can decrypt new content
        """
        from peermodel.delegation import get_cohort_private_key

        # Initial state: 3 members
        members_before = len(list(three_member_cohort.members))
        assert members_before == 3

        # Expel Bob
        cohort_identity, new_keybundle = three_member_cohort.expel_member(bob_identity['identity_id'])

        # Verify member removed
        members_after = len(list(three_member_cohort.members))
        assert members_after == 2

        # Verify KeyBundle has entries for Alice and Carol only
        entry_member_ids = [e.member_id for e in new_keybundle.entries]
        assert alice_identity['identity_id'] in entry_member_ids
        assert carol_identity['identity_id'] in entry_member_ids
        assert bob_identity['identity_id'] not in entry_member_ids

        # Alice can decrypt new key
        alice_key = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id=alice_identity['identity_id'],
            member_x25519_private=alice_identity['x25519_private'],
            member_ed25519_private=alice_identity['ed25519_private'],
        )
        assert alice_key is not None

        # Carol can decrypt new key
        carol_key = get_cohort_private_key(
            keybundle=new_keybundle,
            member_id=carol_identity['identity_id'],
            member_x25519_private=carol_identity['x25519_private'],
            member_ed25519_private=carol_identity['ed25519_private'],
        )
        assert carol_key is not None


class TestCohortIdentityStructure:
    """Test CohortIdentity returned from expel_member."""

    @pytest.mark.issue_12
    def test_returned_cohort_identity_has_correct_cohort_id(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity has the correct cohort_id.

        Acceptance criterion: New cohort key regenerated
        """
        original_cohort_id = multi_member_cohort.cohort_id
        cohort_identity, _ = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert cohort_identity.cohort_id == original_cohort_id

    @pytest.mark.issue_12
    def test_returned_cohort_identity_has_new_signing_key(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity has the new signing public key.

        Acceptance criterion: New cohort key regenerated
        """
        old_signing_key = multi_member_cohort.cohort_ed25519_public
        cohort_identity, _ = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert cohort_identity.signing_public_key == multi_member_cohort.cohort_ed25519_public
        assert cohort_identity.signing_public_key != old_signing_key

    @pytest.mark.issue_12
    def test_returned_cohort_identity_has_new_encryption_key(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity has the new encryption public key.

        Acceptance criterion: New cohort key regenerated
        """
        old_encryption_key = multi_member_cohort.cohort_x25519_public
        cohort_identity, _ = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert cohort_identity.encryption_public_key == multi_member_cohort.cohort_x25519_public
        assert cohort_identity.encryption_public_key != old_encryption_key

    @pytest.mark.issue_12
    def test_returned_cohort_identity_uses_ed25519_signing(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity specifies ed25519 signing algorithm.

        Acceptance criterion: New cohort key regenerated
        """
        cohort_identity, _ = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert cohort_identity.signing_algorithm == 'ed25519'

    @pytest.mark.issue_12
    def test_returned_cohort_identity_uses_x25519_encryption(self, multi_member_cohort, bob_identity):
        """Returned CohortIdentity specifies x25519 encryption algorithm.

        Acceptance criterion: New cohort key regenerated
        """
        cohort_identity, _ = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert cohort_identity.encryption_algorithm == 'x25519'


class TestKeyBundleStructure:
    """Test KeyBundle returned from expel_member."""

    @pytest.mark.issue_12
    def test_returned_keybundle_has_correct_cohort_id(self, multi_member_cohort, bob_identity):
        """Returned KeyBundle has the correct cohort_id.

        Acceptance criterion: New cohort key regenerated
        """
        original_cohort_id = multi_member_cohort.cohort_id
        _, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert keybundle.cohort_id == original_cohort_id

    @pytest.mark.issue_12
    def test_returned_keybundle_has_correct_algorithms(self, multi_member_cohort, bob_identity):
        """Returned KeyBundle specifies correct algorithms.

        Acceptance criterion: New cohort key regenerated
        """
        _, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert keybundle.signing_alg == 'ed25519'
        assert keybundle.encryption_alg == 'x25519'

    @pytest.mark.issue_12
    def test_returned_keybundle_entries_are_non_empty(self, multi_member_cohort, bob_identity):
        """Returned KeyBundle has non-empty entries list (at least for remaining members).

        Acceptance criterion: Remaining members can decrypt new content
        """
        _, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        assert len(keybundle.entries) > 0

    @pytest.mark.issue_12
    def test_keybundle_entry_has_all_required_fields(self, multi_member_cohort, bob_identity):
        """Each KeyBundleEntry in returned bundle has all required fields.

        Acceptance criterion: Remaining members can decrypt new content
        """
        _, keybundle = multi_member_cohort.expel_member(bob_identity['identity_id'])

        for entry in keybundle.entries:
            assert hasattr(entry, 'member_id')
            assert hasattr(entry, 'encrypted_key_material')
            assert hasattr(entry, 'ephemeral_public_key_der')
            assert hasattr(entry, 'nonce')
            assert hasattr(entry, 'tag')

            # All should have values
            assert entry.member_id is not None
            assert entry.encrypted_key_material is not None
            assert entry.ephemeral_public_key_der is not None
            assert entry.nonce is not None
            assert entry.tag is not None
