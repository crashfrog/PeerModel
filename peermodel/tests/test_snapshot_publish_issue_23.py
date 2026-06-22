#!/usr/bin/env python

"""Acceptance tests for Snapshot CBOR serialization & IPFS publishing (Issue #23).

API under test (to be added to peermodel/snapshots.py):
- serialize_snapshot_to_cbor(snapshot) -> bytes
  Full CBOR encoding of a Snapshot including the signature field.
  Distinct from canonical_snapshot_bytes() which excludes signature for signing.
- deserialize_snapshot_from_cbor(cbor_bytes) -> Snapshot
  Round-trip partner.
- publish_snapshot(snapshot, ipfs_client) -> str
  Serializes to CBOR, calls ipfs_client.add(bytes), returns CID string.
- update_ipns_pointer(cohort_id, record_type, cid, ipfs_client) -> str
  Calls ipfs_client.name.publish('/ipfs/{cid}', key='peermodel:{cohort_id}:{record_type}:snapshot').
  Returns the IPNS key name used.
"""

import hashlib
import pytest
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, call

import cbor2

import peermodel
from peermodel.peermodel import DocumentObj
from peermodel.index import IndexDB
from peermodel.primitives import generate_software_keypair
from peermodel.snapshots import Snapshot, SnapshotManager, canonical_snapshot_bytes


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def peer():
    return peermodel.App("test_snapshot_publish")


@pytest.fixture
def cohort_keypair():
    kp = generate_software_keypair("ed25519")
    return {"private": kp[0], "public": kp[1], "algorithm": "ed25519"}


