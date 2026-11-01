"""End-to-end pipeline: generate data -> build SQLite DB -> run every SQL query -> churn model -> insights.

Run:  python -m src.run_pipeline
"""
from __future__ import annotations

import time
from pathlib import Path

from . import build_db, churn_model, db, generate_data, insights

OUT = Path(__file__).resolve().parents[1] / "outputs"


def main() -> None:
    t0 = time.time()
    generate_data.main()
    build_db.build()

    (OUT / "query_results").mkdir(parents=True, exist_ok=True)
    results = {}
    with db.session() as conn:                       # no filters = whole business
        for name in db.QUERY_NAMES:
            df = db.run_query(conn, name)
            df.to_csv(OUT / "query_results" / f"{name}.csv", index=False)
            results[name] = df
            print(f"[sql] {name:<22} -> {len(df):>6,} rows")

    churn = churn_model.run()
    findings = insights.build(results, churn)
    (OUT / "insights.md").write_text(insights.to_markdown(findings))
    print("\n" + insights.to_markdown(findings))
    print(f"Pipeline finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
