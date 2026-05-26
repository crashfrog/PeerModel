"""RED tests for CBOR serialization of all CohortCrypto data structures.

These tests cover canonical CBOR serialization (RFC 7049 section 3.9) for:
- MemberCredential
- CohortIdentity
- KeyBundle
- CohortRecord
- MembershipProposal

Tests are currently FAILING - serialization module doesn't exist yet.
Implementation in issue #15.
"""

import pytest
from datetime import datetime

# Import data structures
from cohortcrypto import MemberCredential
from peermodel.membership import MembershipProposal, MembershipVote

# Import serialization functions (these will fail until implemented)
from cohortcrypto.serialization import (
    serialize_member_credential,
    deserialize_member_credential,
    serialize_cohort_identity,
    deserialize_cohort_identity,
    serialize_keybundle,
    deserialize_keybundle,
    serialize_record,
    deserialize_record,
    serialize_proposal,
    deserialize_proposal,
)

# Fixtures


@pytest.fixture
def member_credential():
    """Create a test MemberCredential."""
    return MemberCredential(
        member_id="alice",
        x25519_public=b"x" * 32,
        ed25519_public=b"e" * 32,
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None,
    )


@pytest.fixture
def hardware_member_credential():
    """Create a hardware-backed MemberCredential."""
    return MemberCredential(
        member_id="bob",
        x25519_public=b"y" * 32,
        ed25519_public=b"f" * 32,
        signing_algorithm="p256_ecdsa",
        encryption_algorithm="p256_ecdh",
        hardware_backed=True,
        certificate_der=b"cert" * 10,
    )


@pytest.fixture
def cohort_identity():
    """Create a test CohortIdentity (structure from spec)."""
    # This will fail until CohortIdentity is implemented
    from cohortcrypto.cohort import CohortIdentity

    return CohortIdentity(
        cohort_id="cohort-123",
        signing_public_key=b"sign" * 8,
        signing_algorithm="ed25519",
        encryption_public_key=b"encr" * 8,
        encryption_algorithm="x25519",
        ipns_key_name="cohort-123-key",
        created_at=datetime(2026, 5, 19, 12, 0, 0),
        keybundle_cid="QmTest123",
    )


@pytest.fixture
def key_bundle():
    """Create a test KeyBundle (structure from spec)."""
    from cohortcrypto.envelope import KeyBundle, KeyBundleEntry

    entry1 = KeyBundleEntry(
        member_id="alice",
        encrypted_key_material=b"encrypted" * 4,
        ephemeral_public_key_der=b"ephemeral" * 4,
        nonce=b"nonce123",
        tag=b"tag12345",
    )

    entry2 = KeyBundleEntry(
        member_id="bob",
        encrypted_key_material=b"encrypted2" * 4,
        ephemeral_public_key_der=b"ephemeral2" * 4,
        nonce=b"nonce456",
        tag=b"tag67890",
    )

    return KeyBundle(
        cohort_id="cohort-123",
        version=1,
        signing_alg="ed25519",
        encryption_alg="x25519",
        entries=[entry1, entry2],
    )


@pytest.fixture
def cohort_record():
    """Create a test CohortRecord (structure from spec)."""
    from cohortcrypto.signing import CohortRecord

    return CohortRecord(
        cohort_id="cohort-123",
        record_id="record-456",
        content_cid="QmContent123",
        key_bundle_cid="QmKeyBundle456",
        is_encrypted=True,
        metadata={"type": "data", "version": 1},
        signature=b"signature" * 8,
        signing_algorithm="ed25519",
        signed_at=datetime(2026, 5, 19, 12, 0, 0),
        schema_version="1.0.0",
    )


