"""Turn query results into plain-English findings (numbers are computed, never hard-coded)."""
from __future__ import annotations

import pandas as pd


def inr(x: float) -> str:
    if x >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.1f} L"
    return f"₹{x:,.0f}"


def retention_at(cohort: pd.DataFrame, idx: int) -> float:
    """Customer-weighted retention at month `idx` across cohorts that have reached it."""
    ok = cohort[cohort.month_idx == idx]
    return 100 * ok.retained.sum() / ok.cohort_size.sum()


def build(results: dict[str, pd.DataFrame], churn: dict) -> dict[str, str]:
    k, coh, dv = results["kpi_monthly"], results["cohort_retention"], results["delivery_vs_repeat"]
    disc, ch, cat = results["discount_analysis"], results["channel_ltv"], results["category_performance"]
    rfm, city = results["rfm_segments"], results["city_performance"]
    cm = churn["metrics"]
    m = cm[cm["selected_model"]]

    out: dict[str, str] = {}
    out["scale"] = (f"{int(k.delivered_orders.sum()):,} delivered orders, {inr(k.revenue.sum())} net revenue, "
                    f"{rfm.shape[0]:,} purchasing customers, AOV {inr(k.revenue.sum() / k.delivered_orders.sum())}, "
                    f"gross margin {100 * k.gross_profit.sum() / k.revenue.sum():.1f}%")
    first, last = k.iloc[0], k.iloc[-1]
    out["growth"] = (f"Monthly revenue grew from {inr(first.revenue)} ({first.month}) to {inr(last.revenue)} "
                     f"({last.month}).")
    diwali = k[k.month == "2025-10"]
    if not diwali.empty and pd.notna(diwali.iloc[0].revenue_mom_pct):
        out["festive"] = (f"October 2025 (Diwali) revenue rose {diwali.iloc[0].revenue_mom_pct:.0f}% month-on-month "
                          f"with AOV at {inr(diwali.iloc[0].aov)}.")
    out["retention"] = (f"Customer-weighted retention: {retention_at(coh, 1):.1f}% in month 1, "
                        f"{retention_at(coh, 3):.1f}% in month 3, {retention_at(coh, 6):.1f}% in month 6.")
    in_time = dv[dv.delivery_bucket.str[0].isin(list("123"))]
    late = dv[dv.delivery_bucket.str[0].isin(list("45"))]
    w = lambda d: (d.orders * d.repeat_within_30d_pct).sum() / d.orders.sum()   # noqa: E731
    out["delivery"] = (f"Orders delivered within 20 min had a {w(in_time):.0f}% 30-day repeat rate vs "
                       f"{w(late):.0f}% when slower - a {w(in_time) - w(late):.0f} pp drop "
                       f"({100 * late.orders.sum() / dv.orders.sum():.0f}% of orders were slower than 20 min).")
    d0, dmax = disc.iloc[0], disc.iloc[-1]
    verdict = ("deeper discounts did not buy more repeat orders"
               if dmax.repeat_within_30d_pct <= d0.repeat_within_30d_pct else "deeper discounts lifted repeat orders")
    out["discount"] = (f"Gross margin falls from {d0.gross_margin_pct:.1f}% at 0% discount to "
                       f"{dmax.gross_margin_pct:.1f}% at {int(dmax.discount_pct)}%; 30-day repeat rate is "
                       f"{d0.repeat_within_30d_pct:.0f}% vs {dmax.repeat_within_30d_pct:.0f}% - {verdict}.")
    valid = ch.dropna(subset=["ltv90_to_cac"])
    best, worst = valid.iloc[valid.ltv90_to_cac.argmax()], valid.iloc[valid.ltv90_to_cac.argmin()]
    out["channel"] = (f"{best.channel} has the best 90-day LTV:CAC ({best.ltv90_to_cac:.2f}x); "
                      f"{worst.channel} the worst ({worst.ltv90_to_cac:.2f}x).")
    seg = rfm.groupby("segment").agg(customers=("customer_id", "size"), revenue=("monetary", "sum"))
    seg["cust_pct"] = 100 * seg.customers / seg.customers.sum()
    seg["rev_pct"] = 100 * seg.revenue / seg.revenue.sum()
    champ = seg.loc["Champions"]
    out["rfm"] = (f"'Champions' are {champ.cust_pct:.0f}% of customers but {champ.rev_pct:.0f}% of revenue.")
    if "At Risk (High Value)" in seg.index:
        ar = seg.loc["At Risk (High Value)"]
        out["at_risk"] = (f"{int(ar.customers):,} high-value customers are drifting away "
                          f"({inr(ar.revenue)} lifetime revenue).")
    top = cat.iloc[0]
    hi = cat.loc[cat.margin_pct.idxmax()]
    out["category"] = (f"{top.category} leads GMV ({top.gmv_share_pct:.0f}% share, {top.margin_pct:.0f}% margin); "
                       f"{hi.category} has the best margin ({hi.margin_pct:.0f}%).")
    out["city"] = (f"{city.iloc[0].city} is the largest city by revenue; "
                   f"{city.loc[city.avg_delivery_min.idxmax()].city} is the slowest "
                   f"({city.avg_delivery_min.max():.1f} min avg delivery).")
    name = cm["selected_model"].replace("_", " ")
    out["churn"] = (f"Best model ({name}) scores ROC-AUC {m['roc_auc']} on a later, unseen time window; the 10% of "
                    f"customers flagged riskiest actually churned {100 * m['top_decile_churn_rate']:.0f}% of the time "
                    f"vs {100 * m['churn_base_rate']:.0f}% overall (logistic {cm['logistic_regression']['roc_auc']} "
                    f"vs gradient boosting {cm['gradient_boosting']['roc_auc']} AUC).")
    return out


def to_markdown(findings: dict[str, str]) -> str:
    lines = ["# Key findings (auto-generated from the data)", ""]
    lines += [f"- **{k.replace('_', ' ').title()}** - {v}" for k, v in findings.items()]
    return "\n".join(lines) + "\n"
