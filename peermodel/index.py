"""SQLite index schema generation from @indexed decorators (Issue #18)."""

from typing import get_origin
from dataclasses import fields as dataclass_fields
from pathlib import Path

from peermodel.exceptions import SchemaMismatchError


__all__ = ['SYSTEM_COLUMNS', 'get_sqlite_type', 'generate_ddl', 'IndexDB', 'SchemaMismatchError']


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
    ddl_lines = []
    ddl_lines.append(f"CREATE TABLE IF NOT EXISTS {model_name} (")

    # Add system columns first
    system_col_defs = []
    for col_name, col_type in SYSTEM_COLUMNS.items():
        if col_name == '_record_id':
            system_col_defs.append(f"    {col_name} {col_type} PRIMARY KEY")
        else:
            system_col_defs.append(f"    {col_name} {col_type}")

    ddl_lines.extend(system_col_defs)

    # Add model fields
    try:
        model_fields = dataclass_fields(model_class)
        for field in model_fields:
            # Skip internal fields like _id
            if field.name.startswith('_'):
                continue

            # Get the SQLite type for this field
            sqlite_type = get_sqlite_type(field.type)
            ddl_lines.append(f"    {field.name} {sqlite_type}")
    except TypeError:
        # Not a dataclass or fields() call failed
        pass

    # Close the CREATE TABLE statement
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
        raise NotImplementedError("IndexDB.ensure_schema() not implemented yet (Issue #19)")
