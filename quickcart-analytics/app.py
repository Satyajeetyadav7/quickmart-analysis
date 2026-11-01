"""QuickCart Analytics - interactive dashboard (Streamlit).

Every number on this page comes from a SQL query in sql/queries/ run against a SQLite
database (data/quickcart.db). Sidebar filters re-run those queries live.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from src import churn_model, db
from src.insights import inr

st.set_page_config(page_title="QuickCart Analytics", page_icon="🛒", layout="wide")

# ---- palette (validated; see README) --------------------------------------------------------
BLUE, ORANGE = "#2a78d6", "#eb6834"
SEQ_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
GRID = "rgba(137,135,129,0.25)"
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

SEGMENT_ORDER = ["Champions", "Loyal", "Potential Loyalist", "New / Promising",
                 "Needs Attention", "At Risk (High Value)", "Hibernating"]
SEGMENT_PLAYBOOK = {
    "Champions": "Reward early access and referral bonuses; do not discount - they already buy.",
    "Loyal": "Upsell into higher-margin categories (Personal Care, Snacks) with basket nudges.",
    "Potential Loyalist": "Push a second and third order within 14 days to build the habit.",
    "New / Promising": "Fast, reliable first deliveries; light-touch welcome journey.",
    "Needs Attention": "Reminder at their usual ordering gap with a small, targeted offer.",
    "At Risk (High Value)": "Highest-priority win-back: personalised offer + service-recovery message.",
    "Hibernating": "Low-cost reactivation only (push / WhatsApp); cap spend per customer.",
}


# ---- data access ----------------------------------------------------------------------------
@st.cache_resource(show_spinner="Building the database for the first time...")
def ensure_db() -> bool:
    if not db.DB_PATH.exists():
        from src import build_db, generate_data
        generate_data.main()
        build_db.build()
    return True


ensure_db()


@st.cache_data(show_spinner=False)
def filter_options() -> dict:
    with db.connect() as conn:
        lo, hi = conn.execute("SELECT MIN(order_date), MAX(order_date) FROM orders").fetchone()
        cities = [r[0] for r in conn.execute("SELECT DISTINCT city FROM customers ORDER BY 1")]
        channels = [r[0] for r in conn.execute("SELECT DISTINCT acquisition_channel FROM customers ORDER BY 1")]
    return {"lo": date.fromisoformat(lo), "hi": date.fromisoformat(hi), "cities": cities, "channels": channels}


@st.cache_data(show_spinner=False)
def run_named(name: str, cities: tuple, channels: tuple, start: str, end: str) -> pd.DataFrame:
    with db.session(cities, channels, start, end) as conn:
        return db.run_query(conn, name)


@st.cache_data(show_spinner="Training churn model...")
def churn_results() -> dict:
    out = db.ROOT / "outputs"
    needed = [out / "churn_metrics.json", out / "churn_scores.csv", out / "churn_feature_importance.csv"]
    if all(p.exists() for p in needed):
        return {"metrics": json.loads(needed[0].read_text()), "scores": pd.read_csv(needed[1]),
                "importance": pd.read_csv(needed[2])}
    return churn_model.run(write=False)


def style(fig, height: int = 320, grid_axis: str = "y"):
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=48, b=8), showlegend=False,
                      title=dict(x=0, font=dict(size=15)), hoverlabel=dict(font_size=12))
    fig.update_xaxes(showgrid=grid_axis == "x", gridcolor=GRID, zeroline=False, title_text=None)
    fig.update_yaxes(showgrid=grid_axis == "y", gridcolor=GRID, zeroline=False, title_text=None)
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch")


# ---- sidebar filters ------------------------------------------------------------------------
opt = filter_options()
st.sidebar.title("Filters")
picked = st.sidebar.date_input("Order date range", value=(opt["lo"], opt["hi"]),
                               min_value=opt["lo"], max_value=opt["hi"])
if not (isinstance(picked, tuple) and len(picked) == 2):
    st.info("Pick an end date to apply the range.")
    st.stop()
start, end = picked[0].isoformat(), picked[1].isoformat()
sel_cities = st.sidebar.multiselect("City", opt["cities"], default=opt["cities"])
sel_channels = st.sidebar.multiselect("Acquisition channel", opt["channels"], default=opt["channels"])
if not sel_cities or not sel_channels:
    st.warning("Select at least one city and one channel.")
    st.stop()
cities = tuple(sel_cities) if len(sel_cities) < len(opt["cities"]) else ()
channels = tuple(sel_channels) if len(sel_channels) < len(opt["channels"]) else ()
st.sidebar.caption("The date range drives the Overview, category, city and demand views. Cohorts, RFM, "
                   "repeat-rate, LTV and churn need each customer's full history, so they respond to the "
                   "city and channel filters only.")
st.sidebar.divider()
st.sidebar.caption("Data is **simulated** (see `src/generate_data.py`). It models quick-commerce behaviour "
                   "but is not from a real company.")


def q(name: str) -> pd.DataFrame:
    return run_named(name, cities, channels, start, end)


# ---- header ---------------------------------------------------------------------------------
st.title("QuickCart: Sales, Retention & Churn Analytics")
st.caption("Quick-commerce analytics on 9,000 customers and ~45,000 orders (Jan 2025 - Oct 2026). "
           "Python + SQL (SQLite) + scikit-learn + Streamlit.")

kpi = q("kpi_monthly")
if kpi.empty:
    st.warning("No orders match these filters.")
    st.stop()

tab_ov, tab_ret, tab_seg, tab_ops, tab_price, tab_churn, tab_sql = st.tabs(
    ["Overview", "Retention", "Customer segments", "Operations", "Pricing & discounts", "Churn model", "SQL lab"])

# ============================== OVERVIEW ======================================================
with tab_ov:
    rev, orders_n = kpi.revenue.sum(), kpi.delivered_orders.sum()
    last = kpi.iloc[-1]
    prev = kpi.iloc[-2] if len(kpi) > 1 else None
    c = st.columns(5)
    c[0].metric("Net revenue", inr(rev), f"{last.revenue_mom_pct:+.1f}% vs prev. month" if prev is not None and pd.notna(last.revenue_mom_pct) else None)
    c[1].metric("Delivered orders", f"{int(orders_n):,}",
                f"{100 * (last.delivered_orders / prev.delivered_orders - 1):+.1f}% vs prev. month" if prev is not None else None)
    c[2].metric("Avg order value", inr(rev / orders_n))
    c[3].metric("Gross margin", f"{100 * kpi.gross_profit.sum() / rev:.1f}%")
    c[4].metric("Active customers (latest month)", f"{int(last.active_customers):,}")

    l, r = st.columns(2)
    with l:
        fig = px.bar(kpi, x="month", y="revenue", title="Net revenue by month (INR)", color_discrete_sequence=[BLUE])
        fig.update_traces(hovertemplate="%{x}<br>₹%{y:,.0f}<extra></extra>")
        show(style(fig))
    with r:
        fig = px.line(kpi, x="month", y="gross_margin_pct", markers=True, title="Gross margin % by month",
                      color_discrete_sequence=[BLUE])
        fig.update_traces(line_width=2, marker_size=8, hovertemplate="%{x}<br>%{y:.1f}%<extra></extra>")
        fig.update_yaxes(ticksuffix="%")
        show(style(fig))

    cat = q("category_performance")
    l, r = st.columns(2)
    order = cat.sort_values("gmv").category.tolist()
    with l:
        fig = px.bar(cat, x="gmv_share_pct", y="category", orientation="h", text="gmv_share_pct",
                     title="Share of GMV by category (%)", color_discrete_sequence=[BLUE],
                     category_orders={"category": order})
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False)
        show(style(fig, 380, "x"))
    with r:
        fig = px.bar(cat, x="margin_pct", y="category", orientation="h", text="margin_pct",
                     title="Gross margin by category (%)", color_discrete_sequence=[BLUE],
                     category_orders={"category": order})
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False)
        show(style(fig, 380, "x"))
    top, best = cat.iloc[0], cat.loc[cat.margin_pct.idxmax()]
    st.info(f"**{top.category}** is the biggest category ({top.gmv_share_pct:.0f}% of GMV) but earns only "
            f"{top.margin_pct:.0f}% margin, while **{best.category}** earns {best.margin_pct:.0f}%. "
            f"Steering baskets toward high-margin categories is a cheaper lever than discounting.")

    st.subheader("City scorecard")
    city = q("city_performance")
    st.dataframe(city, hide_index=True, width="stretch", column_config={
        "city": "City", "city_tier": "Tier", "active_customers": st.column_config.NumberColumn("Customers", format="%d"),
        "delivered_orders": st.column_config.NumberColumn("Orders", format="%d"),
        "revenue": st.column_config.NumberColumn("Revenue", format="₹%d"),
        "aov": st.column_config.NumberColumn("AOV", format="₹%.0f"),
        "avg_delivery_min": st.column_config.NumberColumn("Avg delivery (min)", format="%.1f"),
        "late_delivery_pct": st.column_config.ProgressColumn("Late > 20 min (%)", min_value=0, max_value=100, format="%.1f%%"),
        "cancel_rate_pct": st.column_config.NumberColumn("Cancel rate (%)", format="%.1f"),
        "avg_rating": st.column_config.NumberColumn("Rating", format="%.2f"),
    })

# ============================== RETENTION =====================================================
with tab_ret:
    coh = q("cohort_retention")
    if coh.empty:
        st.warning("No cohort data for these filters.")
    else:
        def wret(i: int) -> float:
            ok = coh[coh.month_idx == i]
            return 100 * ok.retained.sum() / ok.cohort_size.sum() if len(ok) else float("nan")

        c = st.columns(4)
        c[0].metric("Month-1 retention", f"{wret(1):.1f}%")
        c[1].metric("Month-3 retention", f"{wret(3):.1f}%")
        c[2].metric("Month-6 retention", f"{wret(6):.1f}%")
        c[3].metric("Cohorts tracked", f"{coh.cohort_month.nunique()}")

        pivot = coh[coh.month_idx <= 12].pivot(index="cohort_month", columns="month_idx", values="retention_pct")
        fig = px.imshow(pivot, text_auto=".0f", aspect="auto", color_continuous_scale=SEQ_BLUES,
                        labels=dict(x="Months since first order", y="Cohort (first-order month)", color="Retained %"),
                        title="Cohort retention heatmap (% of cohort still ordering)")
        fig.update_layout(height=520, margin=dict(l=8, r=8, t=48, b=8), title=dict(x=0, font=dict(size=15)),
                          coloraxis_colorbar=dict(ticksuffix="%", len=0.8))
        fig.update_xaxes(side="top")
        show(fig)

        curve = pd.DataFrame({"month_idx": range(0, 13), "retention_pct": [wret(i) for i in range(0, 13)]}).dropna()
        fig = px.line(curve, x="month_idx", y="retention_pct", markers=True,
                      title="Average retention curve (customer-weighted)", color_discrete_sequence=[BLUE])
        fig.update_traces(line_width=2, marker_size=8, hovertemplate="Month %{x}<br>%{y:.1f}%<extra></extra>")
        fig.update_yaxes(ticksuffix="%", range=[0, 105])
        fig.update_xaxes(dtick=1)
        show(style(fig, 300))
        st.info(f"Only **{wret(1):.0f}%** of new customers order again the next month and **{wret(6):.0f}%** are "
                f"still active after six months. The biggest drop is between month 0 and 1, so the first 30 days "
                f"are where retention work pays off most.")

# ============================== SEGMENTS ======================================================
with tab_seg:
    rfm = q("rfm_segments")
    if rfm.empty:
        st.warning("No customers for these filters.")
    else:
        seg = (rfm.groupby("segment").agg(customers=("customer_id", "size"), revenue=("monetary", "sum"),
                                          avg_recency_days=("recency_days", "mean"),
                                          avg_orders=("frequency", "mean")).reset_index())
        seg["Customers (%)"] = 100 * seg.customers / seg.customers.sum()
        seg["Revenue (%)"] = 100 * seg.revenue / seg.revenue.sum()
        seg["segment"] = pd.Categorical(seg.segment, SEGMENT_ORDER, ordered=True)
        seg = seg.sort_values("segment")

        long = seg.melt(id_vars="segment", value_vars=["Customers (%)", "Revenue (%)"], var_name="Measure", value_name="pct")
        fig = px.bar(long, x="pct", y="segment", color="Measure", barmode="group", orientation="h", text="pct",
                     title="Share of customers vs share of revenue, by RFM segment",
                     color_discrete_map={"Customers (%)": BLUE, "Revenue (%)": ORANGE},
                     category_orders={"segment": SEGMENT_ORDER[::-1], "Measure": ["Customers (%)", "Revenue (%)"]})
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False)
        style(fig, 440, "x").update_layout(showlegend=True, legend=dict(orientation="h", y=1.08, x=0, title_text=""))
        show(fig)

        champ = seg[seg.segment == "Champions"].iloc[0]
        st.info(f"**Champions are {champ['Customers (%)']:.0f}% of customers but {champ['Revenue (%)']:.0f}% of revenue.** "
                "Protecting them (and winning back the at-risk high-value group) matters more than broad promotions.")

        table = seg.assign(segment=seg.segment.astype(str))[["segment", "customers", "Customers (%)", "Revenue (%)",
                                                              "avg_recency_days", "avg_orders"]]
        table["Recommended action"] = table.segment.map(SEGMENT_PLAYBOOK)
        st.dataframe(table, hide_index=True, width="stretch", column_config={
            "segment": "Segment", "customers": st.column_config.NumberColumn("Customers", format="%d"),
            "Customers (%)": st.column_config.NumberColumn(format="%.1f"), "Revenue (%)": st.column_config.NumberColumn(format="%.1f"),
            "avg_recency_days": st.column_config.NumberColumn("Avg days since order", format="%.0f"),
            "avg_orders": st.column_config.NumberColumn("Avg orders", format="%.1f")})
        st.download_button("Download customer-level RFM list (CSV)", rfm.to_csv(index=False).encode(),
                           "rfm_segments.csv", "text/csv")

        st.subheader("Which acquisition channel pays back?")
        ltv = q("channel_ltv")
        paid = ltv.dropna(subset=["ltv90_to_cac"]).sort_values("ltv90_to_cac")
        if not paid.empty:
            fig = px.bar(paid, x="ltv90_to_cac", y="channel", orientation="h", text="ltv90_to_cac",
                         title="90-day gross profit per customer / acquisition cost (paid channels)",
                         color_discrete_sequence=[BLUE])
            fig.update_traces(texttemplate="%{text:.2f}x", textposition="outside", cliponaxis=False)
            fig.add_vline(x=1, line_dash="dash", line_color="#898781", annotation_text="break-even (1x)",
                          annotation_position="top")
            show(style(fig, 300, "x"))
        st.dataframe(ltv, hide_index=True, width="stretch", column_config={
            "channel": "Channel", "customers": st.column_config.NumberColumn("Customers", format="%d"),
            "avg_orders_90d": st.column_config.NumberColumn("Orders in 90d", format="%.2f"),
            "avg_gross_profit_90d": st.column_config.NumberColumn("90d gross profit", format="₹%d"),
            "retained_after_day30_pct": st.column_config.NumberColumn("Active after day 30 (%)", format="%.1f"),
            "cac_inr": st.column_config.NumberColumn("Assumed CAC", format="₹%d"),
            "ltv90_to_cac": st.column_config.NumberColumn("LTV:CAC", format="%.2fx")})
        st.caption("CAC values are illustrative assumptions (table `channel_cac`); organic has no paid CAC. "
                   "Gross profit is before delivery and dark-store costs.")

# ============================== OPERATIONS ====================================================
with tab_ops:
    dv = q("delivery_vs_repeat")
    if dv.empty:
        st.warning("Not enough data for these filters.")
    else:
        fig = px.bar(dv, x="delivery_bucket", y="repeat_within_30d_pct", text="repeat_within_30d_pct",
                     title="Chance a customer orders again within 30 days, by delivery time of the order",
                     color_discrete_sequence=[BLUE])
        fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside", cliponaxis=False,
                          hovertemplate="%{x}<br>%{y:.1f}% repeat<br>%{customdata:,} orders<extra></extra>",
                          customdata=dv.orders)
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        show(style(fig, 340))
        fast = dv[dv.delivery_bucket.str[0].isin(list("123"))]
        slow = dv[dv.delivery_bucket.str[0].isin(list("45"))]
        wfast = (fast.orders * fast.repeat_within_30d_pct).sum() / max(fast.orders.sum(), 1)
        wslow = (slow.orders * slow.repeat_within_30d_pct).sum() / max(slow.orders.sum(), 1)
        st.info(f"Repeat rate is **{wfast:.0f}%** after a delivery under 20 minutes but **{wslow:.0f}%** after a slower one "
                f"(a {wfast - wslow:.0f} pp drop). Orders in the last 30 days of data are excluded so every order has "
                f"a full 30-day window to repeat in.")

    hh = q("hourly_demand")
    if not hh.empty:
        grid = hh.pivot(index="dow", columns="hour", values="orders").reindex(range(7)).reindex(columns=range(24)).fillna(0)
        grid.index = DOW
        fig = px.imshow(grid, aspect="auto", color_continuous_scale=SEQ_BLUES,
                        labels=dict(x="Hour of day", y="", color="Orders"), title="When do customers order? (orders by weekday and hour)")
        fig.update_layout(height=340, margin=dict(l=8, r=8, t=48, b=8), title=dict(x=0, font=dict(size=15)))
        fig.update_xaxes(dtick=2)
        show(fig)
        peak = hh.groupby("hour").orders.sum().nlargest(3).index.tolist()
        st.caption(f"Busiest hours overall: {', '.join(f'{h}:00' for h in sorted(peak))}. "
                   f"Use this to schedule riders and dark-store staffing ahead of demand.")

# ============================== PRICING =======================================================
with tab_price:
    disc = q("discount_analysis")
    if disc.empty:
        st.warning("Not enough data for these filters.")
    else:
        disc["discount"] = disc.discount_pct.astype(str) + "%"
        c = st.columns(3)
        specs = [("gross_margin_pct", "Gross margin (%)", "%"), ("profit_per_order", "Profit per order (INR)", ""),
                 ("repeat_within_30d_pct", "30-day repeat rate (%)", "%")]
        for col, (metric, title, suffix) in zip(c, specs):
            fig = px.bar(disc, x="discount", y=metric, text=metric, title=title, color_discrete_sequence=[BLUE],
                         category_orders={"discount": disc.discount.tolist()})
            fig.update_traces(texttemplate="%{text:.0f}" + suffix, textposition="outside", cliponaxis=False)
            fig.update_xaxes(title_text="Discount on order")
            with col:
                show(style(fig, 330))
        d0, dmax = disc.iloc[0], disc.iloc[-1]
        breakeven = disc[disc.profit_per_order <= 0]
        extra = (f" Orders with a {int(breakeven.iloc[0].discount_pct)}% discount or more lose money on average."
                 if not breakeven.empty else "")
        st.info(f"Going from **{int(d0.discount_pct)}% to {int(dmax.discount_pct)}%** discount cuts gross margin from "
                f"{d0.gross_margin_pct:.1f}% to {dmax.gross_margin_pct:.1f}% and profit per order from "
                f"₹{d0.profit_per_order:.0f} to ₹{dmax.profit_per_order:.0f}. The 30-day repeat rate does not improve "
                f"({d0.repeat_within_30d_pct:.0f}% to {dmax.repeat_within_30d_pct:.0f}%).{extra}")
        st.caption("Caveat: this is observational. Customers who receive deep discounts are not a random sample "
                   "(they skew to paid channels), so a proper A/B test would be the next step before cutting offers.")

# ============================== CHURN =========================================================
with tab_churn:
    res = churn_results()
    m = res["metrics"]
    best = m[m["selected_model"]]
    st.markdown(f"**Question:** among customers active in the last {churn_model.ACTIVE_WINDOW_DAYS} days, who will *not* "
                f"order in the next {m['horizon_days']} days?  \n"
                f"**Validation:** trained on the {m['train_snapshot']} snapshot and tested on the later "
                f"{m['test_snapshot']} snapshot (out-of-time, no leakage).")
    c = st.columns(4)
    c[0].metric("ROC-AUC (unseen period)", f"{best['roc_auc']:.3f}")
    c[1].metric("Overall churn rate", f"{100 * best['churn_base_rate']:.0f}%")
    c[2].metric("Churn rate in riskiest 10%", f"{100 * best['top_decile_churn_rate']:.0f}%")
    c[3].metric("Model selected", m["selected_model"].replace("_", " ").title())
    st.caption(f"Logistic regression AUC {m['logistic_regression']['roc_auc']:.3f} vs gradient boosting "
               f"{m['gradient_boosting']['roc_auc']:.3f}. The simpler model generalised at least as well, so it was kept.")

    scores = res["scores"]
    scores = scores[scores.city.isin(sel_cities) & scores.acquisition_channel.isin(sel_channels)]
    l, r = st.columns(2)
    with l:
        imp = res["importance"].head(8).sort_values("importance")
        fig = px.bar(imp, x="importance", y="label", orientation="h", title="What drives churn? (permutation importance)",
                     color_discrete_sequence=[BLUE])
        fig.update_xaxes(title_text="Drop in AUC when the feature is shuffled")
        show(style(fig, 360, "x"))
    with r:
        fig = px.histogram(scores, x="churn_risk", nbins=20, title="Distribution of churn risk (active customers today)",
                           color_discrete_sequence=[BLUE])
        fig.update_xaxes(title_text="Predicted churn risk", tickformat=".0%")
        fig.update_yaxes(title_text="Customers")
        show(style(fig, 360))

    thr = scores.monetary.quantile(0.75) if len(scores) else 0
    winback = (scores[(scores.churn_risk >= 0.7) & (scores.monetary >= thr)]
               .sort_values("monetary", ascending=False))
    st.subheader("Win-back list: high-value customers likely to lapse")
    st.caption(f"Top-quartile lifetime spend (>= {inr(thr)}) and predicted churn risk >= 70%. "
               f"{len(winback):,} customers, {inr(winback.monetary.sum())} lifetime revenue.")
    st.dataframe(winback.head(200), hide_index=True, width="stretch", column_config={
        "churn_risk": st.column_config.ProgressColumn("Churn risk", min_value=0, max_value=1, format="%.2f"),
        "monetary": st.column_config.NumberColumn("Lifetime spend", format="₹%d"),
        "recency_days": "Days since order", "frequency": "Orders", "avg_delivery_min": "Avg delivery (min)",
        "late_share": st.column_config.NumberColumn("Late share", format="%.2f"),
        "acquisition_channel": "Channel", "city": "City", "customer_id": "Customer"})
    st.download_button("Download win-back list (CSV)", winback.to_csv(index=False).encode(), "winback_list.csv", "text/csv")
    st.caption("Scores are model predictions on simulated data; a real deployment would add monitoring and an A/B test of win-back offers.")

# ============================== SQL LAB =======================================================
with tab_sql:
    st.markdown("Every chart above is powered by a SQL file. Browse them here, or write your own read-only query "
                "against the filtered tables.")
    name = st.selectbox("Saved analysis query", db.QUERY_NAMES, index=db.QUERY_NAMES.index("cohort_retention"))
    l, r = st.columns([3, 2])
    with l:
        st.code(db.query_text(name), language="sql")
    with r:
        out = q(name)
        st.caption(f"{len(out):,} rows returned")
        st.dataframe(out.head(200), hide_index=True, width="stretch")

    st.subheader("Write your own query")
    with st.expander("Tables you can query"):
        st.markdown("`customers_f`, `orders_f`, `orders_cc` (filtered views), plus `customers`, `orders`, `order_items`, "
                    "`products`, `channel_cac`. Only `SELECT` / `WITH` statements are allowed.")
    sql = st.text_area("SQL", height=140, value=(
        "SELECT c.acquisition_channel, COUNT(*) AS orders, ROUND(AVG(o.net_revenue),0) AS aov\n"
        "FROM orders_f o JOIN customers_f c USING (customer_id)\n"
        "WHERE o.status = 'delivered'\nGROUP BY 1\nORDER BY orders DESC"))
    if st.button("Run query"):
        try:
            with db.session(cities, channels, start, end) as conn:
                st.dataframe(db.run_custom_select(conn, sql), hide_index=True, width="stretch")
        except Exception as exc:  # noqa: BLE001 - show any SQL error to the user
            st.error(f"Query failed: {exc}")
