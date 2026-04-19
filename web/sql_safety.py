"""SQL safety helpers — prevent SQL injection via dynamic table/column names."""

import re

# Valid SQL identifier pattern
_IDENT_RE = re.compile(r'^[a-zA-Z_]\w*$')


def safe_table(name, allowed_set):
    """Validate table name against an explicit allowlist.

    Args:
        name: Table name to validate
        allowed_set: Set of allowed table names

    Returns:
        The validated table name (unchanged)

    Raises:
        ValueError: If name is not in allowed_set
    """
    if name not in allowed_set:
        raise ValueError(f'Table {name!r} not in allowed set')
    return name


def safe_columns(data_dict, allowed_list):
    """Filter a dict to only keys present in allowed_list and matching identifier pattern.

    Args:
        data_dict: Dict of column_name -> value
        allowed_list: Collection of allowed column names

    Returns:
        Filtered dict with only allowed keys that match identifier pattern
    """
    allowed = set(allowed_list)
    return {k: v for k, v in data_dict.items()
            if k in allowed and _IDENT_RE.match(k)}


def build_update(table, data_dict, allowed_columns, where_col='id', where_val=None):
    """Build a safe UPDATE statement with parameterized values.

    Args:
        table: Table name (must be in caller's allowed set — caller validates)
        data_dict: Dict of column_name -> value to update
        allowed_columns: Collection of allowed column names
        where_col: WHERE clause column (default 'id')
        where_val: WHERE clause value

    Returns:
        Tuple of (sql_string, params_list)

    Raises:
        ValueError: If no valid columns to update, or where_col invalid
    """
    if not _IDENT_RE.match(where_col):
        raise ValueError(f'Invalid WHERE column: {where_col!r}')
    filtered = safe_columns(data_dict, allowed_columns)
    if not filtered:
        raise ValueError('No valid columns to update')
    set_clause = ', '.join(f'{col} = ?' for col in filtered)
    params = list(filtered.values()) + [where_val]
    sql = f'UPDATE {table} SET {set_clause} WHERE {where_col} = ?'
    return sql, params


def safe_column(name, allowed_set):
    """V8-07: Validate a single column name against an allowlist.

    Use for sort_by, order_by, and other single-column dynamic SQL.
    Returns the validated name or raises ValueError.
    """
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f'Invalid column name: {name!r}')
    if name not in allowed_set:
        raise ValueError(f'Column {name!r} not in allowed set')
    return name


def build_insert(table, data_dict, allowed_columns):
    """Build a safe INSERT statement with parameterized values.

    Args:
        table: Table name (must be in caller's allowed set — caller validates)
        data_dict: Dict of column_name -> value to insert
        allowed_columns: Collection of allowed column names

    Returns:
        Tuple of (sql_string, params_list)

    Raises:
        ValueError: If no valid columns to insert
    """
    filtered = safe_columns(data_dict, allowed_columns)
    if not filtered:
        raise ValueError('No valid columns to insert')
    cols = ', '.join(filtered.keys())
    placeholders = ', '.join('?' for _ in filtered)
    params = list(filtered.values())
    sql = f'INSERT INTO {table} ({cols}) VALUES ({placeholders})'
    return sql, params
