-- Which acquisition channel pays back? 90-day gross profit per customer vs assumed CAC.
-- Only customers with a fully observed 90-day window are included.
-- Skills: LEFT JOIN with conditional aggregation, cohort windows, unit economics (LTV:CAC).
WITH ref AS (SELECT MAX(order_date) AS max_date FROM orders),
cohort AS (
    SELECT c.customer_id, c.acquisition_channel, c.signup_date
    FROM customers_f c
    CROSS JOIN ref r
    WHERE julianday(r.max_date) - julianday(c.signup_date) >= 90
),
per_customer AS (
    SELECT k.customer_id,
           k.acquisition_channel,
           COALESCE(SUM(CASE WHEN julianday(o.order_date) - julianday(k.signup_date) <= 90 THEN 1 END), 0)                     AS orders_90d,
           COALESCE(SUM(CASE WHEN julianday(o.order_date) - julianday(k.signup_date) <= 90 THEN o.net_revenue - o.cogs END), 0) AS gp_90d,
           MAX(CASE WHEN julianday(o.order_date) - julianday(k.signup_date) BETWEEN 30 AND 90 THEN 1 ELSE 0 END)               AS active_after_day30
    FROM cohort k
    LEFT JOIN orders_cc o ON o.customer_id = k.customer_id AND o.status = 'delivered'
    GROUP BY k.customer_id, k.acquisition_channel
)
SELECT p.acquisition_channel                                           AS channel,
       COUNT(*)                                                        AS customers,
       ROUND(AVG(p.orders_90d), 2)                                     AS avg_orders_90d,
       ROUND(AVG(p.gp_90d), 0)                                         AS avg_gross_profit_90d,
       ROUND(100.0 * AVG(p.active_after_day30), 1)                     AS retained_after_day30_pct,
       a.cac_inr,
       ROUND(AVG(p.gp_90d) * 1.0 / NULLIF(a.cac_inr, 0), 2)            AS ltv90_to_cac
FROM per_customer p
JOIN channel_cac a ON a.channel = p.acquisition_channel
GROUP BY p.acquisition_channel, a.cac_inr
ORDER BY avg_gross_profit_90d DESC;
