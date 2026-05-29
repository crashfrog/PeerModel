"""SQLite index schema generation from @indexed decorators (Issue #18)."""

import sqlite3
from typing import get_origin
from dataclasses import fields as dataclass_fields
from pathlib import Path
from datetime import datetime

from peermodel.exceptions import SchemaMismatchError
from peermodel.operations import OperationRecord

__all__ = [
    "SYSTEM_COLUMNS",
    "get_sqlite_type",
    "generate_ddl",
    "IndexDB",
    "SchemaMismatchError",
]


# System columns that appear in every indexed table
SYSTEM_COLUMNS = {
    "_record_id": "TEXT",
    "_op_id": "TEXT",
    "_sequence": "INTEGER",
    "_timestamp": "INTEGER",
    "_head_cid": "TEXT",
    "_tombstoned": "INTEGER",
    "_schema_version": "INTEGER",
}


def get_sqlite_type(python_type):
    """
    Map Python types to SQLite column types.

    Args:
        python_type: A Python type (str, int, float, bool, dict, list,
            bytes, or typing hints)

    Returns:
        SQLite type string (TEXT, INTEGER, REAL, BLOB)
    """
    # Handle None type
    if python_type is None or python_type is type(None):
        return "TEXT"

    # Handle typing hints like List[str], Dict[str, int]
    origin = get_origin(python_type)
    if origin is not None:
        # For any generic type (List, Dict, Tuple, etc.), use BLOB
        # for CBOR encoding
        return "BLOB"

    # Handle basic types
    if python_type is str:
        return "TEXT"
    elif python_type is int:
        return "INTEGER"
    elif python_type is float:
        return "REAL"
    elif python_type is bool:
        return "INTEGER"  # SQLite uses 0/1 for boolean
    elif python_type is dict:
        return "BLOB"  # CBOR-encoded
    elif python_type is list:
        return "BLOB"  # CBOR-encoded
    elif python_type is bytes:
        return "BLOB"
    else:
        # Default for unknown types
        return "BLOB"


def generate_ddl(model_class):
    """
    Generate SQLite DDL (CREATE TABLE + CREATE INDEX statements) for
    a model class.

    Args:
        model_class: A dataclass model decorated with @peer.model

    Returns:
        String containing CREATE TABLE and CREATE INDEX statements
    """
    # Get the model name
    model_name = model_class.__name__

    # Get indexed fields (if any)
    indexed_fields = set()
    if hasattr(model_class, "_peermodel_indexed_fields"):
        indexed_fields = model_class._peermodel_indexed_fields

    # Start building the CREATE TABLE statement
    col_defs = []

    # Add system columns first
    for col_name, col_type in SYSTEM_COLUMNS.items():
        if col_name == "_record_id":
            col_defs.append(f"    {col_name} {col_type} PRIMARY KEY")
        else:
            col_defs.append(f"    {col_name} {col_type}")

    # Add model fields
    try:
        model_fields = dataclass_fields(model_class)
        for field in model_fields:
            # Skip internal fields like _id
            if field.name.startswith("_"):
                continue

            # Get the SQLite type for this field
            sqlite_type = get_sqlite_type(field.type)
            col_defs.append(f"    {field.name} {sqlite_type}")
    except TypeError:
        # Not a dataclass or fields() call failed
        pass

    # Join column definitions with commas
    ddl_lines = [f"CREATE TABLE IF NOT EXISTS {model_name} ("]
    for i, col_def in enumerate(col_defs):
        if i < len(col_defs) - 1:
            ddl_lines.append(col_def + ",")
        else:
            ddl_lines.append(col_def)
    ddl_lines.append(");")

    # Create the initial DDL string (table definition)
    ddl = "\n".join(ddl_lines)

    # Add CREATE INDEX statements for indexed fields
    if indexed_fields:
        index_statements = []
        for field_name in sorted(indexed_fields):
            index_name = f"{model_name}_{field_name}_idx"
            index_stmt = (
                f"CREATE INDEX IF NOT EXISTS {index_name} ON "
                f"{model_name} ({field_name});"
            )
            index_statements.append(index_stmt)

        if index_statements:
            ddl = ddl + "\n\n" + "\n".join(index_statements)

    return ddl


