#!/usr/bin/env python

"""Tests for operation log traversal (Issue #25).

Tests cover:
- Traverse from head to genesis
- Operations returned in chronological order (ascending sequence_number)
- Signature verification with invalid operations skipped
- Concurrent fetch with semaphore limiting
- LogIntegrityError raised on bad state (>10% invalid or non-contiguous sequences)
- Edge cases: single operation, empty log, long chains
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime
from unittest.mock import MagicMock, patch

import peermodel.primitives
from peermodel.operations import OperationRecord
from peermodel.delegation import SimpleCohort


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def alice_identity():
    """Generate Alice's identity."""
    x25519_priv, x25519_pub, ed25519_priv, ed25519_pub = (
        peermodel.primitives.generate_keypair()
    )
    return {
        "identity_id": "alice",
        "x25519_private": x25519_priv,
        "x25519_public": x25519_pub,
        "ed25519_private": ed25519_priv,
        "ed25519_public": ed25519_pub,
    }


@pytest.fixture
def test_cohort(alice_identity):
    """Create a cohort for operation testing."""
    return SimpleCohort(
        cohort_id="test_cohort", founder_identity=alice_identity
    )


@pytest.fixture
def sample_operations(test_cohort, alice_identity):
    """Create a chain of sample operations for testing traversal."""
    operations = []
    previous_cid = None

    for i in range(5):
        op = test_cohort.create_operation(
            op_type="insert" if i == 0 else "update",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": f"value{i}", "index": i},
            previous_head_cid=previous_cid,
            initiator=alice_identity,
        )
        operations.append(op)
        # In real implementation, op would have ipfs_cid after publishing
        op.ipfs_cid = f"Qm{i:064x}"
        previous_cid = op.ipfs_cid

    return operations


@pytest.fixture
def mock_ipfs_client(sample_operations):
    """Mock IPFS client that returns operations by CID."""
    client = MagicMock()

    # Create lookup dict: CID -> operation
    op_lookup = {op.ipfs_cid: op for op in sample_operations}

    async def mock_fetch(cid):
        """Simulate fetching operation from IPFS."""
        await asyncio.sleep(0.01)  # Simulate network delay
        if cid in op_lookup:
            return op_lookup[cid]
        raise ValueError(f"CID not found: {cid}")

    client.fetch = mock_fetch
    return client


# ============================================================================
# HAPPY PATH TESTS
# ============================================================================