@pytest.fixture
def membership_proposal():
    """Create a test MembershipProposal with votes."""
    proposal = MembershipProposal(
        proposal_id="proposal-789",
        cohort_id="cohort-123",
        action="add",
        subject_member_id="carol",
        subject_credential={"member_id": "carol"},
        proposed_by="alice",
        proposed_at=datetime(2026, 5, 19, 12, 0, 0),
        votes=[],
    )

    # Add some votes
    vote1 = MembershipVote(
        voter_identity_id="alice",
        proposal_id="proposal-789",
        approve=True,
        signature=b"sig1" * 8,
        voted_at=datetime(2026, 5, 19, 12, 1, 0),
    )

    vote2 = MembershipVote(
        voter_identity_id="bob",
        proposal_id="proposal-789",
        approve=True,
        signature=b"sig2" * 8,
        voted_at=datetime(2026, 5, 19, 12, 2, 0),
    )

    proposal.votes = [vote1, vote2]
    return proposal


# MemberCredential Serialization Tests


def test_serialize_member_credential_returns_bytes(member_credential):
    """serialize_member_credential returns bytes."""
    result = serialize_member_credential(member_credential)
    assert isinstance(result, bytes)


def test_deserialize_member_credential_returns_object(member_credential):
    """deserialize_member_credential returns MemberCredential."""
    serialized = serialize_member_credential(member_credential)
    result = deserialize_member_credential(serialized)
    assert isinstance(result, MemberCredential)


def test_member_credential_round_trip_preserves_fields(member_credential):
    """Round-trip serialization preserves all MemberCredential fields."""
    serialized = serialize_member_credential(member_credential)
    result = deserialize_member_credential(serialized)

    assert result.member_id == member_credential.member_id
    assert result.x25519_public == member_credential.x25519_public
    assert result.ed25519_public == member_credential.ed25519_public
    assert result.signing_algorithm == member_credential.signing_algorithm
    assert result.encryption_algorithm == member_credential.encryption_algorithm
    assert result.hardware_backed == member_credential.hardware_backed
    assert result.certificate_der == member_credential.certificate_der


def test_member_credential_canonical_form_stable(member_credential):
    """Same MemberCredential serializes to identical bytes (canonical form)."""
    serialized1 = serialize_member_credential(member_credential)
    serialized2 = serialize_member_credential(member_credential)
    assert serialized1 == serialized2


def test_hardware_member_credential_round_trip(hardware_member_credential):
    """Hardware-backed MemberCredential round-trips correctly."""
    serialized = serialize_member_credential(hardware_member_credential)
    result = deserialize_member_credential(serialized)

    assert result.hardware_backed is True
    assert result.certificate_der == hardware_member_credential.certificate_der
    assert result.signing_algorithm == "p256_ecdsa"
    assert result.encryption_algorithm == "p256_ecdh"


# CohortIdentity Serialization Tests


def test_serialize_cohort_identity_returns_bytes(cohort_identity):
    """serialize_cohort_identity returns bytes."""
    result = serialize_cohort_identity(cohort_identity)
    assert isinstance(result, bytes)


def test_deserialize_cohort_identity_returns_object(cohort_identity):
    """deserialize_cohort_identity returns CohortIdentity."""
    from cohortcrypto.cohort import CohortIdentity

    serialized = serialize_cohort_identity(cohort_identity)
    result = deserialize_cohort_identity(serialized)
    assert isinstance(result, CohortIdentity)


def test_cohort_identity_round_trip_preserves_fields(cohort_identity):
    """Round-trip serialization preserves all CohortIdentity fields."""
    serialized = serialize_cohort_identity(cohort_identity)
    result = deserialize_cohort_identity(serialized)

    assert result.cohort_id == cohort_identity.cohort_id
    assert result.signing_public_key == cohort_identity.signing_public_key
    assert result.signing_algorithm == cohort_identity.signing_algorithm
    assert result.encryption_public_key == cohort_identity.encryption_public_key
    assert result.encryption_algorithm == cohort_identity.encryption_algorithm
    assert result.ipns_key_name == cohort_identity.ipns_key_name
    assert result.created_at == cohort_identity.created_at
    assert result.keybundle_cid == cohort_identity.keybundle_cid


def test_cohort_identity_canonical_form_stable(cohort_identity):
    """Same CohortIdentity serializes to identical bytes (canonical form)."""
    serialized1 = serialize_cohort_identity(cohort_identity)
    serialized2 = serialize_cohort_identity(cohort_identity)
    assert serialized1 == serialized2