class IndexDB:
    """
    Manages the SQLite index for one or more record types within a cohort.

    The database file lives at the configured path (e.g., ~/.peermodel/<cohort_id>/index.db).
    One IndexDB instance is shared across all record types for a cohort.
    Each record type gets its own table, named by the record type.
    A shared _node_state table holds NodeState rows.
    """

    def __init__(self, db_path: Path):
        """
        Initialize IndexDB with a database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        # Ensure parent directory exists
        if not self.db_path.parent.exists():
            raise FileNotFoundError(f"Directory does not exist: {self.db_path.parent}")

    def ensure_schema(self, model_class: type) -> None:
        """
        Create or verify the SQLite schema for a DocumentObj subclass.

        Creates:
          - Record table named after record_type with columns for each annotated field
          - System columns: _record_id, _op_id, _sequence, _timestamp, _head_cid,
            _tombstoned, _schema_version
          - CREATE INDEX on each field decorated with @indexed
          - CREATE INDEX on _tombstoned (for live-record filtering)
          - _node_state table if not exists

        Idempotent: safe to call on an existing database.
        Raises SchemaMismatchError if the existing table has incompatible
        columns (different types or missing non-nullable columns).

        Args:
            model_class: A dataclass model decorated with @peer.model

        Raises:
            SchemaMismatchError: If existing schema doesn't match expected schema
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            model_name = model_class.__name__

            # Check if table already exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (model_name,),
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Verify existing schema matches expected schema
                self._verify_schema(cursor, model_class)
            else:
                # Create the table
                ddl = generate_ddl(model_class)
                cursor.executescript(ddl)

            # Create or verify indexes
            self._ensure_indexes(cursor, model_class)

            # Create _node_state table if not exists
            self._ensure_node_state_table(cursor)

            conn.commit()
        finally:
            conn.close()

    def _verify_schema(self, cursor: sqlite3.Cursor, model_class: type) -> None:
        """
        Verify that the existing table schema matches the expected schema.

        Args:
            cursor: SQLite cursor
            model_class: The model class with expected schema

        Raises:
            SchemaMismatchError: If existing schema doesn't match expected
        """
        model_name = model_class.__name__

        # Get existing columns from database
        cursor.execute(f"PRAGMA table_info({model_name})")
        existing_cols = {row[1]: row[2] for row in cursor.fetchall()}

        # Build expected schema
        expected_cols = dict(SYSTEM_COLUMNS)

        # Add model fields
        try:
            model_fields = dataclass_fields(model_class)
            for field in model_fields:
                if field.name.startswith("_"):
                    continue
                sqlite_type = get_sqlite_type(field.type)
                expected_cols[field.name] = sqlite_type
        except TypeError:
            pass

        # Check all expected columns exist with correct types
        for col_name, col_type in expected_cols.items():
            if col_name not in existing_cols:
                raise SchemaMismatchError(
                    f"Missing column '{col_name}' in table '{model_name}'"
                )
            if existing_cols[col_name] != col_type:
                raise SchemaMismatchError(
                    f"Column '{col_name}' has type '{existing_cols[col_name]}' "
                    f"but expected '{col_type}' in table '{model_name}'"
                )

    def _ensure_indexes(self, cursor: sqlite3.Cursor, model_class: type) -> None:
        """
        Create indexes on @indexed fields and _tombstoned column.

        Args:
            cursor: SQLite cursor
            model_class: The model class
        """
        model_name = model_class.__name__

        # Get indexed fields
        indexed_fields = set()
        if hasattr(model_class, "_peermodel_indexed_fields"):
            indexed_fields = model_class._peermodel_indexed_fields

        # Create indexes for indexed fields
        for field_name in indexed_fields:
            index_name = f"{model_name}_{field_name}_idx"
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {model_name} ({field_name})"
            )

        # Create index on _tombstoned
        tombstone_index_name = f"{model_name}__tombstoned_idx"
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {tombstone_index_name} ON {model_name} (_tombstoned)"
        )

    def _ensure_node_state_table(self, cursor: sqlite3.Cursor) -> None:
        """
        Create _node_state table if not exists.

        Args:
            cursor: SQLite cursor
        """
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _node_state (
                cohort_id TEXT NOT NULL,
                record_type TEXT NOT NULL,
                last_synced_head_cid TEXT,
                last_synced_sequence INTEGER NOT NULL,
                snapshot_cid TEXT,
                snapshot_sequence INTEGER NOT NULL,
                index_status TEXT NOT NULL,
                last_sync_at TEXT,
                PRIMARY KEY (cohort_id, record_type)
            )
        """)

    def apply_operation(self, model_class: type, op: OperationRecord) -> None:
        """
        Apply a single operation to the index database.

        Handles INSERT, UPDATE, and TOMBSTONE operations idempotently.
        Operations are idempotent: replaying the same op_id is a no-op.

        Args:
            model_class: The model class (used to get table name)
            op: OperationRecord to apply

        Operation types:
            - insert: INSERT OR REPLACE new/updated row
            - update: UPDATE existing row with new payload
            - tombstone: SET _tombstoned=1 on existing row
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            model_name = model_class.__name__

            # Check if this op_id has already been applied (idempotency check)
            cursor.execute(
                f"SELECT _op_id FROM {model_name} WHERE _record_id = ? AND _op_id = ?",
                (op.record_id, op.op_id),
            )
            if cursor.fetchone() is not None:
                # Operation already applied, skip
                return

            # Convert timestamp to integer (Unix timestamp in milliseconds)
            try:
                # Parse ISO format timestamp
                if op.timestamp.endswith("Z"):
                    ts_str = op.timestamp[:-1]
                else:
                    ts_str = op.timestamp
                dt = datetime.fromisoformat(ts_str)
                timestamp_int = int(dt.timestamp() * 1000)
            except (ValueError, AttributeError):
                # Fallback: use current time
                timestamp_int = int(datetime.utcnow().timestamp() * 1000)

            if op.op_type == "insert":
                # INSERT OR REPLACE: insert new row or replace existing
                self._apply_insert(cursor, model_name, op, timestamp_int)
            elif op.op_type == "update":
                # UPDATE: update existing row
                self._apply_update(cursor, model_name, op, timestamp_int)
            elif op.op_type == "tombstone":
                # TOMBSTONE: set _tombstoned=1
                self._apply_tombstone(cursor, model_name, op, timestamp_int)

            conn.commit()
        finally:
            conn.close()

    def _apply_insert(
        self,
        cursor: sqlite3.Cursor,
        model_name: str,
        op: OperationRecord,
        timestamp_int: int,
    ) -> None:
        """
        Apply an INSERT operation (INSERT OR REPLACE).

        Args:
            cursor: SQLite cursor
            model_name: Name of the table
            op: OperationRecord with op_type='insert'
            timestamp_int: Timestamp as integer
        """
        # Build the column list and value placeholders
        columns = [
            "_record_id",
            "_op_id",
            "_sequence",
            "_timestamp",
            "_head_cid",
            "_tombstoned",
        ]
        values = [
            op.record_id,
            op.op_id,
            op.sequence_number,
            timestamp_int,
            op.previous_head_cid,
            0,
        ]

        # Add payload fields to columns and values
        if op.payload:
            for key, val in op.payload.items():
                columns.append(key)
                values.append(val)

        # Build INSERT OR REPLACE statement
        placeholders = ",".join(["?" for _ in values])
        col_list = ",".join(columns)
        sql = (
            f"INSERT OR REPLACE INTO {model_name} ({col_list}) VALUES ({placeholders})"
        )

        cursor.execute(sql, values)

    def _apply_update(
        self,
        cursor: sqlite3.Cursor,
        model_name: str,
        op: OperationRecord,
        timestamp_int: int,
    ) -> None:
        """
        Apply an UPDATE operation.

        Args:
            cursor: SQLite cursor
            model_name: Name of the table
            op: OperationRecord with op_type='update'
            timestamp_int: Timestamp as integer
        """
        # Build SET clause for system columns
        set_parts = [
            "_op_id = ?",
            "_sequence = ?",
            "_timestamp = ?",
            "_head_cid = ?",
            "_tombstoned = 0",  # Update always un-tombstones
        ]
        values = [op.op_id, op.sequence_number, timestamp_int, op.previous_head_cid]

        # Add payload fields to SET clause
        if op.payload:
            for key, val in op.payload.items():
                set_parts.append(f"{key} = ?")
                values.append(val)

        # Add WHERE clause value
        values.append(op.record_id)

        # Build UPDATE statement
        set_clause = ",".join(set_parts)
        sql = f"UPDATE {model_name} SET {set_clause} WHERE _record_id = ?"

        cursor.execute(sql, values)

    def _apply_tombstone(
        self,
        cursor: sqlite3.Cursor,
        model_name: str,
        op: OperationRecord,
        timestamp_int: int,
    ) -> None:
        """
        Apply a TOMBSTONE operation (mark row as deleted).

        Args:
            cursor: SQLite cursor
            model_name: Name of the table
            op: OperationRecord with op_type='tombstone'
            timestamp_int: Timestamp as integer
        """
        sql = f"""
            UPDATE {model_name}
            SET _op_id = ?, _sequence = ?, _timestamp = ?, _head_cid = ?, _tombstoned = 1
            WHERE _record_id = ?
        """
        cursor.execute(
            sql,
            (
                op.op_id,
                op.sequence_number,
                timestamp_int,
                op.previous_head_cid,
                op.record_id,
            ),
        )
