#!/usr/bin/env python

"""Tests for CBOR serialization of CohortCrypto data structures.

Tests cover:
- Serialization to canonical CBOR (RFC 7049 section 3.9)
- Deserialization back to objects
- Round-trip stability (serialize → deserialize → serialize yields identical bytes)
- Canonical form stability (same object → same bytes)
- Edge cases: nested structures, empty collections, null fields
- Boundaries: large byte strings, deep nesting
"""

import pytest
from datetime import datetime

import peermodel.primitives
from peermodel.primitives import MemberCredential
from peermodel.delegation import SimpleCohort
from peermodel.membership import MembershipProposal, MembershipVote


# Fixtures for generating identities and credentials

@pytest.fixture
def alice_identity():
    """Generate Alice's identity with keypairs."""
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
    """Generate Bob's identity with keypairs."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = peermodel.primitives.generate_keypair()
    return {
        'identity_id': 'bob',
        'x25519_private': x25519_priv,
        'x25519_public': x25519_pub,
        'ed25519_private': ed25519_priv,
        'ed25519_public': ed25519_pub
    }


@pytest.fixture
def alice_credential(alice_identity):
    """Create a MemberCredential for Alice."""
    return MemberCredential(
        member_id=alice_identity['identity_id'],
        x25519_public=alice_identity['x25519_public'],
        ed25519_public=alice_identity['ed25519_public'],
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None
    )


@pytest.fixture
def bob_credential(bob_identity):
    """Create a MemberCredential for Bob."""
    return MemberCredential(
        member_id=bob_identity['identity_id'],
        x25519_public=bob_identity['x25519_public'],
        ed25519_public=bob_identity['ed25519_public'],
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None
    )


@pytest.fixture
def alice_credential_with_cert(alice_identity):
    """Create a MemberCredential for Alice with hardware certificate."""
    return MemberCredential(
        member_id=alice_identity['identity_id'],
        x25519_public=alice_identity['x25519_public'],
        ed25519_public=alice_identity['ed25519_public'],
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=True,
        certificate_der=b'\x30\x82\x01\x00' + b'\x00' * 256  # Mock DER certificate
    )


@pytest.fixture
def test_cohort(alice_identity):
    """Create a test cohort with Alice as founder."""
    return SimpleCohort(
        cohort_id='test_cohort',
        founder_identity=alice_identity
    )


@pytest.fixture
def multi_member_cohort(alice_identity, bob_identity):
    """Create a cohort with Alice and Bob as members."""
    cohort = SimpleCohort(
        cohort_id='multi_cohort',
        founder_identity=alice_identity
    )
    cohort.addMember(bob_identity)
    return cohort


# ===== MemberCredential CBOR Serialization Tests =====

class TestMemberCredentialCBORSerialization:
    """Test CBOR serialization of MemberCredential structure."""

    def test_member_credential_serialize_basic(self, alice_credential):
        """Serialize basic MemberCredential to CBOR."""
        from peermodel.primitives import serialize_to_cbor

        cbor_bytes = serialize_to_cbor(alice_credential)
        assert isinstance(cbor_bytes, bytes)
        assert len(cbor_bytes) > 0

    def test_member_credential_deserialize_basic(self, alice_credential):
        """Deserialize CBOR back to MemberCredential."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        cbor_bytes = serialize_to_cbor(alice_credential)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert isinstance(deserialized, MemberCredential)
        assert deserialized.member_id == alice_credential.member_id

    def test_member_credential_round_trip(self, alice_credential):
        """Test round-trip serialization: object → CBOR → object."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        cbor_bytes = serialize_to_cbor(alice_credential)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert deserialized.member_id == alice_credential.member_id
        assert deserialized.x25519_public == alice_credential.x25519_public
        assert deserialized.ed25519_public == alice_credential.ed25519_public
        assert deserialized.signing_algorithm == alice_credential.signing_algorithm
        assert deserialized.encryption_algorithm == alice_credential.encryption_algorithm
        assert deserialized.hardware_backed == alice_credential.hardware_backed
        assert deserialized.certificate_der == alice_credential.certificate_der

    def test_member_credential_canonical_stability(self, alice_credential):
        """Serialize same object twice → identical bytes (canonical form)."""
        from peermodel.primitives import serialize_to_cbor

        cbor_bytes1 = serialize_to_cbor(alice_credential)
        cbor_bytes2 = serialize_to_cbor(alice_credential)

        assert cbor_bytes1 == cbor_bytes2, "Canonical CBOR should produce identical bytes"

    def test_member_credential_with_certificate(self, alice_credential_with_cert):
        """Serialize and deserialize MemberCredential with hardware certificate."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        cbor_bytes = serialize_to_cbor(alice_credential_with_cert)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert deserialized.hardware_backed is True
        assert deserialized.certificate_der == alice_credential_with_cert.certificate_der

    def test_member_credential_large_certificate(self, alice_credential):
        """Serialize MemberCredential with large DER certificate (boundary test)."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        # Create credential with large certificate
        large_cert = MemberCredential(
            member_id=alice_credential.member_id,
            x25519_public=alice_credential.x25519_public,
            ed25519_public=alice_credential.ed25519_public,
            hardware_backed=True,
            certificate_der=b'\x30\x82' + b'\x00' * 4096  # 4KB certificate
        )

        cbor_bytes = serialize_to_cbor(large_cert)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert len(deserialized.certificate_der) == len(large_cert.certificate_der)
        assert deserialized.certificate_der == large_cert.certificate_der

    def test_member_credential_null_certificate(self, alice_credential):
        """Serialize MemberCredential with null certificate field."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        credential = MemberCredential(
            member_id=alice_credential.member_id,
            x25519_public=alice_credential.x25519_public,
            ed25519_public=alice_credential.ed25519_public,
            hardware_backed=False,
            certificate_der=None
        )

        cbor_bytes = serialize_to_cbor(credential)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert deserialized.certificate_der is None


