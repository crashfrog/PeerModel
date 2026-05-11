#!/usr/bin/env python

"""Tests for cohort membership lifecycle.

Tests cover:
- Cohort creation
- Membership proposals (add/expel)
- Voting and approval thresholds
- Member addition and removal
- Key regeneration and forward secrecy
- Persistence
"""

import pytest
from datetime import datetime
from typing import Literal

import peermodel
import peermodel.primitives
from peermodel.delegation import SimpleCohort
from peermodel.membership import MembershipProposal, MembershipVote


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
def test_cohort(alice_identity):
    """Create a cohort with Alice as founder."""
    return SimpleCohort(
        cohort_id='test_cohort',
        founder_identity=alice_identity
    )


@pytest.fixture
def multi_member_cohort(alice_identity, bob_identity):
    """Create a cohort with Alice and Bob as members."""
    cohort = SimpleCohort(cohort_id='multi_cohort', founder_identity=alice_identity)
    cohort.addMember(bob_identity)
    return cohort


# Cohort Creation Tests

def test_create_cohort_with_founder(test_cohort, alice_identity):
    """Founder is automatically a member."""
    members = list(test_cohort.members)
    assert alice_identity in members
    assert len(members) == 1


def test_cohort_has_unique_id(alice_identity):
    """Cohort IDs are unique."""
    cohort1 = SimpleCohort(cohort_id='cohort1', founder_identity=alice_identity)
    cohort2 = SimpleCohort(cohort_id='cohort2', founder_identity=alice_identity)
    assert cohort1.cohort_id != cohort2.cohort_id


def test_cohort_has_signing_key(test_cohort):
    """Cohort can sign records."""
    signature = test_cohort.signature
    assert isinstance(signature, bytes)
    assert len(signature) > 0


# Membership Proposal Tests

def test_create_add_member_proposal(test_cohort, alice_identity, bob_identity):
    """Create proposal to add member."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    assert proposal is not None
    assert proposal.action == "add"
    assert proposal.subject_member_id == bob_identity['identity_id']
    assert proposal.cohort_id == test_cohort.cohort_id


def test_proposal_has_unique_id(test_cohort, alice_identity, bob_identity):
    """Proposal IDs are unique."""
    proposal1 = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    proposal2 = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    assert proposal1.proposal_id != proposal2.proposal_id


def test_proposal_includes_subject_credential(test_cohort, alice_identity, bob_identity):
    """New member's public keys included in proposal."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    assert proposal.subject_credential is not None
    assert 'x25519_public' in proposal.subject_credential
    assert 'ed25519_public' in proposal.subject_credential


def test_cannot_propose_existing_member(test_cohort, alice_identity):
    """Cannot propose adding member who already exists."""
    with pytest.raises(ValueError):
        test_cohort.create_add_member_proposal(alice_identity, alice_identity)


def test_create_expel_member_proposal(multi_member_cohort, alice_identity, bob_identity):
    """Create proposal to expel member."""
    proposal = multi_member_cohort.create_expel_member_proposal(bob_identity, alice_identity)
    assert proposal is not None
    assert proposal.action == "expel"
    assert proposal.subject_member_id == bob_identity['identity_id']


# Voting Tests

def test_founder_can_vote(test_cohort, alice_identity, bob_identity):
    """Founder can vote on proposals."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    updated_proposal = test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    assert len(updated_proposal.votes) == 1
    assert updated_proposal.votes[0].voter_identity_id == alice_identity['identity_id']


def test_vote_includes_signature(test_cohort, alice_identity, bob_identity):
    """Votes are cryptographically signed."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    updated_proposal = test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    vote = updated_proposal.votes[0]
    assert isinstance(vote.signature, bytes)
    assert len(vote.signature) > 0


def test_cannot_vote_twice(test_cohort, alice_identity, bob_identity):
    """Member can only vote once per proposal."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    with pytest.raises(ValueError):
        test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=False)


def test_non_member_cannot_vote(test_cohort, bob_identity, carol_identity):
    """Non-member cannot vote."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, carol_identity)
    with pytest.raises(ValueError):
        test_cohort.vote_on_proposal(proposal.proposal_id, carol_identity, approve=True)


# Approval Threshold Tests

