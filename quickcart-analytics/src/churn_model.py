"""Customer churn model: "will this customer order again in the next 60 days?"

Design choices worth explaining in an interview:
  * Population = customers active in the last 90 days (already-lost customers are excluded).
  * Features are built as of a SNAPSHOT date using only data on or before it (no leakage).
  * Label = delivered order in the 60 days AFTER the snapshot.
  * OUT-OF-TIME validation: train on the 2026-06-30 snapshot, test on the 2026-08-31 snapshot.
  * Baseline (logistic regression) vs gradient boosting; AUC, PR-AUC and top-decile lift reported.
  * Final model is refit on both snapshots and used to score customers as of the latest date.

Run:  python -m src.churn_model
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import db

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"

HORIZON_DAYS = 60
ACTIVE_WINDOW_DAYS = 90   # population = customers who ordered in the last 90 days
TRAIN_SNAPSHOT = "2026-06-30"
TEST_SNAPSHOT = "2026-08-31"
SCORE_SNAPSHOT = "2026-10-31"
LATE_MIN = 20

CAT_COLS = ["city_tier", "acquisition_channel", "device", "age_group"]
NUM_COLS = ["frequency", "monetary", "aov", "avg_delivery_min", "late_share", "avg_discount_pct",
            "avg_rating", "orders_last_30d", "orders_last_90d", "cancel_rate", "recency_days",
            "avg_gap_days", "tenure_days", "recency_vs_gap"]

FEATURE_LABELS = {
    "frequency": "Order count", "monetary": "Lifetime spend", "aov": "Avg order value",
    "avg_delivery_min": "Avg delivery time", "late_share": "Share of late deliveries",
    "avg_discount_pct": "Avg discount used", "avg_rating": "Avg rating given",
    "orders_last_30d": "Orders in last 30d", "orders_last_90d": "Orders in last 90d",
    "cancel_rate": "Cancellation rate", "recency_days": "Days since last order",
    "avg_gap_days": "Avg days between orders", "tenure_days": "Customer tenure (days)",
    "recency_vs_gap": "Recency / usual gap",
}


def load_frames(conn) -> tuple[pd.DataFrame, pd.DataFrame]:
    orders = pd.read_sql_query(
        "SELECT order_id, customer_id, order_date, delivery_minutes, discount_pct, net_revenue, status, rating "
        "FROM orders", conn, parse_dates=["order_date"])
    customers = pd.read_sql_query("SELECT * FROM customers", conn, parse_dates=["signup_date"])
    return orders, customers


def build_features(orders: pd.DataFrame, customers: pd.DataFrame, asof: str) -> pd.DataFrame:
    """One row per customer with >= 1 delivered order on/before `asof`."""
    asof_ts = pd.Timestamp(asof)
    o = orders[orders.order_date <= asof_ts].copy()
    o["is_cancel"] = (o.status == "cancelled").astype(float)
    cancel_rate = o.groupby("customer_id").is_cancel.mean().rename("cancel_rate")

    d = o[o.status == "delivered"].copy()
    d["is_late"] = (d.delivery_minutes > LATE_MIN).astype(float)
    days_ago = (asof_ts - d.order_date).dt.days
    d["in30"] = (days_ago <= 30).astype(int)
    d["in90"] = (days_ago <= 90).astype(int)

    g = d.groupby("customer_id")
    f = pd.DataFrame({
        "frequency": g.size(),
        "monetary": g.net_revenue.sum(),
        "aov": g.net_revenue.mean(),
        "first_order": g.order_date.min(),
        "last_order": g.order_date.max(),
        "avg_delivery_min": g.delivery_minutes.mean(),
        "late_share": g.is_late.mean(),
        "avg_discount_pct": g.discount_pct.mean(),
        "avg_rating": g.rating.mean(),
        "orders_last_30d": g.in30.sum(),
        "orders_last_90d": g.in90.sum(),
    }).join(cancel_rate).reset_index()

    f["recency_days"] = (asof_ts - f.last_order).dt.days
    span = (f.last_order - f.first_order).dt.days
    f = f.merge(customers[["customer_id", "signup_date", "city", *CAT_COLS]], on="customer_id", how="left")
    f["tenure_days"] = (asof_ts - f.signup_date).dt.days
    f["avg_gap_days"] = np.where(f.frequency > 1, span / (f.frequency - 1).clip(lower=1), np.nan)
    f["avg_gap_days"] = f.avg_gap_days.fillna(f.tenure_days.clip(lower=1))
    f["avg_rating"] = f.avg_rating.fillna(f.avg_rating.median())
    f["recency_vs_gap"] = f.recency_days / f.avg_gap_days.clip(lower=1)
    # Score only customers still "in play". Customers silent for 90+ days are already lost,
    # and including them would make the problem trivially easy (inflated AUC).
    return f[f.recency_days <= ACTIVE_WINDOW_DAYS].reset_index(drop=True)


def make_labels(orders: pd.DataFrame, feats: pd.DataFrame, asof: str) -> pd.Series:
    asof_ts = pd.Timestamp(asof)
    end = asof_ts + pd.Timedelta(days=HORIZON_DAYS)
    w = orders[(orders.status == "delivered") & (orders.order_date > asof_ts) & (orders.order_date <= end)]
    return feats.customer_id.isin(set(w.customer_id)).astype(int)


def to_matrix(f: pd.DataFrame, columns=None) -> pd.DataFrame:
    X = pd.concat([f[NUM_COLS].reset_index(drop=True),
                   pd.get_dummies(f[CAT_COLS], dtype=float).reset_index(drop=True)], axis=1)
    return X.reindex(columns=columns, fill_value=0.0) if columns is not None else X


def _lr():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))


def _gb() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250,
                                          l2_regularization=1.0, random_state=42)


def _evaluate(y_true: np.ndarray, p_reorder: np.ndarray) -> dict:
    churn = 1 - y_true
    risk = 1 - p_reorder
    top = np.argsort(-risk)[: max(1, len(risk) // 10)]
    return {
        "roc_auc": round(float(roc_auc_score(y_true, p_reorder)), 3),
        "pr_auc": round(float(average_precision_score(churn, risk)), 3),
        "churn_base_rate": round(float(churn.mean()), 3),
        "top_decile_churn_rate": round(float(churn[top].mean()), 3),
        "top_decile_lift": round(float(churn[top].mean() / churn.mean()), 2),
    }


def run(conn=None, write: bool = True) -> dict:
    own = conn is None
    conn = conn or db.connect()
    try:
        orders, customers = load_frames(conn)
    finally:
        if own:
            conn.close()

    f_tr = build_features(orders, customers, TRAIN_SNAPSHOT)
    f_te = build_features(orders, customers, TEST_SNAPSHOT)
    y_tr = make_labels(orders, f_tr, TRAIN_SNAPSHOT).values
    y_te = make_labels(orders, f_te, TEST_SNAPSHOT).values
    X_tr = to_matrix(f_tr)
    X_te = to_matrix(f_te, X_tr.columns)

    factories = {"logistic_regression": _lr, "gradient_boosting": _gb}
    fitted = {name: make().fit(X_tr, y_tr) for name, make in factories.items()}
    metrics_by_model = {name: _evaluate(y_te, mdl.predict_proba(X_te)[:, 1]) for name, mdl in fitted.items()}
    m_lr, m_gb = metrics_by_model["logistic_regression"], metrics_by_model["gradient_boosting"]

    # Keep the model that generalises best out-of-time (a simpler model winning is a perfectly good outcome)
    selected = max(metrics_by_model, key=lambda n: metrics_by_model[n]["roc_auc"])
    imp = permutation_importance(fitted[selected], X_te, y_te, scoring="roc_auc", n_repeats=5, random_state=42)
    importance = (pd.DataFrame({"feature": X_te.columns, "importance": imp.importances_mean})
                  .assign(label=lambda d: d.feature.map(FEATURE_LABELS).fillna(d.feature))
                  .sort_values("importance", ascending=False).reset_index(drop=True))

    # Final model: refit on both snapshots, score today's customers
    final = factories[selected]().fit(pd.concat([X_tr, X_te], ignore_index=True), np.concatenate([y_tr, y_te]))
    f_sc = build_features(orders, customers, SCORE_SNAPSHOT)
    p = final.predict_proba(to_matrix(f_sc, X_tr.columns))[:, 1]
    scores = f_sc[["customer_id", "city", "acquisition_channel", "frequency", "monetary", "recency_days",
                   "avg_delivery_min", "late_share"]].copy()
    scores["churn_risk"] = (1 - p).round(3)
    scores["monetary"] = scores.monetary.round(0)
    scores["avg_delivery_min"] = scores.avg_delivery_min.round(1)
    scores["late_share"] = scores.late_share.round(2)

    metrics = {
        "horizon_days": HORIZON_DAYS, "train_snapshot": TRAIN_SNAPSHOT, "test_snapshot": TEST_SNAPSHOT,
        "score_snapshot": SCORE_SNAPSHOT, "n_train": int(len(y_tr)), "n_test": int(len(y_te)),
        "selected_model": selected, "logistic_regression": m_lr, "gradient_boosting": m_gb,
    }
    if write:
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "churn_metrics.json").write_text(json.dumps(metrics, indent=2))
        importance.to_csv(OUT_DIR / "churn_feature_importance.csv", index=False)
        scores.to_csv(OUT_DIR / "churn_scores.csv", index=False)
        print(f"[churn_model] out-of-time AUC  logreg={m_lr['roc_auc']}  gradient-boosting={m_gb['roc_auc']}  "
              f"-> selected {selected}")
    return {"metrics": metrics, "importance": importance, "scores": scores}


if __name__ == "__main__":
    run()