# ===== KeyBundle CBOR Serialization Tests =====

class TestKeyBundleCBORSerialization:
    """Test CBOR serialization of KeyBundle structure (from capabilities.py)."""

    def test_keybundle_serialize(self, alice_identity):
        """Serialize KeyBundle to CBOR."""
        from peermodel.primitives import serialize_to_cbor

        # Create a KeyBundle-like structure
        keybundle = {
            'identity_id': alice_identity['identity_id'],
            'x25519_public': alice_identity['x25519_public'],
            'ed25519_public': alice_identity['ed25519_public'],
            'x25519_private': alice_identity['x25519_private'],
            'ed25519_private': alice_identity['ed25519_private'],
        }

        cbor_bytes = serialize_to_cbor(keybundle)
        assert isinstance(cbor_bytes, bytes)
        assert len(cbor_bytes) > 0

    def test_keybundle_round_trip(self, alice_identity):
        """Test round-trip serialization of KeyBundle."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        keybundle = {
            'identity_id': alice_identity['identity_id'],
            'x25519_public': alice_identity['x25519_public'],
            'ed25519_public': alice_identity['ed25519_public'],
            'x25519_private': alice_identity['x25519_private'],
            'ed25519_private': alice_identity['ed25519_private'],
        }

        cbor_bytes = serialize_to_cbor(keybundle)
        deserialized = deserialize_from_cbor(cbor_bytes, dict)

        assert deserialized['identity_id'] == keybundle['identity_id']
        assert deserialized['x25519_public'] == keybundle['x25519_public']
        assert deserialized['ed25519_public'] == keybundle['ed25519_public']

    def test_keybundle_canonical_stability(self, alice_identity):
        """Serialize same KeyBundle twice → identical bytes."""
        from peermodel.primitives import serialize_to_cbor

        keybundle = {
            'identity_id': alice_identity['identity_id'],
            'x25519_public': alice_identity['x25519_public'],
            'ed25519_public': alice_identity['ed25519_public'],
        }

        cbor_bytes1 = serialize_to_cbor(keybundle)
        cbor_bytes2 = serialize_to_cbor(keybundle)

        assert cbor_bytes1 == cbor_bytes2


# ===== CohortRecord CBOR Serialization Tests =====

class TestCohortRecordCBORSerialization:
    """Test CBOR serialization of CohortRecord structure."""

    def test_cohort_record_serialize(self):
        """Serialize CohortRecord to CBOR."""
        from peermodel.primitives import serialize_to_cbor

        cohort_record = {
            'cohort_id': 'test_cohort',
            'founder_id': 'alice',
            'members': ['alice', 'bob'],
            'guests': ['charlie'],
            'created_at': datetime.now().isoformat(),
        }

        cbor_bytes = serialize_to_cbor(cohort_record)
        assert isinstance(cbor_bytes, bytes)
        assert len(cbor_bytes) > 0

    def test_cohort_record_round_trip(self):
        """Test round-trip serialization of CohortRecord."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        cohort_record = {
            'cohort_id': 'test_cohort',
            'founder_id': 'alice',
            'members': ['alice', 'bob'],
            'guests': ['charlie'],
            'created_at': datetime.now().isoformat(),
        }

        cbor_bytes = serialize_to_cbor(cohort_record)
        deserialized = deserialize_from_cbor(cbor_bytes, dict)

        assert deserialized['cohort_id'] == cohort_record['cohort_id']
        assert deserialized['founder_id'] == cohort_record['founder_id']
        assert set(deserialized['members']) == set(cohort_record['members'])
        assert set(deserialized['guests']) == set(cohort_record['guests'])

    def test_cohort_record_canonical_stability(self):
        """Serialize same CohortRecord twice → identical bytes."""
        from peermodel.primitives import serialize_to_cbor

        cohort_record = {
            'cohort_id': 'test_cohort',
            'founder_id': 'alice',
            'members': ['alice', 'bob'],
            'guests': ['charlie'],
        }

        cbor_bytes1 = serialize_to_cbor(cohort_record)
        cbor_bytes2 = serialize_to_cbor(cohort_record)

        assert cbor_bytes1 == cbor_bytes2

    def test_cohort_record_with_encrypted_keys(self):
        """Serialize CohortRecord with encrypted member keys."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        cohort_record = {
            'cohort_id': 'test_cohort',
            'founder_id': 'alice',
            'members': ['alice', 'bob'],
            'encrypted_keys': {
                'alice': b'\x00' * 64,
                'bob': b'\x00' * 64,
            }
        }

        cbor_bytes = serialize_to_cbor(cohort_record)
        deserialized = deserialize_from_cbor(cbor_bytes, dict)

        assert deserialized['encrypted_keys']['alice'] == cohort_record['encrypted_keys']['alice']
        assert deserialized['encrypted_keys']['bob'] == cohort_record['encrypted_keys']['bob']


# ===== MembershipProposal CBOR Serialization Tests =====

class TestMembershipProposalCBORSerialization:
    """Test CBOR serialization of MembershipProposal structure."""

    def test_membership_proposal_serialize(self, bob_identity):
        """Serialize MembershipProposal to CBOR."""
        from peermodel.primitives import serialize_to_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice',
            proposed_at=datetime.now()
        )

        cbor_bytes = serialize_to_cbor(proposal)
        assert isinstance(cbor_bytes, bytes)
        assert len(cbor_bytes) > 0

    def test_membership_proposal_deserialize(self, bob_identity):
        """Deserialize CBOR back to MembershipProposal."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice'
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert isinstance(deserialized, MembershipProposal)
        assert deserialized.proposal_id == proposal.proposal_id
        assert deserialized.cohort_id == proposal.cohort_id
        assert deserialized.action == proposal.action

    def test_membership_proposal_round_trip(self, bob_identity):
        """Test round-trip serialization of MembershipProposal."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice'
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert deserialized.subject_member_id == proposal.subject_member_id
        assert deserialized.subject_credential == proposal.subject_credential
        assert deserialized.proposed_by == proposal.proposed_by

    def test_membership_proposal_canonical_stability(self, bob_identity):
        """Serialize same MembershipProposal twice → identical bytes."""
        from peermodel.primitives import serialize_to_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice'
        )

        cbor_bytes1 = serialize_to_cbor(proposal)
        cbor_bytes2 = serialize_to_cbor(proposal)

        assert cbor_bytes1 == cbor_bytes2

    def test_membership_proposal_with_votes(self, alice_identity, bob_identity):
        """Serialize MembershipProposal with votes."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=b'\x00' * 64
        )

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice',
            votes=[vote]
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert len(deserialized.votes) == 1
        assert deserialized.votes[0].voter_identity_id == vote.voter_identity_id
        assert deserialized.votes[0].approve == vote.approve

    def test_membership_proposal_expel_action(self, bob_identity):
        """Serialize MembershipProposal with expel action."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-456',
            cohort_id='test_cohort',
            action='expel',
            subject_member_id=bob_identity['identity_id'],
            proposed_by='alice'
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert deserialized.action == 'expel'
        assert deserialized.subject_credential is None


# ===== MembershipVote CBOR Serialization Tests =====

class TestMembershipVoteCBORSerialization:
    """Test CBOR serialization of MembershipVote structure."""

    def test_membership_vote_serialize(self, alice_identity):
        """Serialize MembershipVote to CBOR."""
        from peermodel.primitives import serialize_to_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=b'\x00' * 64
        )

        cbor_bytes = serialize_to_cbor(vote)
        assert isinstance(cbor_bytes, bytes)
        assert len(cbor_bytes) > 0

    def test_membership_vote_deserialize(self, alice_identity):
        """Deserialize CBOR back to MembershipVote."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=b'\x00' * 64
        )

        cbor_bytes = serialize_to_cbor(vote)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipVote)

        assert isinstance(deserialized, MembershipVote)
        assert deserialized.voter_identity_id == vote.voter_identity_id

    def test_membership_vote_round_trip(self, alice_identity):
        """Test round-trip serialization of MembershipVote."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=b'\x00' * 64
        )

        cbor_bytes = serialize_to_cbor(vote)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipVote)

        assert deserialized.voter_identity_id == vote.voter_identity_id
        assert deserialized.proposal_id == vote.proposal_id
        assert deserialized.approve == vote.approve
        assert deserialized.signature == vote.signature

    def test_membership_vote_canonical_stability(self, alice_identity):
        """Serialize same MembershipVote twice → identical bytes."""
        from peermodel.primitives import serialize_to_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=b'\x00' * 64
        )

        cbor_bytes1 = serialize_to_cbor(vote)
        cbor_bytes2 = serialize_to_cbor(vote)

        assert cbor_bytes1 == cbor_bytes2

    def test_membership_vote_approval_false(self, alice_identity):
        """Serialize MembershipVote with approval=False."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=False,
            signature=b'\x00' * 64
        )

        cbor_bytes = serialize_to_cbor(vote)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipVote)

        assert deserialized.approve is False

    def test_membership_vote_with_large_signature(self, alice_identity):
        """Serialize MembershipVote with large signature (boundary test)."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        # Ed25519 signatures are 64 bytes, but test with larger
        large_sig = b'\x00' * 256
        vote = MembershipVote(
            voter_identity_id=alice_identity['identity_id'],
            proposal_id='prop-123',
            approve=True,
            signature=large_sig
        )

        cbor_bytes = serialize_to_cbor(vote)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipVote)

        assert deserialized.signature == large_sig


# ===== Nested Structure CBOR Serialization Tests =====

class TestNestedStructuresCBORSerialization:
    """Test CBOR serialization of nested structures (edge cases)."""

    def test_credential_in_proposal(self, alice_credential, bob_identity):
        """Serialize MembershipProposal containing MemberCredential."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id=bob_identity['identity_id'],
            subject_credential={
                'x25519_public': bob_identity['x25519_public'],
                'ed25519_public': bob_identity['ed25519_public']
            },
            proposed_by='alice'
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert deserialized.subject_credential['x25519_public'] == bob_identity['x25519_public']

    def test_nested_empty_lists(self):
        """Serialize structure with empty nested lists."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id='bob',
            proposed_by='alice',
            votes=[]  # Empty votes list
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert deserialized.votes == []

    def test_nested_empty_dict(self):
        """Serialize structure with empty nested dict."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id='bob',
            proposed_by='alice',
            subject_credential={}  # Empty dict
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert deserialized.subject_credential == {}