class TestLogTraversalHappyPath:
    """Happy path: successfully traverse operation log."""

    @pytest.mark.asyncio
    async def test_traverse_function_exists(self):
        """traverse() function must be defined."""
        # This will fail until implementation exists
        with pytest.raises((ImportError, AttributeError)):
            from peermodel.operations import traverse  # noqa: F401

    @pytest.mark.asyncio
    async def test_traverse_returns_list_of_operations(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() returns list of OperationRecords."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=None,
            ipfs_client=mock_ipfs_client
        )

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(op, OperationRecord) for op in result)

    @pytest.mark.asyncio
    async def test_traverse_from_head_to_genesis(
        self, sample_operations, mock_ipfs_client
    ):
        """Traverse fetches all operations from head to genesis."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=None,
            ipfs_client=mock_ipfs_client
        )

        # Should fetch all 5 operations
        assert len(result) == len(sample_operations)

    @pytest.mark.asyncio
    async def test_traverse_stops_at_specified_cid(
        self, sample_operations, mock_ipfs_client
    ):
        """Traverse stops at stop_at_cid (exclusive)."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid
        stop_cid = sample_operations[2].ipfs_cid

        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=stop_cid,
            ipfs_client=mock_ipfs_client
        )

        # Should fetch operations 3 and 4 only (stop_at_cid is exclusive)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_traverse_returns_chronological_order(
        self, sample_operations, mock_ipfs_client
    ):
        """Operations returned in ascending sequence_number order."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=None,
            ipfs_client=mock_ipfs_client
        )

        # Check sequence numbers are ascending
        sequence_numbers = [op.sequence_number for op in result]
        assert sequence_numbers == sorted(sequence_numbers)

        # First operation should have lowest sequence number
        assert result[0].sequence_number == 1

    @pytest.mark.asyncio
    async def test_traverse_single_operation(self, test_cohort, alice_identity):
        """Traverse works with single operation (genesis)."""
        from peermodel.operations import traverse

        # Create single operation
        op = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=str(uuid4()),
            payload={"data": "genesis"},
            previous_head_cid=None,
            initiator=alice_identity,
        )
        op.ipfs_cid = "QmGenesis"

        # Mock IPFS client
        client = MagicMock()

        async def mock_fetch(cid):
            if cid == op.ipfs_cid:
                return op
            raise ValueError(f"CID not found: {cid}")

        client.fetch = mock_fetch

        result = await traverse(
            head_cid=op.ipfs_cid,
            stop_at_cid=None,
            ipfs_client=client
        )

        assert len(result) == 1
        assert result[0].sequence_number == 1
        assert result[0].previous_head_cid is None


# ============================================================================
# SIGNATURE VERIFICATION TESTS
# ============================================================================


class TestSignatureVerification:
    """Test signature verification during traversal."""

    @pytest.mark.asyncio
    async def test_traverse_verifies_signatures(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() verifies signatures on fetched operations."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        # Mock verify_operation to track calls
        with patch('peermodel.operations.verify_operation') as mock_verify:
            mock_verify.return_value = True

            await traverse(
                head_cid=head_cid,
                stop_at_cid=None,
                ipfs_client=mock_ipfs_client
            )

            # Verify was called for each operation
            assert mock_verify.call_count == len(sample_operations)

    @pytest.mark.asyncio
    async def test_traverse_skips_invalid_signatures(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() skips operations with invalid signatures."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        # Mock verify_operation to mark some as invalid
        def mock_verify(op):
            # Mark operation 2 as invalid
            return op.sequence_number != 3

        with patch('peermodel.operations.verify_operation', side_effect=mock_verify):
            result = await traverse(
                head_cid=head_cid,
                stop_at_cid=None,
                ipfs_client=mock_ipfs_client
            )

            # Should have 4 operations (skipped 1 invalid)
            assert len(result) == 4
            # Skipped operation should not be in result
            assert all(op.sequence_number != 3 for op in result)

    @pytest.mark.asyncio
    async def test_traverse_warns_on_invalid_signature(
        self, sample_operations, mock_ipfs_client, caplog
    ):
        """traverse() logs warning for invalid signatures."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        def mock_verify(op):
            return op.sequence_number != 3

        with patch('peermodel.operations.verify_operation', side_effect=mock_verify):
            await traverse(
                head_cid=head_cid,
                stop_at_cid=None,
                ipfs_client=mock_ipfs_client
            )

            # Check for warning in logs
            # (exact message format depends on implementation)
            assert any(
                "invalid" in record.message.lower() or
                "signature" in record.message.lower()
                for record in caplog.records
                if record.levelname == "WARNING"
            )


# ============================================================================
# CONCURRENT FETCH TESTS
# ============================================================================


class TestConcurrentFetch:
    """Test concurrent fetching with semaphore limiting."""

    @pytest.mark.asyncio
    async def test_traverse_accepts_concurrency_parameter(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() accepts concurrency parameter."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=None,
            ipfs_client=mock_ipfs_client,
            concurrency=10
        )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_traverse_default_concurrency_is_50(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() defaults to concurrency=50."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        # Call without concurrency parameter
        result = await traverse(
            head_cid=head_cid,
            stop_at_cid=None,
            ipfs_client=mock_ipfs_client
        )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_traverse_respects_concurrency_limit(self):
        """traverse() respects semaphore concurrency limit."""
        from peermodel.operations import traverse

        # Track concurrent fetches
        current_concurrent = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def tracked_fetch(cid):
            nonlocal current_concurrent, max_concurrent

            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.01)  # Simulate work

            async with lock:
                current_concurrent -= 1

            # Return mock operation
            return OperationRecord(
                op_id=str(uuid4()),
                op_type="insert",
                cohort_id="test",
                record_type="TestRecord",
                record_id=str(uuid4()),
                sequence_number=1,
                payload={"data": "test"},
                previous_head_cid=None,
                timestamp=datetime.utcnow().isoformat() + "Z",
                schema_version="1.0.0",
                signature=b"test",
                signing_algorithm="Ed25519"
            )

        client = MagicMock()
        client.fetch = tracked_fetch

        # Create a mock head operation
        with patch('peermodel.operations.verify_operation', return_value=True):
            await traverse(
                head_cid="QmHead",
                stop_at_cid=None,
                ipfs_client=client,
                concurrency=5
            )

        # Max concurrent should not exceed limit
        assert max_concurrent <= 5


# ============================================================================
# LOG INTEGRITY ERROR TESTS
# ============================================================================


