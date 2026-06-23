"""CohortRepository: primary ORM interface for cohort-encrypted IPFS records (Issue #28)."""

import json
import sqlite3
import time
from dataclasses import fields as dataclass_fields

from cryptography.fernet import Fernet

from peermodel import primitives


class CohortRepository:
    """Primary ORM interface: save/get/query/delete records with encryption and IPFS persistence."""

    def __init__(
        self,
        cohort,
        member_identity,
        cohort_private_key_bytes,
        index_db,
        ipfs_client,
        sync_manager=None,
    ):
        self.cohort = cohort
        self.member_identity = member_identity
        self.cohort_private_key_bytes = cohort_private_key_bytes
        self.index_db = index_db
        self.ipfs_client = ipfs_client
        self.sync_manager = sync_manager

    async def save(self, doc):
        """Encrypt doc, create insert op, publish to IPFS, apply to index. Returns CID."""
        record_type_name = type(doc).__name__
        record_id = doc._id
        field_values = self._get_field_values(doc)

        payload = self._encrypt_record(field_values)

        op = self.cohort.create_operation(
            op_type='insert',
            record_type=record_type_name,
            record_id=record_id,
            payload=payload,
            previous_head_cid=None,
            initiator=self.member_identity,
        )

        cid = await self.ipfs_client.publish(op)
        self._insert_index_row(record_type_name, doc, op, cid, field_values)
        return cid

    async def get(self, record_type, record_id):
        """Fetch from IPFS, decrypt, deserialize. Returns DocumentObj."""
        rows = self.index_db.query(
            record_type, filters={'_record_id': record_id}, include_tombstoned=False
        )
        if not rows:
            raise KeyError(f"Record not found: {record_id}")

        op = await self.ipfs_client.fetch(rows[0]['_head_cid'])
        field_values = self._decrypt_record(op.payload)
        return self._reconstruct_doc(record_type, record_id, field_values)

    async def query(self, record_type, filters=None):
        """Query SQLite index then fetch+decrypt each from IPFS. Returns list of DocumentObj."""
        rows = self.query_index(record_type, filters=filters)
        results = []
        for row in rows:
            doc = await self.get(record_type, row['_record_id'])
            results.append(doc)
        return results

    def query_index(self, record_type, filters=None, include_tombstoned=False):
        """Return raw SQLite rows without touching IPFS."""
        return self.index_db.query(
            record_type, filters=filters, include_tombstoned=include_tombstoned
        )

    async def delete(self, record_type, record_id):
        """Publish tombstone op and mark record deleted in index. Returns CID."""
        rows = self.index_db.query(
            record_type, filters={'_record_id': record_id}, include_tombstoned=True
        )
        if not rows:
            raise KeyError(f"Record not found: {record_id}")

        record_type_name = record_type.__name__
        op = self.cohort.create_operation(
            op_type='tombstone',
            record_type=record_type_name,
            record_id=record_id,
            payload=None,
            previous_head_cid=rows[0]['_head_cid'],
            initiator=self.member_identity,
        )

        cid = await self.ipfs_client.publish(op)
        self._tombstone_index_row(record_type_name, record_id, cid)
        return cid

    async def sync(self, record_type, current_head_cid):
        """Delegate to sync_manager.incremental_sync()."""
        if self.sync_manager is None:
            raise RuntimeError("No sync manager configured")
        return await self.sync_manager.incremental_sync(
            record_type=record_type, current_head_cid=current_head_cid
        )

    # ── private helpers ──────────────────────────────────────────────────────

    def _get_field_values(self, doc):
        return {
            f.name: getattr(doc, f.name)
            for f in dataclass_fields(doc)
            if not f.name.startswith('_')
        }

    def _encrypt_record(self, field_values):
        fernet_key = Fernet.generate_key()
        plaintext = json.dumps(field_values).encode('utf-8')
        encrypted_record = Fernet(fernet_key).encrypt(plaintext)
        ciphertext, nonce, tag, ephemeral_pub = primitives.encrypt_to_recipient(
            fernet_key, self.member_identity['x25519_public']
        )
        return {
            'encrypted_record': encrypted_record,
            'key_ciphertext': ciphertext,
            'key_nonce': nonce,
            'key_tag': tag,
            'key_ephemeral_pub': ephemeral_pub,
        }

    def _decrypt_record(self, payload):
        fernet_key = primitives.decrypt_from_sender(
            payload['key_ciphertext'],
            payload['key_nonce'],
            payload['key_tag'],
            payload['key_ephemeral_pub'],
            self.member_identity['x25519_private'],
        )
        plaintext = Fernet(fernet_key).decrypt(payload['encrypted_record'])
        return json.loads(plaintext)

    def _reconstruct_doc(self, record_type, record_id, field_values):
        doc = record_type(**field_values)
        doc._id = record_id
        return doc

    def _insert_index_row(self, record_type_name, doc, op, cid, field_values):
        columns = [
            '_record_id', '_op_id', '_sequence', '_timestamp',
            '_head_cid', '_tombstoned', '_schema_version',
        ]
        values = [
            doc._id, op.op_id, op.sequence_number, int(time.time()),
            cid, 0, 1,
        ]
        for col, val in field_values.items():
            columns.append(col)
            values.append(val)

        col_str = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(values))

        conn = sqlite3.connect(self.index_db.db_path)
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO {record_type_name} ({col_str}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
        finally:
            conn.close()

    def _tombstone_index_row(self, record_type_name, record_id, cid):
        conn = sqlite3.connect(self.index_db.db_path)
        try:
            conn.execute(
                f"UPDATE {record_type_name} SET _tombstoned = 1, _head_cid = ? WHERE _record_id = ?",
                (cid, record_id),
            )
            conn.commit()
        finally:
            conn.close()
