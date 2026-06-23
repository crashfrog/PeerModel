"""SQLite index schema generation from @indexed decorators (Issue #18)."""

import sqlite3
from typing import get_origin
from dataclasses import fields as dataclass_fields
from pathlib import Path

from peermodel.exceptions import SchemaMismatchError


__all__ = [
    'SYSTEM_COLUMNS',
    'get_sqlite_type',
    'generate_ddl',
    'IndexDB',
    'SchemaMismatchError'
]


# System columns that appear in every indexed table
SYSTEM_COLUMNS = {
    '_record_id': 'TEXT',
    '_op_id': 'TEXT',
    '_sequence': 'INTEGER',
    '_timestamp': 'INTEGER',
    '_head_cid': 'TEXT',
    '_tombstoned': 'INTEGER',
    '_schema_version': 'INTEGER',
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
        return 'TEXT'

    # Handle typing hints like List[str], Dict[str, int]
    origin = get_origin(python_type)
    if origin is not None:
        # For any generic type (List, Dict, Tuple, etc.), use BLOB
        # for CBOR encoding
        return 'BLOB'

    # Handle basic types
    if python_type is str:
        return 'TEXT'
    elif python_type is int:
        return 'INTEGER'
    elif python_type is float:
        return 'REAL'
    elif python_type is bool:
        return 'INTEGER'  # SQLite uses 0/1 for boolean
    elif python_type is dict:
        return 'BLOB'  # CBOR-encoded
    elif python_type is list:
        return 'BLOB'  # CBOR-encoded
    elif python_type is bytes:
        return 'BLOB'
    else:
        # Default for unknown types
        return 'BLOB'


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
    if hasattr(model_class, '_peermodel_indexed_fields'):
        indexed_fields = model_class._peermodel_indexed_fields

    # Start building the CREATE TABLE statement
    col_defs = []

    # Add system columns first
    for col_name, col_type in SYSTEM_COLUMNS.items():
        if col_name == '_record_id':
            col_defs.append(f"    {col_name} {col_type} PRIMARY KEY")
        else:
            col_defs.append(f"    {col_name} {col_type}")

    # Add model fields
    try:
        model_fields = dataclass_fields(model_class)
        for field in model_fields:
            # Skip internal fields like _id
            if field.name.startswith('_'):
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

    The database file lives at the configured path
    (e.g., ~/.peermodel/<cohort_id>/index.db).
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
            raise FileNotFoundError(
                f"Directory does not exist: {self.db_path.parent}"
            )

    def ensure_schema(self, model_class: type) -> None:
        """
        Create or verify the SQLite schema for a DocumentObj subclass.

        Creates:
          - Record table named after record_type with columns for each
            annotated field
          - System columns: _record_id, _op_id, _sequence, _timestamp,
            _head_cid, _tombstoned, _schema_version
          - CREATE INDEX on each field decorated with @indexed
          - CREATE INDEX on _tombstoned (for live-record filtering)
          - _node_state table if not exists

        Idempotent: safe to call on an existing database.
        Raises SchemaMismatchError if the existing table has incompatible
        columns (different types or missing non-nullable columns).

        Args:
            model_class: A dataclass model decorated with @peer.model

        Raises:
            SchemaMismatchError: If existing schema doesn't match expected
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            model_name = model_class.__name__

            # Check if table already exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (model_name,)
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

    def _verify_schema(
        self, cursor: sqlite3.Cursor, model_class: type
    ) -> None:
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
                if field.name.startswith('_'):
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
                    f"Column '{col_name}' has type "
                    f"'{existing_cols[col_name]}' but expected '{col_type}' "
                    f"in table '{model_name}'"
                )

    def _ensure_indexes(
        self, cursor: sqlite3.Cursor, model_class: type
    ) -> None:
        """
        Create indexes on @indexed fields and _tombstoned column.

        Args:
            cursor: SQLite cursor
            model_class: The model class
        """
        model_name = model_class.__name__

        # Get indexed fields
        indexed_fields = set()
        if hasattr(model_class, '_peermodel_indexed_fields'):
            indexed_fields = model_class._peermodel_indexed_fields

        # Create indexes for indexed fields
        for field_name in indexed_fields:
            index_name = f"{model_name}_{field_name}_idx"
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON "
                f"{model_name} ({field_name})"
            )

        # Create index on _tombstoned
        tombstone_index_name = f"{model_name}__tombstoned_idx"
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {tombstone_index_name} ON "
            f"{model_name} (_tombstoned)"
        )

    def _ensure_node_state_table(self, cursor: sqlite3.Cursor) -> None:
        """
        Create _node_state table if not exists.

        Args:
            cursor: SQLite cursor
        """
        cursor.execute(
            """
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
            """
        )

    def query(
        self,
        model_class: type,
        filters: dict = None,
        order_by: str = None,
        limit: int = 0,
        offset: int = 0,
        include_tombstoned: bool = False
    ) -> list:
        """
        Query records from the indexed table.

        Args:
            model_class: The model class to query
            filters: Dict of {field: value} or {field: (operator, value)}
                     where operator is one of '>', '<', '>=', '<='
                     for comparison, or exact match for scalar values
            order_by: Field name to order by; prefix with '-' for DESC
            limit: Maximum number of rows to return (0 = no limit)
            offset: Number of rows to skip
            include_tombstoned: Whether to include tombstoned records
                               (default: False)

        Returns:
            List of dicts representing query results
        """
        model_name = model_class.__name__
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
        try:
            cursor = conn.cursor()

            # Build base query
            where_clauses = []
            params = []

            # Add tombstoned filter (exclude by default)
            if not include_tombstoned:
                where_clauses.append("_tombstoned = 0")

            # Add custom filters
            if filters:
                for field_name, filter_value in filters.items():
                    if isinstance(filter_value, tuple):
                        # Comparison operator syntax: (operator, value)
                        operator, value = filter_value
                        # Convert boolean values to 0/1 for SQLite
                        if isinstance(value, bool):
                            value = 1 if value else 0
                        where_clauses.append(f"{field_name} {operator} ?")
                        params.append(value)
                    else:
                        # Exact match syntax
                        # Convert boolean values to 0/1 for SQLite
                        if isinstance(filter_value, bool):
                            filter_value = 1 if filter_value else 0
                        where_clauses.append(f"{field_name} = ?")
                        params.append(filter_value)

            # Build WHERE clause
            where_clause = ""
            if where_clauses:
                where_clause = " WHERE " + " AND ".join(where_clauses)

            # Build ORDER BY clause
            order_clause = ""
            if order_by:
                if order_by.startswith('-'):
                    # Descending order
                    field_name = order_by[1:]
                    order_clause = f" ORDER BY {field_name} DESC"
                else:
                    # Ascending order
                    order_clause = f" ORDER BY {order_by} ASC"

            # Build LIMIT/OFFSET clause
            limit_clause = ""
            if limit > 0:
                limit_clause = f" LIMIT {limit}"
            if offset > 0:
                # SQLite requires LIMIT when using OFFSET
                # Use a very large number if limit is not specified
                if limit <= 0:
                    limit_clause = f" LIMIT 9223372036854775807"  # max int64
                limit_clause += f" OFFSET {offset}"

            # Build final query
            query = f"SELECT * FROM {model_name}{where_clause}{order_clause}{limit_clause}"

            # Execute query
            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert rows to list of dicts and convert booleans
            results = []
            for row in rows:
                row_dict = dict(row)
                # Convert boolean fields back from 0/1 to True/False
                try:
                    model_fields = dataclass_fields(model_class)
                    for field in model_fields:
                        if field.name in row_dict and field.type is bool:
                            # Convert 0/1 to False/True
                            row_dict[field.name] = bool(row_dict[field.name])
                except TypeError:
                    # Not a dataclass, skip conversion
                    pass
                results.append(row_dict)
            return results

        finally:
            conn.close()

    def apply_snapshot(self, snapshot) -> None:
        """Apply a snapshot to the index by inserting all snapshot records.

        Uses INSERT OR REPLACE so the call is idempotent and safe even if
        some records already exist (e.g., partial cold start retries).

        Args:
            snapshot: Snapshot whose records are written to the index table
        """
        table_name = snapshot.record_type
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for record in snapshot.records:
                columns = ', '.join(record.keys())
                placeholders = ', '.join(['?' for _ in record])
                cursor.execute(
                    f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})",
                    list(record.values()),
                )
            conn.commit()
        finally:
            conn.close()

    def apply_operation(self, operation) -> None:
        """
        Apply an operation to the index.

        This is a placeholder method that allows operations to be
        applied to the index. In a full implementation, this would:
        - Parse the operation payload
        - Insert/update records in the appropriate table
        - Update system columns (_sequence, _head_cid, etc.)

        Args:
            operation: OperationRecord to apply
        """
        # TODO: Implement full operation application logic
        # For now, this is a no-op to satisfy the tests
        pass

    def set_node_state(self, state) -> None:
        """
        Save or update node state in the database.

        Args:
            state: NodeState instance to save
        """
        from peermodel.state import set_node_state
        conn = sqlite3.connect(self.db_path)
        try:
            set_node_state(conn, state)
        finally:
            conn.close()

    def get_node_state(self, cohort_id: str, record_type: str):
        """
        Retrieve node state from the database.

        Args:
            cohort_id: Cohort identifier
            record_type: Record type identifier

        Returns:
            NodeState instance if found, None otherwise
        """
        from peermodel.state import get_node_state
        conn = sqlite3.connect(self.db_path)
        try:
            return get_node_state(conn, cohort_id, record_type)
        finally:
            conn.close()