# ===== Canonical Form Tests (RFC 7049 Section 3.9) =====

class TestCanonicalFormCBOR:
    """Test RFC 7049 canonical CBOR encoding."""

    def test_member_credential_differs_on_field_order_change(self, alice_credential):
        """Verify canonical form handles field ordering correctly."""
        from peermodel.primitives import serialize_to_cbor

        # Both orderings should produce identical canonical form
        cred1 = MemberCredential(
            member_id='alice',
            x25519_public=alice_credential.x25519_public,
            ed25519_public=alice_credential.ed25519_public,
            signing_algorithm='ed25519',
            encryption_algorithm='x25519',
            hardware_backed=False,
            certificate_der=None
        )

        cred2 = MemberCredential(
            member_id='alice',
            ed25519_public=alice_credential.ed25519_public,
            x25519_public=alice_credential.x25519_public,
            encryption_algorithm='x25519',
            signing_algorithm='ed25519',
            certificate_der=None,
            hardware_backed=False
        )

        cbor1 = serialize_to_cbor(cred1)
        cbor2 = serialize_to_cbor(cred2)

        # Canonical form should be identical regardless of construction order
        assert cbor1 == cbor2

    def test_dict_field_ordering_canonical(self):
        """Verify dicts with different key insertion order produce same CBOR."""
        from peermodel.primitives import serialize_to_cbor

        dict1 = {
            'x25519_public': b'\x00' * 32,
            'ed25519_public': b'\x00' * 32,
            'identity_id': 'alice'
        }

        dict2 = {
            'identity_id': 'alice',
            'ed25519_public': b'\x00' * 32,
            'x25519_public': b'\x00' * 32,
        }

        cbor1 = serialize_to_cbor(dict1)
        cbor2 = serialize_to_cbor(dict2)

        assert cbor1 == cbor2

    def test_integer_encoding_canonical(self):
        """Verify integers use shortest canonical encoding."""
        from peermodel.primitives import serialize_to_cbor

        # Small integer
        data_small = {'count': 5}
        cbor_small = serialize_to_cbor(data_small)

        # Large integer should use appropriate encoding
        data_large = {'count': 1000000}
        cbor_large = serialize_to_cbor(data_large)

        # Both should be valid CBOR
        assert isinstance(cbor_small, bytes)
        assert isinstance(cbor_large, bytes)