# KeyBundle Serialization Tests


def test_serialize_keybundle_returns_bytes(key_bundle):
    """serialize_keybundle returns bytes."""
    result = serialize_keybundle(key_bundle)
    assert isinstance(result, bytes)


def test_deserialize_keybundle_returns_object(key_bundle):
    """deserialize_keybundle returns KeyBundle."""
    from cohortcrypto.envelope import KeyBundle

    serialized = serialize_keybundle(key_bundle)
    result = deserialize_keybundle(serialized)
    assert isinstance(result, KeyBundle)


def test_keybundle_round_trip_preserves_fields(key_bundle):
    """Round-trip serialization preserves all KeyBundle fields."""
    serialized = serialize_keybundle(key_bundle)
    result = deserialize_keybundle(serialized)

    assert result.cohort_id == key_bundle.cohort_id
    assert result.version == key_bundle.version
    assert result.signing_alg == key_bundle.signing_alg
    assert result.encryption_alg == key_bundle.encryption_alg
    assert len(result.entries) == len(key_bundle.entries)

    # Check first entry
    assert result.entries[0].member_id == key_bundle.entries[0].member_id
    assert (
        result.entries[0].encrypted_key_material
        == key_bundle.entries[0].encrypted_key_material
    )
    assert (
        result.entries[0].ephemeral_public_key_der
        == key_bundle.entries[0].ephemeral_public_key_der
    )
    assert result.entries[0].nonce == key_bundle.entries[0].nonce
    assert result.entries[0].tag == key_bundle.entries[0].tag


def test_keybundle_canonical_form_stable(key_bundle):
    """Same KeyBundle serializes to identical bytes (canonical form)."""
    serialized1 = serialize_keybundle(key_bundle)
    serialized2 = serialize_keybundle(key_bundle)
    assert serialized1 == serialized2


# CohortRecord Serialization Tests


def test_serialize_record_returns_bytes(cohort_record):
    """serialize_record returns bytes."""
    result = serialize_record(cohort_record)
    assert isinstance(result, bytes)


def test_deserialize_record_returns_object(cohort_record):
    """deserialize_record returns CohortRecord."""
    from cohortcrypto.signing import CohortRecord

    serialized = serialize_record(cohort_record)
    result = deserialize_record(serialized)
    assert isinstance(result, CohortRecord)


def test_cohort_record_round_trip_preserves_fields(cohort_record):
    """Round-trip serialization preserves all CohortRecord fields."""
    serialized = serialize_record(cohort_record)
    result = deserialize_record(serialized)

    assert result.cohort_id == cohort_record.cohort_id
    assert result.record_id == cohort_record.record_id
    assert result.content_cid == cohort_record.content_cid
    assert result.key_bundle_cid == cohort_record.key_bundle_cid
    assert result.is_encrypted == cohort_record.is_encrypted
    assert result.metadata == cohort_record.metadata
    assert result.signature == cohort_record.signature
    assert result.signing_algorithm == cohort_record.signing_algorithm
    assert result.signed_at == cohort_record.signed_at
    assert result.schema_version == cohort_record.schema_version


def test_cohort_record_canonical_form_stable(cohort_record):
    """Same CohortRecord serializes to identical bytes (canonical form)."""
    serialized1 = serialize_record(cohort_record)
    serialized2 = serialize_record(cohort_record)
    assert serialized1 == serialized2


def test_cohort_record_preserves_signature(cohort_record):
    """Round-trip preserves signature bytes exactly."""
    serialized = serialize_record(cohort_record)
    result = deserialize_record(serialized)

    assert result.signature == cohort_record.signature
    assert len(result.signature) == len(cohort_record.signature)


# MembershipProposal Serialization Tests


def test_serialize_proposal_returns_bytes(membership_proposal):
    """serialize_proposal returns bytes."""
    result = serialize_proposal(membership_proposal)
    assert isinstance(result, bytes)


