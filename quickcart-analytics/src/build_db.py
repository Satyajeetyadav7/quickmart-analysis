"""Load the raw CSVs into a SQLite database and run data-quality checks.

Run:  python -m src.build_db
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "quickcart.db"
SCHEMA = ROOT / "sql" / "schema.sql"

# Illustrative assumptions (INR per acquired customer) used for LTV:CAC analysis.
CHANNEL_CAC = {"Organic": 0, "Referral": 120, "Google Ads": 260, "Paid Social": 210, "Influencer": 310}

LOAD_ORDER = ["customers", "products", "orders", "order_items"]


def data_quality_checks(conn: sqlite3.Connection) -> dict[str, int]:
    """Each check returns the number of offending rows; all should be 0."""
    q = {
        "orphan_orders (no customer)": "SELECT COUNT(*) FROM orders o LEFT JOIN customers c USING(customer_id) WHERE c.customer_id IS NULL",
        "orphan_items (no order)": "SELECT COUNT(*) FROM order_items i LEFT JOIN orders o USING(order_id) WHERE o.order_id IS NULL",
        "orphan_items (no product)": "SELECT COUNT(*) FROM order_items i LEFT JOIN products p USING(product_id) WHERE p.product_id IS NULL",
        "orders before signup": "SELECT COUNT(*) FROM orders o JOIN customers c USING(customer_id) WHERE o.order_date < c.signup_date",
        "negative / zero values": "SELECT COUNT(*) FROM orders WHERE net_revenue <= 0 OR gross_value <= 0 OR delivery_minutes <= 0",
        "invalid status": "SELECT COUNT(*) FROM orders WHERE status NOT IN ('delivered','cancelled')",
        "rating on cancelled order": "SELECT COUNT(*) FROM orders WHERE status='cancelled' AND rating IS NOT NULL",
        "order total mismatch": "SELECT COUNT(*) FROM orders WHERE ABS(net_revenue - (gross_value - discount_amount + delivery_fee)) > 0.02",
    }
    results = {name: conn.execute(sql).fetchone()[0] for name, sql in q.items()}
    for name, n in results.items():
        print(f"  [{'OK' if n == 0 else 'FAIL'}] {name}: {n}")
    return results


def build(db_path: Path = DB_PATH, raw_dir: Path = RAW_DIR) -> Path:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())
    for table in LOAD_ORDER:
        df = pd.read_csv(raw_dir / f"{table}.csv")
        df.to_sql(table, conn, if_exists="append", index=False)
        print(f"[build_db] loaded {table:<12} {len(df):>8,} rows")
    conn.executemany("INSERT INTO channel_cac VALUES (?, ?)", list(CHANNEL_CAC.items()))
    conn.commit()
    print("[build_db] data-quality checks")
    checks = data_quality_checks(conn)
    conn.execute("ANALYZE")
    conn.close()
    assert all(v == 0 for v in checks.values()), "Data-quality checks failed"
    return db_path


if __name__ == "__main__":
    build()
