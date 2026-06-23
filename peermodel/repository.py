#!/usr/bin/env python

"""CohortRepository: lazy migration on read for DocumentObj records.

Fetches OperationRecords from IPFS and applies schema migrations when the
stored schema_version differs from the current package version.  The
original OperationRecord in the log is never mutated.
"""

import copy
import peermodel.migrations as _migrations
from peermodel.peermodel import DocumentObj


class _StubDb:
    """Minimal database stub for deserialising flat records without references."""

    def _is_reference(self, value):
        return False

    def _retrieve_record(self, *args):
        raise RuntimeError("References not supported in CohortRepository")


class CohortRepository:
    """Repository that lazily migrates records to the current schema on read.

    Args:
        ipfs_client: Object with a synchronous ``fetch(record_id) -> OperationRecord`` method.
        package_name:  Package name passed to ``load_engine()`` to locate MIGRATIONS.
        current_version: Target schema version (e.g. ``'2.0.0'``).
    """

    def __init__(self, ipfs_client, package_name: str, current_version: str):
        self._client = ipfs_client
        self._package_name = package_name
        self._current_version = current_version

    def get(self, record_type: type, record_id: str) -> DocumentObj:
        """Fetch a record and return a migrated DocumentObj instance.

        If the stored ``schema_version`` differs from ``current_version``,
        the migration engine is loaded and applied to a *copy* of the payload
        so the original OperationRecord is unchanged.

        Args:
            record_type: DocumentObj subclass to instantiate.
            record_id:   Identifier used to fetch the OperationRecord.

        Returns:
            Fully migrated instance of ``record_type``.
        """
        op = self._client.fetch(record_id)

        payload = copy.deepcopy(op.payload)

        if op.schema_version != self._current_version:
            engine = _migrations.load_engine(self._package_name)
            payload = engine.apply(
                op.record_type,
                payload,
                op.schema_version,
                self._current_version,
            )

        return record_type._from_storage(_StubDb(), op.record_id, payload)