def test_deserialize_proposal_returns_object(membership_proposal):
    """deserialize_proposal returns MembershipProposal."""
    serialized = serialize_proposal(membership_proposal)
    result = deserialize_proposal(serialized)
    assert isinstance(result, MembershipProposal)


def test_membership_proposal_round_trip_preserves_fields(membership_proposal):
    """Round-trip serialization preserves all MembershipProposal fields."""
    serialized = serialize_proposal(membership_proposal)
    result = deserialize_proposal(serialized)

    assert result.proposal_id == membership_proposal.proposal_id
    assert result.cohort_id == membership_proposal.cohort_id
    assert result.action == membership_proposal.action
    assert result.subject_member_id == membership_proposal.subject_member_id
    assert result.subject_credential == membership_proposal.subject_credential
    assert result.proposed_by == membership_proposal.proposed_by
    assert result.proposed_at == membership_proposal.proposed_at
    assert len(result.votes) == len(membership_proposal.votes)


def test_membership_proposal_preserves_votes(membership_proposal):
    """Round-trip preserves all vote details."""
    serialized = serialize_proposal(membership_proposal)
    result = deserialize_proposal(serialized)

    assert len(result.votes) == 2

    # Check first vote
    vote1 = result.votes[0]
    assert vote1.voter_identity_id == "alice"
    assert vote1.proposal_id == "proposal-789"
    assert vote1.approve is True
    assert vote1.signature == b"sig1" * 8

    # Check second vote
    vote2 = result.votes[1]
    assert vote2.voter_identity_id == "bob"
    assert vote2.approve is True
    assert vote2.signature == b"sig2" * 8


def test_membership_proposal_canonical_form_stable(membership_proposal):
    """Same MembershipProposal serializes to identical bytes (canonical form)."""
    serialized1 = serialize_proposal(membership_proposal)
    serialized2 = serialize_proposal(membership_proposal)
    assert serialized1 == serialized2


# Canonical Form Stability Tests


def test_canonical_form_field_order_independence():
    """Canonical form is stable regardless of field construction order.

    This tests that CBOR canonical encoding (RFC 7049 section 3.9) produces
    identical output regardless of how the object was constructed.
    """
    # Create two MemberCredentials with fields set in different orders
    cred1 = MemberCredential(
        member_id="test",
        x25519_public=b"x" * 32,
        ed25519_public=b"e" * 32,
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None,
    )

    # Construct with same values but via dict (simulating different construction path)
    cred2 = MemberCredential(
        **{
            "certificate_der": None,
            "hardware_backed": False,
            "encryption_algorithm": "x25519",
            "signing_algorithm": "ed25519",
            "ed25519_public": b"e" * 32,
            "x25519_public": b"x" * 32,
            "member_id": "test",
        }
    )

    serialized1 = serialize_member_credential(cred1)
    serialized2 = serialize_member_credential(cred2)

    assert (
        serialized1 == serialized2
    ), "Canonical form must be independent of field order"


def test_canonical_form_multiple_serializations():
    """Multiple serializations of the same object produce identical bytes."""
    cred = MemberCredential(
        member_id="stable",
        x25519_public=b"x" * 32,
        ed25519_public=b"e" * 32,
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None,
    )

    # Serialize 5 times
    serializations = [serialize_member_credential(cred) for _ in range(5)]

    # All should be identical
    first = serializations[0]
    for s in serializations[1:]:
        assert (
            s == first
        ), "Canonical form must be stable across multiple serializations"


def test_canonical_form_deserialize_serialize_stable():
    """Deserialize-then-serialize produces identical bytes (idempotent)."""
    cred = MemberCredential(
        member_id="idempotent",
        x25519_public=b"x" * 32,
        ed25519_public=b"e" * 32,
        signing_algorithm="ed25519",
        encryption_algorithm="x25519",
        hardware_backed=False,
        certificate_der=None,
    )

    serialized1 = serialize_member_credential(cred)
    deserialized = deserialize_member_credential(serialized1)
    serialized2 = serialize_member_credential(deserialized)

    assert serialized1 == serialized2, "Deserialize-serialize must be idempotent"