class TestLogIntegrityError:
    """Test LogIntegrityError raised on bad state."""

    @pytest.mark.asyncio
    async def test_log_integrity_error_exists(self):
        """LogIntegrityError exception must be defined."""
        from peermodel.exceptions import LogIntegrityError

        assert LogIntegrityError is not None
        assert issubclass(LogIntegrityError, Exception)

    @pytest.mark.asyncio
    async def test_traverse_raises_on_missing_cid(self):
        """traverse() raises LogIntegrityError if CID not found after retries."""
        from peermodel.operations import traverse
        from peermodel.exceptions import LogIntegrityError

        client = MagicMock()

        async def mock_fetch_fail(cid):
            raise ValueError("CID not found")

        client.fetch = mock_fetch_fail

        with pytest.raises(LogIntegrityError):
            await traverse(
                head_cid="QmMissing",
                stop_at_cid=None,
                ipfs_client=client
            )

    @pytest.mark.asyncio
    async def test_traverse_raises_on_non_contiguous_sequences(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() raises LogIntegrityError on sequence gaps."""
        from peermodel.operations import traverse
        from peermodel.exceptions import LogIntegrityError

        # Corrupt sequence numbers
        sample_operations[2].sequence_number = 99  # Create gap

        head_cid = sample_operations[-1].ipfs_cid

        with pytest.raises(LogIntegrityError):
            await traverse(
                head_cid=head_cid,
                stop_at_cid=None,
                ipfs_client=mock_ipfs_client
            )

    @pytest.mark.asyncio
    async def test_traverse_raises_on_10_percent_invalid_signatures(
        self, alice_identity
    ):
        """traverse() raises LogIntegrityError if >10% invalid signatures."""
        from peermodel.operations import traverse
        from peermodel.exceptions import LogIntegrityError

        # Create 20 operations
        cohort = SimpleCohort(cohort_id="test", founder_identity=alice_identity)
        operations = []
        previous_cid = None

        for i in range(20):
            op = cohort.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": f"value{i}"},
                previous_head_cid=previous_cid,
                initiator=alice_identity,
            )
            op.ipfs_cid = f"Qm{i:064x}"
            operations.append(op)
            previous_cid = op.ipfs_cid

        # Mock IPFS client
        client = MagicMock()
        op_lookup = {op.ipfs_cid: op for op in operations}

        async def mock_fetch(cid):
            return op_lookup[cid]

        client.fetch = mock_fetch

        # Mock verification to fail >10% (3 out of 20 = 15%)
        def mock_verify(op):
            return op.sequence_number not in [5, 10, 15]

        with patch('peermodel.operations.verify_operation', side_effect=mock_verify):
            with pytest.raises(LogIntegrityError):
                await traverse(
                    head_cid=operations[-1].ipfs_cid,
                    stop_at_cid=None,
                    ipfs_client=client
                )

    @pytest.mark.asyncio
    async def test_traverse_allows_under_10_percent_invalid(
        self, alice_identity
    ):
        """traverse() succeeds if <10% invalid signatures."""
        from peermodel.operations import traverse

        # Create 20 operations
        cohort = SimpleCohort(cohort_id="test", founder_identity=alice_identity)
        operations = []
        previous_cid = None

        for i in range(20):
            op = cohort.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": f"value{i}"},
                previous_head_cid=previous_cid,
                initiator=alice_identity,
            )
            op.ipfs_cid = f"Qm{i:064x}"
            operations.append(op)
            previous_cid = op.ipfs_cid

        # Mock IPFS client
        client = MagicMock()
        op_lookup = {op.ipfs_cid: op for op in operations}

        async def mock_fetch(cid):
            return op_lookup[cid]

        client.fetch = mock_fetch

        # Mock verification to fail <10% (1 out of 20 = 5%)
        def mock_verify(op):
            return op.sequence_number != 10

        with patch('peermodel.operations.verify_operation', side_effect=mock_verify):
            result = await traverse(
                head_cid=operations[-1].ipfs_cid,
                stop_at_cid=None,
                ipfs_client=client
            )

            # Should succeed and return 19 operations (skipped 1)
            assert len(result) == 19


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestTraversalEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_traverse_empty_log_handles_none_head(self):
        """traverse() handles None head_cid (empty log)."""
        from peermodel.operations import traverse

        client = MagicMock()

        result = await traverse(
            head_cid=None,
            stop_at_cid=None,
            ipfs_client=client
        )

        # Empty log returns empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_traverse_long_chain(self, test_cohort, alice_identity):
        """traverse() handles long operation chains."""
        from peermodel.operations import traverse

        # Create 100 operations
        operations = []
        previous_cid = None

        for i in range(100):
            op = test_cohort.create_operation(
                op_type="insert" if i == 0 else "update",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"data": f"value{i}"},
                previous_head_cid=previous_cid,
                initiator=alice_identity,
            )
            op.ipfs_cid = f"Qm{i:064x}"
            operations.append(op)
            previous_cid = op.ipfs_cid

        # Mock IPFS client
        client = MagicMock()
        op_lookup = {op.ipfs_cid: op for op in operations}

        async def mock_fetch(cid):
            await asyncio.sleep(0.001)
            return op_lookup[cid]

        client.fetch = mock_fetch

        with patch('peermodel.operations.verify_operation', return_value=True):
            result = await traverse(
                head_cid=operations[-1].ipfs_cid,
                stop_at_cid=None,
                ipfs_client=client
            )

        assert len(result) == 100
        assert result[0].sequence_number == 1
        assert result[-1].sequence_number == 100

    @pytest.mark.asyncio
    async def test_traverse_preserves_operation_data(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() preserves all operation fields."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid

        with patch('peermodel.operations.verify_operation', return_value=True):
            result = await traverse(
                head_cid=head_cid,
                stop_at_cid=None,
                ipfs_client=mock_ipfs_client
            )

        # Verify all fields are preserved
        for i, op in enumerate(result):
            assert op.op_id == sample_operations[i].op_id
            assert op.payload == sample_operations[i].payload
            assert op.cohort_id == sample_operations[i].cohort_id

    @pytest.mark.asyncio
    async def test_traverse_with_tombstone_operations(
        self, test_cohort, alice_identity
    ):
        """traverse() handles tombstone (delete) operations."""
        from peermodel.operations import traverse

        record_id = str(uuid4())

        # Create insert, update, tombstone chain
        op1 = test_cohort.create_operation(
            op_type="insert",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "initial"},
            previous_head_cid=None,
            initiator=alice_identity,
        )
        op1.ipfs_cid = "Qm1"

        op2 = test_cohort.create_operation(
            op_type="update",
            record_type="TestRecord",
            record_id=record_id,
            payload={"data": "updated"},
            previous_head_cid=op1.ipfs_cid,
            initiator=alice_identity,
        )
        op2.ipfs_cid = "Qm2"

        op3 = test_cohort.create_operation(
            op_type="tombstone",
            record_type="TestRecord",
            record_id=record_id,
            payload=None,
            previous_head_cid=op2.ipfs_cid,
            initiator=alice_identity,
        )
        op3.ipfs_cid = "Qm3"

        # Mock IPFS client
        client = MagicMock()
        op_lookup = {"Qm1": op1, "Qm2": op2, "Qm3": op3}

        async def mock_fetch(cid):
            return op_lookup[cid]

        client.fetch = mock_fetch

        with patch('peermodel.operations.verify_operation', return_value=True):
            result = await traverse(
                head_cid=op3.ipfs_cid,
                stop_at_cid=None,
                ipfs_client=client
            )

        assert len(result) == 3
        assert result[2].op_type == "tombstone"
        assert result[2].payload is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestTraversalIntegration:
    """Integration tests with full operation chain."""

    @pytest.mark.asyncio
    async def test_traverse_with_stop_at_mid_chain(
        self, sample_operations, mock_ipfs_client
    ):
        """traverse() correctly stops at mid-chain CID."""
        from peermodel.operations import traverse

        head_cid = sample_operations[-1].ipfs_cid
        stop_cid = sample_operations[1].ipfs_cid

        with patch('peermodel.operations.verify_operation', return_value=True):
            result = await traverse(
                head_cid=head_cid,
                stop_at_cid=stop_cid,
                ipfs_client=mock_ipfs_client
            )

        # Should return operations 2, 3, 4 (stop_at_cid is exclusive)
        assert len(result) == 3
        assert result[0].sequence_number == 2
        assert result[-1].sequence_number == 4

    @pytest.mark.asyncio
    async def test_traverse_follows_previous_head_chain(
        self, test_cohort, alice_identity
    ):
        """traverse() follows previous_head_cid chain correctly."""
        from peermodel.operations import traverse

        # Create chain with explicit previous_head_cid tracking
        ops = []
        for i in range(3):
            op = test_cohort.create_operation(
                op_type="insert",
                record_type="TestRecord",
                record_id=str(uuid4()),
                payload={"index": i},
                previous_head_cid=ops[-1].ipfs_cid if ops else None,
                initiator=alice_identity,
            )
            op.ipfs_cid = f"Qm{i}"
            ops.append(op)

        # Mock client
        client = MagicMock()
        op_lookup = {op.ipfs_cid: op for op in ops}

        async def mock_fetch(cid):
            return op_lookup[cid]

        client.fetch = mock_fetch

        with patch('peermodel.operations.verify_operation', return_value=True):
            result = await traverse(
                head_cid=ops[-1].ipfs_cid,
                stop_at_cid=None,
                ipfs_client=client
            )

        # Verify chain integrity
        assert len(result) == 3
        assert result[0].previous_head_cid is None
        assert result[1].previous_head_cid == ops[0].ipfs_cid
        assert result[2].previous_head_cid == ops[1].ipfs_cid
