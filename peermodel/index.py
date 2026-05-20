"""SQLite schema generation from @indexed decorators.

This module handles parsing @indexed metadata from model classes and
generating SQLite table definitions (DDL) with proper type mappings,
system columns, and indexes.
"""

from typing import get_origin
from dataclasses import fields


def get_sqlite_type(python_type):
    """Map Python types to SQLite types.

    Args:
        python_type: A Python type annotation

    Returns:
        SQLite type string (TEXT, INTEGER, REAL, BLOB)

    Examples:
        get_sqlite_type(str) -> 'TEXT'
        get_sqlite_type(int) -> 'INTEGER'
        get_sqlite_type(list) -> 'BLOB'
        get_sqlite_type(List[str]) -> 'BLOB'  # noqa: E501
    """
    # Handle None type
    if python_type is None or python_type is type(None):
        return 'BLOB'

    # Handle typing module generics (List, Dict, etc.)
    origin = get_origin(python_type)
    if origin is not None:
        # List[T], Tuple[T], etc. all map to BLOB
        if origin in (list, tuple, dict):
            return 'BLOB'
        return 'BLOB'

    # Handle basic types
    if python_type is str:
        return 'TEXT'
    elif python_type is int:
        return 'INTEGER'
    elif python_type is float:
        return 'REAL'
    elif python_type is bool:
        return 'INTEGER'
    elif python_type is bytes:
        return 'BLOB'
    elif python_type is dict:
        return 'BLOB'
    elif python_type is list:
        return 'BLOB'
    else:
        # Default to BLOB for unknown types
        return 'BLOB'


# System columns required for every table
SYSTEM_COLUMNS = {
    '_record_id': 'TEXT',          # UUID as text (PRIMARY KEY)
    '_op_id': 'TEXT',              # Operation ID
    '_sequence': 'INTEGER',        # Sequence number
    '_timestamp': 'INTEGER',       # Unix timestamp
    '_head_cid': 'TEXT',           # IPFS CID
    '_tombstoned': 'INTEGER',      # Boolean 0/1
    '_schema_version': 'INTEGER'   # Schema version number
}


def generate_ddl(model_class):
    """Generate CREATE TABLE DDL from a model class.

    Includes all system columns and any indexed fields from the model.

    Args:
        model_class: A model class decorated with @peer.model

    Returns:
        String containing CREATE TABLE and CREATE INDEX DDL statements
    """
    table_name = model_class.__name__

    # Start DDL with CREATE TABLE IF NOT EXISTS
    ddl_lines = []
    ddl_lines.append(f'CREATE TABLE IF NOT EXISTS {table_name} (')

    # Add system columns first
    column_defs = []
    system_col_names = [
        '_record_id', '_op_id', '_sequence', '_timestamp',
        '_head_cid', '_tombstoned', '_schema_version'
    ]
    for col_name in system_col_names:
        col_type = SYSTEM_COLUMNS[col_name]
        if col_name == '_record_id':
            column_defs.append(f'    {col_name} {col_type} PRIMARY KEY')
        else:
            column_defs.append(f'    {col_name} {col_type}')

    # Add model fields
    try:
        for field in fields(model_class):
            if field.name.startswith('_'):
                # Skip private fields like _id
                continue
            sql_type = get_sqlite_type(field.type)
            column_defs.append(f'    {field.name} {sql_type}')
    except (TypeError, AttributeError):
        # If fields() fails, this might not be a dataclass yet
        # Try to get annotations directly
        if hasattr(model_class, '__annotations__'):
            for field_name, field_type in (
                model_class.__annotations__.items()
            ):
                if field_name.startswith('_'):
                    continue
                sql_type = get_sqlite_type(field_type)
                column_defs.append(f'    {field_name} {sql_type}')

    # Join column definitions and close table definition
    ddl_lines.append(',\n'.join(column_defs))
    ddl_lines.append(')')

    # Add CREATE INDEX statements for indexed fields
    indexed_fields = getattr(model_class, '_peermodel_indexed_fields',
                             set())
    for field_name in indexed_fields:
        index_name = f'{table_name}_{field_name}_idx'
        ddl_lines.append(
            f'CREATE INDEX IF NOT EXISTS {index_name} '
            f'ON {table_name} ({field_name})'
        )

    return '\n'.join(ddl_lines)
