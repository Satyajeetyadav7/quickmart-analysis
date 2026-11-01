"""Database helpers: read-only connections, filter sessions and SQL file runner.

Every analysis query in sql/queries/ reads from three TEMP tables that this
module creates for the chosen filters:

    customers_f  customers matching the city / channel filter
    orders_cc    all orders of those customers          (full history - needed for
                 cohorts, repeat-rate, RFM, LTV which look across time)
    orders_f     orders_cc restricted to the date range (for KPI-style views)
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "quickcart.db"
QUERY_DIR = ROOT / "sql" / "queries"

QUERY_NAMES = [p.stem for p in sorted(QUERY_DIR.glob("*.sql"))]


def connect(readonly: bool = True, db_path: Path = DB_PATH) -> sqlite3.Connection:
    if readonly:
        return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(db_path)


def _in_clause(column: str, values: Iterable[str] | None) -> tuple[str, list]:
    values = list(values or [])
    if not values:
        return "1=1", []
    return f"{column} IN ({','.join('?' * len(values))})", values


def prepare_session(conn: sqlite3.Connection, cities: Iterable[str] | None = None,
                    channels: Iterable[str] | None = None, start: str | None = None,
                    end: str | None = None) -> None:
    """Create the filtered TEMP tables. Values are always bound parameters."""
    city_sql, city_p = _in_clause("city", cities)
    chan_sql, chan_p = _in_clause("acquisition_channel", channels)
    for t in ("customers_f", "orders_cc", "orders_f"):
        conn.execute(f"DROP TABLE IF EXISTS temp.{t}")
    conn.execute(f"CREATE TEMP TABLE customers_f AS SELECT * FROM customers WHERE {city_sql} AND {chan_sql}",
                 city_p + chan_p)
    conn.execute("CREATE TEMP TABLE orders_cc AS SELECT o.* FROM orders o "
                 "JOIN customers_f c ON c.customer_id = o.customer_id")
    lo = start or "0000-01-01"
    hi = end or "9999-12-31"
    conn.execute("CREATE TEMP TABLE orders_f AS SELECT * FROM orders_cc WHERE order_date BETWEEN ? AND ?",
                 (lo, hi))
    conn.execute("CREATE INDEX temp.ix_cc_customer ON orders_cc(customer_id, order_ts)")


@contextmanager
def session(cities=None, channels=None, start=None, end=None) -> Iterator[sqlite3.Connection]:
    conn = connect(readonly=True)
    try:
        prepare_session(conn, cities, channels, start, end)
        yield conn
    finally:
        conn.close()


def query_text(name: str) -> str:
    return (QUERY_DIR / f"{name}.sql").read_text()


def run_query(conn: sqlite3.Connection, name: str) -> pd.DataFrame:
    return pd.read_sql_query(query_text(name), conn)


def run_custom_select(conn: sqlite3.Connection, sql: str, max_rows: int = 1000,
                      max_steps: int = 3000) -> pd.DataFrame:
    """Run a user-typed read-only query with guard rails (used by the SQL Lab tab)."""
    stripped = sql.strip().rstrip(";")
    if not stripped.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT / WITH queries are allowed.")
    if ";" in stripped:
        raise ValueError("Please run one statement at a time.")
    conn.execute("PRAGMA query_only = ON")
    steps = {"n": 0}

    def _guard() -> int:                       # abort runaway queries
        steps["n"] += 1
        return 1 if steps["n"] > max_steps else 0

    conn.set_progress_handler(_guard, 10_000)
    try:
        cur = conn.execute(stripped)
        rows = cur.fetchmany(max_rows)
        return pd.DataFrame(rows, columns=[c[0] for c in cur.description])
    finally:
        conn.set_progress_handler(None, 0)