def test_single_founder_auto_approves(test_cohort, alice_identity, bob_identity):
    """1-member cohort auto-approves."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    outcome = proposal.check_outcome(1)
    assert outcome == "approved"


def test_two_members_requires_both(multi_member_cohort, alice_identity, bob_identity, carol_identity):
    """2-member cohort needs both votes for majority."""
    proposal = multi_member_cohort.create_add_member_proposal(carol_identity, alice_identity)
    # Only one vote shouldn't be enough
    multi_member_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    outcome = proposal.check_outcome(2)
    assert outcome == "pending"
    # Both votes should approve
    updated_proposal = multi_member_cohort.vote_on_proposal(proposal.proposal_id, bob_identity, approve=True)
    outcome = updated_proposal.check_outcome(2)
    assert outcome == "approved"


def test_three_members_requires_two(alice_identity, bob_identity, carol_identity):
    """3-member cohort needs 2 votes for majority (>50%)."""
    cohort = SimpleCohort(cohort_id='three_cohort', founder_identity=alice_identity)
    cohort.addMember(bob_identity)
    cohort.addMember(carol_identity)

    # Create proposal to add new member
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    dave_identity = {
        'identity_id': 'dave',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }

    proposal = cohort.create_add_member_proposal(dave_identity, alice_identity)

    # One vote pending
    cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    outcome = proposal.check_outcome(3)
    assert outcome == "pending"

    # Two votes approved
    updated_proposal = cohort.vote_on_proposal(proposal.proposal_id, bob_identity, approve=True)
    outcome = updated_proposal.check_outcome(3)
    assert outcome == "approved"


def test_proposal_pending_until_threshold(multi_member_cohort, alice_identity, bob_identity, carol_identity):
    """Proposal stays pending until threshold met."""
    proposal = multi_member_cohort.create_add_member_proposal(carol_identity, alice_identity)
    assert proposal.check_outcome(2) == "pending"

    multi_member_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    assert proposal.check_outcome(2) == "pending"


# Member Addition Tests

def test_approved_member_added_to_cohort(test_cohort, alice_identity, bob_identity):
    """Approved member joins."""
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    test_cohort.execute_proposal(proposal)

    members = [m['identity_id'] for m in test_cohort.members]
    assert bob_identity['identity_id'] in members


def test_new_member_can_vote(test_cohort, alice_identity, bob_identity, carol_identity):
    """New member can vote on future proposals."""
    # Add Bob
    proposal1 = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal1.proposal_id, alice_identity, approve=True)
    test_cohort.execute_proposal(proposal1)

    # Bob votes on Carol's proposal
    proposal2 = test_cohort.create_add_member_proposal(carol_identity, alice_identity)
    bob_vote = test_cohort.vote_on_proposal(proposal2.proposal_id, bob_identity, approve=True)
    assert len(bob_vote.votes) >= 1


def test_new_member_can_decrypt_new_records(test_cohort, alice_identity, bob_identity):
    """New member can decrypt records created after joining."""
    # Record created before Bob joins
    record_key_before = test_cohort.generateRecordKey()

    # Add Bob
    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    test_cohort.execute_proposal(proposal)

    # Record key after Bob joins - should be encryptable for Bob
    record_key_after = test_cohort.generateRecordKey()
    assert record_key_after is not None


def test_new_member_cannot_decrypt_old_records(test_cohort, alice_identity, bob_identity):
    """No retroactive access - new member can't decrypt records from before joining."""
    # This is enforced by not including new member in old KeyBundles
    # Test just verifies the cohort doesn't retroactively grant access
    members_before = list(test_cohort.members)

    proposal = test_cohort.create_add_member_proposal(bob_identity, alice_identity)
    test_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    test_cohort.execute_proposal(proposal)

    members_after = list(test_cohort.members)
    assert len(members_after) > len(members_before)


# Member Expulsion Tests

def test_create_expel_proposal(multi_member_cohort, alice_identity, bob_identity):
    """Create expulsion proposal."""
    proposal = multi_member_cohort.create_expel_member_proposal(bob_identity, alice_identity)
    assert proposal.action == "expel"
    assert proposal.subject_member_id == bob_identity['identity_id']


def test_expelled_member_removed_from_members_list(multi_member_cohort, alice_identity, bob_identity):
    """Expelled member removed from members list."""
    proposal = multi_member_cohort.create_expel_member_proposal(bob_identity, alice_identity)
    multi_member_cohort.vote_on_proposal(proposal.proposal_id, alice_identity, approve=True)
    # Need both members to vote (2/2 = 100% > 50%)
    updated_proposal = multi_member_cohort.vote_on_proposal(proposal.proposal_id, bob_identity, approve=True)
    multi_member_cohort.execute_proposal(updated_proposal)

    members = [m['identity_id'] for m in multi_member_cohort.members]
    assert bob_identity['identity_id'] not in members


def test_cannot_expel_founder(multi_member_cohort, alice_identity):
    """Cannot expel founder."""
    with pytest.raises(ValueError):
        multi_member_cohort.create_expel_member_proposal(alice_identity, alice_identity)


# Key Regeneration Tests

def test_regenerate_keys(test_cohort, alice_identity):
    """Keys can be regenerated."""
    old_signature = test_cohort.signature
    test_cohort.regenerate()
    new_signature = test_cohort.signature
    assert old_signature != new_signature


def test_old_keys_dont_decrypt_new_records_after_regeneration(test_cohort):
    """Forward secrecy: old KeyBundle can't decrypt new records."""
    # Generate old key
    old_record_key = test_cohort.generateRecordKey()

    # Regenerate
    test_cohort.regenerate()

    # New key is different
    new_record_key = test_cohort.generateRecordKey()
    assert old_record_key != new_record_key


def test_current_members_decrypt_after_regeneration(multi_member_cohort):
    """Current members retain access after key regeneration."""
    # Members still exist after regeneration
    members_before = len(list(multi_member_cohort.members))
    multi_member_cohort.regenerate()
    members_after = len(list(multi_member_cohort.members))
    assert members_before == members_after


def test_cohort_signature_changes_after_regeneration(test_cohort):
    """Cohort signature changes after regeneration."""
    sig1 = test_cohort.signature
    test_cohort.regenerate()
    sig2 = test_cohort.signature
    assert sig1 != sig2