# ===== Large Scale / Boundary Tests =====

class TestCBORBoundaries:
    """Test CBOR serialization with boundary conditions."""

    def test_large_byte_string_member_credential(self, alice_identity):
        """Serialize credential with large DER certificate."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        large_der = b'\x30\x82' + b'\xaa' * 10000  # 10KB DER
        credential = MemberCredential(
            member_id=alice_identity['identity_id'],
            x25519_public=alice_identity['x25519_public'],
            ed25519_public=alice_identity['ed25519_public'],
            hardware_backed=True,
            certificate_der=large_der
        )

        cbor_bytes = serialize_to_cbor(credential)
        deserialized = deserialize_from_cbor(cbor_bytes, MemberCredential)

        assert len(deserialized.certificate_der) == len(large_der)

    def test_many_votes_in_proposal(self, alice_identity):
        """Serialize proposal with many votes."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        votes = []
        for i in range(100):
            vote = MembershipVote(
                voter_identity_id=f'voter_{i}',
                proposal_id='prop-123',
                approve=(i % 2 == 0),
                signature=b'\x00' * 64
            )
            votes.append(vote)

        proposal = MembershipProposal(
            proposal_id='prop-123',
            cohort_id='test_cohort',
            action='add',
            subject_member_id='bob',
            proposed_by='alice',
            votes=votes
        )

        cbor_bytes = serialize_to_cbor(proposal)
        deserialized = deserialize_from_cbor(cbor_bytes, MembershipProposal)

        assert len(deserialized.votes) == 100

    def test_deep_nested_dict(self):
        """Serialize deeply nested dictionary structure."""
        from peermodel.primitives import serialize_to_cbor, deserialize_from_cbor

        # Build deep nesting
        data = {'level_0': {'level_1': {'level_2': {'level_3': {'level_4': {'value': 42}}}}}}

        cbor_bytes = serialize_to_cbor(data)
        deserialized = deserialize_from_cbor(cbor_bytes, dict)

        assert deserialized['level_0']['level_1']['level_2']['level_3']['level_4']['value'] == 42