@pytest.fixture
def sample_snapshot(cohort_keypair):
    """Build a signed Snapshot directly without hitting the database."""
    from peermodel.primitives import sign_bytes

    snap = Snapshot(
        cohort_id="cohort-abc-123",
        snapshot_id="snap-uuid-001",
        record_type="Widget",
        log_head_cid="bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
        sequence_number=7,
        records=[
            {"_record_id": "r1", "_sequence": 1, "_tombstoned": 0, "name": "Alpha", "value": 10},
            {"_record_id": "r2", "_sequence": 2, "_tombstoned": 0, "name": "Beta", "value": 20},
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
        signature=b"",
        signing_algorithm="ed25519",
    )
    canonical = canonical_snapshot_bytes(snap)
    snap.signature = sign_bytes(canonical, cohort_keypair["private"], algorithm="ed25519")
    return snap


@pytest.fixture
def empty_snapshot(cohort_keypair):
    """A snapshot with zero records."""
    from peermodel.primitives import sign_bytes

    snap = Snapshot(
        cohort_id="cohort-empty",
        snapshot_id="snap-empty",
        record_type="Widget",
        log_head_cid="cid-empty",
        sequence_number=0,
        records=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        signature=b"",
        signing_algorithm="ed25519",
    )
    canonical = canonical_snapshot_bytes(snap)
    snap.signature = sign_bytes(canonical, cohort_keypair["private"], algorithm="ed25519")
    return snap


@pytest.fixture
def another_snapshot(cohort_keypair):
    """A snapshot with different content from sample_snapshot."""
    from peermodel.primitives import sign_bytes

    snap = Snapshot(
        cohort_id="cohort-xyz-999",
        snapshot_id="snap-uuid-002",
        record_type="Gadget",
        log_head_cid="cid-different",
        sequence_number=42,
        records=[
            {"_record_id": "r9", "_sequence": 9, "_tombstoned": 0, "name": "Gamma", "value": 99},
        ],
        created_at=datetime.now(timezone.utc).isoformat(),
        signature=b"",
        signing_algorithm="ed25519",
    )
    canonical = canonical_snapshot_bytes(snap)
    snap.signature = sign_bytes(canonical, cohort_keypair["private"], algorithm="ed25519")
    return snap


def make_deterministic_ipfs_client():
    """Mock IPFS client whose add() is content-addressed (same bytes → same CID)."""
    client = MagicMock()
    _store = {}

    def _add(data):
        content_hash = hashlib.sha256(data).hexdigest()
        cid = f"Qm{content_hash[:44]}"
        _store[cid] = data
        return {"Hash": cid}

    client.add.side_effect = _add
    client.name.publish.return_value = {"Name": "peermodel:x:y:snapshot", "Value": "/ipfs/Qm..."}
    client._store = _store
    return client


# ============================================================================
# CBOR SERIALIZATION TESTS
# ============================================================================


@pytest.mark.issue_23
class TestSerializeSnapshotToCBOR:
    """serialize_snapshot_to_cbor() produces valid, deterministic CBOR including signature."""

    def test_returns_bytes(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        result = serialize_snapshot_to_cbor(sample_snapshot)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_includes_signature_field(self, sample_snapshot):
        """serialize_snapshot_to_cbor includes signature (unlike canonical_snapshot_bytes)."""
        from peermodel.snapshots import serialize_snapshot_to_cbor

        cbor_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        decoded = cbor2.loads(cbor_bytes)

        assert "signature" in decoded
        assert decoded["signature"] == sample_snapshot.signature

    def test_includes_all_snapshot_fields(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        cbor_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        decoded = cbor2.loads(cbor_bytes)

        required_fields = {
            "cohort_id", "snapshot_id", "record_type", "log_head_cid",
            "sequence_number", "records", "created_at", "signature", "signing_algorithm",
        }
        missing = required_fields - set(decoded.keys())
        assert not missing, f"Missing fields in CBOR: {missing}"

    def test_cohort_id_value_preserved(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        decoded = cbor2.loads(serialize_snapshot_to_cbor(sample_snapshot))
        assert decoded["cohort_id"] == "cohort-abc-123"

    def test_sequence_number_preserved(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        decoded = cbor2.loads(serialize_snapshot_to_cbor(sample_snapshot))
        assert decoded["sequence_number"] == 7

    def test_records_list_preserved(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        decoded = cbor2.loads(serialize_snapshot_to_cbor(sample_snapshot))
        assert isinstance(decoded["records"], list)
        assert len(decoded["records"]) == 2

    def test_canonical_stability(self, sample_snapshot):
        """Same Snapshot object → identical bytes on repeated calls."""
        from peermodel.snapshots import serialize_snapshot_to_cbor

        bytes1 = serialize_snapshot_to_cbor(sample_snapshot)
        bytes2 = serialize_snapshot_to_cbor(sample_snapshot)
        assert bytes1 == bytes2

    def test_different_snapshots_produce_different_bytes(self, sample_snapshot, another_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        bytes1 = serialize_snapshot_to_cbor(sample_snapshot)
        bytes2 = serialize_snapshot_to_cbor(another_snapshot)
        assert bytes1 != bytes2

    def test_empty_records_list_serializes(self, empty_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor

        cbor_bytes = serialize_snapshot_to_cbor(empty_snapshot)
        decoded = cbor2.loads(cbor_bytes)
        assert decoded["records"] == []

    def test_differs_from_canonical_snapshot_bytes(self, sample_snapshot):
        """serialize_snapshot_to_cbor includes signature; canonical_snapshot_bytes does not."""
        from peermodel.snapshots import serialize_snapshot_to_cbor

        full_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        signing_bytes = canonical_snapshot_bytes(sample_snapshot)
        # They must differ because full serialization includes the signature field
        assert full_bytes != signing_bytes


# ============================================================================
# CBOR DESERIALIZATION TESTS
# ============================================================================


@pytest.mark.issue_23
class TestDeserializeSnapshotFromCBOR:
    """deserialize_snapshot_from_cbor() reconstructs a Snapshot from bytes."""

    def test_returns_snapshot_instance(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        cbor_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        result = deserialize_snapshot_from_cbor(cbor_bytes)
        assert isinstance(result, Snapshot)

    def test_restores_cohort_id(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.cohort_id == sample_snapshot.cohort_id

    def test_restores_snapshot_id(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.snapshot_id == sample_snapshot.snapshot_id

    def test_restores_record_type(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.record_type == "Widget"

    def test_restores_log_head_cid(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.log_head_cid == sample_snapshot.log_head_cid

    def test_restores_sequence_number(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.sequence_number == 7

    def test_restores_signature_exact_bytes(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.signature == sample_snapshot.signature

    def test_restores_signing_algorithm(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.signing_algorithm == "ed25519"

    def test_restores_created_at(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert result.created_at == sample_snapshot.created_at


# ============================================================================
# ROUND-TRIP TESTS
# ============================================================================


@pytest.mark.issue_23
class TestSnapshotRoundTrip:
    """serialize → deserialize preserves every field exactly."""

    def test_round_trip_all_fields_equal(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))

        assert result.cohort_id == sample_snapshot.cohort_id
        assert result.snapshot_id == sample_snapshot.snapshot_id
        assert result.record_type == sample_snapshot.record_type
        assert result.log_head_cid == sample_snapshot.log_head_cid
        assert result.sequence_number == sample_snapshot.sequence_number
        assert result.created_at == sample_snapshot.created_at
        assert result.signing_algorithm == sample_snapshot.signing_algorithm
        assert result.signature == sample_snapshot.signature

    def test_round_trip_records_count(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        assert len(result.records) == 2

    def test_round_trip_record_ids_preserved(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        record_ids = {r["_record_id"] for r in result.records}
        assert record_ids == {"r1", "r2"}

    def test_round_trip_record_values_preserved(self, sample_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        names = {r["name"] for r in result.records}
        assert names == {"Alpha", "Beta"}

    def test_round_trip_empty_records(self, empty_snapshot):
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        result = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(empty_snapshot))
        assert result.records == []

    def test_round_trip_re_serializes_to_same_bytes(self, sample_snapshot):
        """serialize → deserialize → serialize yields identical bytes (CID stable)."""
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor

        original_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        restored = deserialize_snapshot_from_cbor(original_bytes)
        restored_bytes = serialize_snapshot_to_cbor(restored)
        assert restored_bytes == original_bytes

    def test_round_trip_signature_verifiable_after_restore(self, sample_snapshot, cohort_keypair):
        """Restored snapshot signature still verifies against the public key."""
        from peermodel.snapshots import serialize_snapshot_to_cbor, deserialize_snapshot_from_cbor
        from cryptography.hazmat.primitives import serialization

        restored = deserialize_snapshot_from_cbor(serialize_snapshot_to_cbor(sample_snapshot))
        signing_bytes = canonical_snapshot_bytes(restored)
        public_key = serialization.load_der_public_key(cohort_keypair["public"])
        # Should not raise
        public_key.verify(restored.signature, signing_bytes)


# ============================================================================
# IPFS PUBLISH TESTS
# ============================================================================


@pytest.mark.issue_23
class TestPublishSnapshot:
    """publish_snapshot(snapshot, ipfs_client) serializes to CBOR and adds to IPFS."""

    def test_returns_cid_string(self, sample_snapshot):
        from peermodel.snapshots import publish_snapshot, serialize_snapshot_to_cbor

        mock_ipfs = MagicMock()
        mock_ipfs.add.return_value = {"Hash": "QmTestCID0000000000000000000000000000000000000"}
        cid = publish_snapshot(sample_snapshot, mock_ipfs)
        assert isinstance(cid, str)
        assert cid == "QmTestCID0000000000000000000000000000000000000"

    def test_calls_ipfs_add(self, sample_snapshot):
        from peermodel.snapshots import publish_snapshot

        mock_ipfs = MagicMock()
        mock_ipfs.add.return_value = {"Hash": "QmSomeCID"}
        publish_snapshot(sample_snapshot, mock_ipfs)
        mock_ipfs.add.assert_called_once()

    def test_passes_cbor_bytes_to_ipfs_add(self, sample_snapshot):
        """The bytes passed to ipfs_client.add must match serialize_snapshot_to_cbor output."""
        from peermodel.snapshots import publish_snapshot, serialize_snapshot_to_cbor

        mock_ipfs = MagicMock()
        mock_ipfs.add.return_value = {"Hash": "QmSomeCID"}
        publish_snapshot(sample_snapshot, mock_ipfs)

        expected_bytes = serialize_snapshot_to_cbor(sample_snapshot)
        actual_bytes = mock_ipfs.add.call_args[0][0]
        assert actual_bytes == expected_bytes

    def test_cid_stable_for_same_content(self, sample_snapshot):
        """Same snapshot content → same bytes → same CID (content-addressed invariant)."""
        from peermodel.snapshots import publish_snapshot, serialize_snapshot_to_cbor

        ipfs = make_deterministic_ipfs_client()
        cid1 = publish_snapshot(sample_snapshot, ipfs)
        cid2 = publish_snapshot(sample_snapshot, ipfs)
        assert cid1 == cid2

    def test_different_content_yields_different_cids(self, sample_snapshot, another_snapshot):
        from peermodel.snapshots import publish_snapshot

        ipfs = make_deterministic_ipfs_client()
        cid1 = publish_snapshot(sample_snapshot, ipfs)
        cid2 = publish_snapshot(another_snapshot, ipfs)
        assert cid1 != cid2

    def test_cid_from_deterministic_content(self, sample_snapshot):
        """CID published is deterministically derived from the CBOR bytes."""
        from peermodel.snapshots import publish_snapshot, serialize_snapshot_to_cbor

        ipfs = make_deterministic_ipfs_client()
        returned_cid = publish_snapshot(sample_snapshot, ipfs)

        expected_cbor = serialize_snapshot_to_cbor(sample_snapshot)
        content_hash = hashlib.sha256(expected_cbor).hexdigest()
        expected_cid = f"Qm{content_hash[:44]}"
        assert returned_cid == expected_cid

    def test_publish_empty_snapshot(self, empty_snapshot):
        from peermodel.snapshots import publish_snapshot

        mock_ipfs = MagicMock()
        mock_ipfs.add.return_value = {"Hash": "QmEmptyCID"}
        cid = publish_snapshot(empty_snapshot, mock_ipfs)
        assert cid == "QmEmptyCID"


# ============================================================================
# IPNS POINTER UPDATE TESTS
# ============================================================================


@pytest.mark.issue_23
class TestUpdateIPNSPointer:
    """update_ipns_pointer() publishes snapshot CID to IPNS under the canonical key name."""

    def test_calls_ipfs_name_publish(self):
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {"Name": "peermodel:c:T:snapshot"}
        update_ipns_pointer("cohort-1", "TestRecord", "QmSomeCID", mock_ipfs)
        mock_ipfs.name.publish.assert_called_once()

    def test_key_name_format(self):
        """Key must be 'peermodel:{cohort_id}:{record_type}:snapshot'."""
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {"Name": "peermodel:cohort-1:Widget:snapshot"}
        update_ipns_pointer("cohort-1", "Widget", "QmSomeCID", mock_ipfs)

        _, kwargs = mock_ipfs.name.publish.call_args
        assert kwargs.get("key") == "peermodel:cohort-1:Widget:snapshot"

    def test_cid_passed_as_value(self):
        """The CID must appear in the value argument to name.publish."""
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        update_ipns_pointer("cohort-1", "Widget", "QmActualCID", mock_ipfs)

        args, kwargs = mock_ipfs.name.publish.call_args
        value = args[0] if args else kwargs.get("value", "")
        assert "QmActualCID" in value

    def test_key_contains_cohort_id(self):
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        update_ipns_pointer("my-special-cohort", "Widget", "QmCID", mock_ipfs)

        _, kwargs = mock_ipfs.name.publish.call_args
        assert "my-special-cohort" in kwargs.get("key", "")

    def test_key_contains_record_type(self):
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        update_ipns_pointer("cohort-1", "VerySpecificModel", "QmCID", mock_ipfs)

        _, kwargs = mock_ipfs.name.publish.call_args
        assert "VerySpecificModel" in kwargs.get("key", "")

    def test_different_cohorts_produce_different_keys(self):
        from peermodel.snapshots import update_ipns_pointer

        calls = []

        def capture_publish(*args, **kwargs):
            calls.append(kwargs.get("key", ""))
            return {}

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.side_effect = capture_publish

        update_ipns_pointer("cohort-alpha", "Widget", "QmCID1", mock_ipfs)
        update_ipns_pointer("cohort-beta", "Widget", "QmCID2", mock_ipfs)

        assert calls[0] != calls[1]
        assert "cohort-alpha" in calls[0]
        assert "cohort-beta" in calls[1]

    def test_different_record_types_produce_different_keys(self):
        from peermodel.snapshots import update_ipns_pointer

        calls = []

        def capture_publish(*args, **kwargs):
            calls.append(kwargs.get("key", ""))
            return {}

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.side_effect = capture_publish

        update_ipns_pointer("cohort-1", "ModelA", "QmCID1", mock_ipfs)
        update_ipns_pointer("cohort-1", "ModelB", "QmCID2", mock_ipfs)

        assert calls[0] != calls[1]
        assert "ModelA" in calls[0]
        assert "ModelB" in calls[1]

    def test_returns_ipns_key_name(self):
        """Return value is the IPNS key name that was updated."""
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        result = update_ipns_pointer("cohort-1", "Widget", "QmSomeCID", mock_ipfs)
        assert result == "peermodel:cohort-1:Widget:snapshot"

    def test_key_has_peermodel_prefix(self):
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        result = update_ipns_pointer("c", "T", "QmCID", mock_ipfs)
        assert result.startswith("peermodel:")

    def test_key_ends_with_snapshot_suffix(self):
        from peermodel.snapshots import update_ipns_pointer

        mock_ipfs = MagicMock()
        mock_ipfs.name.publish.return_value = {}
        result = update_ipns_pointer("c", "T", "QmCID", mock_ipfs)
        assert result.endswith(":snapshot")
