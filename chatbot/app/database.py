"""Read-only SQL access for the chatbot.

Three independent layers keep the chatbot from changing data:
  1. the database role (goodwill_chatbot) only has SELECT, and every
     transaction it opens is read-only (setup_readonly_role.sql),
  2. each query runs in an explicitly read-only transaction that is rolled back,
  3. this module rejects anything that is not a single SELECT/WITH statement.
"""

import re
from datetime import date, datetime, time
from decimal import Decimal

import psycopg

from . import config

_WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|merge|upsert|drop|alter|create|truncate|grant|revoke|copy|call|do|vacuum|"
    r"analyze|refresh|lock|set|reset|listen|notify|prepare|execute|deallocate|comment|security|import|"
    r"pg_sleep|pg_read_file|pg_ls_dir|lo_import|lo_export|dblink)\b",
    re.IGNORECASE,
)


class QueryRejected(ValueError):
    """The SQL is not a single read-only SELECT statement."""


def _without_literals(sql):
    """SQL with quoted strings and identifiers blanked, so words inside them
    (e.g. WHERE review_text ILIKE '%update%') don't trip the keyword check."""
    return re.sub(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"", "''", sql)


def validate_select(sql):
    """Return the cleaned statement, or raise QueryRejected."""
    statement = (sql or "").strip().rstrip(";").strip()
    if not statement:
        raise QueryRejected("Empty query.")
    bare = _without_literals(statement)
    if "--" in bare or "/*" in bare:
        raise QueryRejected("SQL comments are not allowed.")
    if ";" in bare:
        raise QueryRejected("Only one statement per query is allowed.")
    if not re.match(r"(?is)^\s*(select|with)\b", bare):
        raise QueryRejected("Only SELECT queries (optionally starting with WITH) are allowed.")
    word = _WRITE_WORDS.search(bare)
    if word:
        raise QueryRejected(f"'{word.group(0)}' is not allowed in chatbot queries.")
    return statement


def _plain(value):
    """JSON-safe cell value; numbers stay exact (Decimal → string)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def run_query(sql, conninfo=None, max_rows=None):
    """Run one read-only SELECT and return
    {sql, columns, rows, row_count, truncated} or {sql, error}."""
    max_rows = max_rows or config.MAX_RESULT_ROWS
    try:
        statement = validate_select(sql)
    except QueryRejected as e:
        return {"sql": sql, "error": str(e)}
    try:
        with psycopg.connect(conninfo or config.DATABASE_URL, connect_timeout=5) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '5s'")
                cur.execute(f"SET LOCAL TIME ZONE '{config.REPORT_TIMEZONE}'")
                cur.execute(statement)
                if cur.description is None:
                    return {"sql": statement, "error": "The statement returned no result set."}
                columns = [d.name for d in cur.description]
                fetched = cur.fetchmany(max_rows + 1)
            conn.rollback()
    except psycopg.Error as e:
        message = (e.diag.message_primary if getattr(e, "diag", None) and e.diag.message_primary else str(e)).strip()
        return {"sql": statement, "error": message}
    rows = [[_plain(v) for v in row] for row in fetched[:max_rows]]
    return {"sql": statement, "columns": columns, "rows": rows, "row_count": len(rows),
            "truncated": len(fetched) > max_rows}


def describe_schema(conninfo=None):
    """Tables, materialized views and the columns this role may read."""
    query = """
        SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'm')
          AND a.attnum > 0 AND NOT a.attisdropped
          AND has_column_privilege(c.oid, a.attnum, 'SELECT')
          AND c.relname <> 'schema_migration'
        ORDER BY c.relname, a.attnum"""
    tables = {}
    with psycopg.connect(conninfo or config.DATABASE_URL, connect_timeout=5) as conn:
        conn.read_only = True
        for table, column, data_type in conn.execute(query):
            tables.setdefault(table, []).append(f"{column} {data_type}")
        conn.rollback()
    return "\n".join(f"{table}({', '.join(cols)})" for table, cols in tables.items())