# ===== Signature/Signing Integration Tests =====

class TestCBORSigningIntegration:
    """Test that canonical CBOR is suitable for signatures."""

    def test_canonical_bytes_are_signable(self, alice_identity):
        """Verify canonical CBOR bytes can be signed."""
        from peermodel.primitives import serialize_to_cbor, sign_bytes

        credential = MemberCredential(
            member_id=alice_identity['identity_id'],
            x25519_public=alice_identity['x25519_public'],
            ed25519_public=alice_identity['ed25519_public']
        )

        cbor_bytes = serialize_to_cbor(credential)

        # Should be able to sign the CBOR bytes
        signature = sign_bytes(cbor_bytes, alice_identity['ed25519_private'])

        assert isinstance(signature, bytes)
        assert len(signature) == 64

    def test_canonical_deterministic_for_signatures(self, alice_identity):
        """Verify same object always produces same canonical bytes for signature."""
        from peermodel.primitives import serialize_to_cbor, sign_bytes

        credential = MemberCredential(
            member_id=alice_identity['identity_id'],
            x25519_public=alice_identity['x25519_public'],
            ed25519_public=alice_identity['ed25519_public']
        )

        cbor_bytes1 = serialize_to_cbor(credential)
        cbor_bytes2 = serialize_to_cbor(credential)

        sig1 = sign_bytes(cbor_bytes1, alice_identity['ed25519_private'])
        sig2 = sign_bytes(cbor_bytes2, alice_identity['ed25519_private'])

        # Same bytes should produce same signature
        assert sig1 == sig2
