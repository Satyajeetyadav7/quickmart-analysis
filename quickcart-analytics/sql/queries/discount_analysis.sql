-- Do deeper discounts buy loyalty, or just burn margin?
-- Per discount level: order count, AOV, gross margin, profit per order and 30-day repeat rate.
-- Skills: LEAD(), conditional aggregation, margin vs retention trade-off analysis.
WITH seq AS (
    SELECT order_id,
           discount_pct,
           net_revenue,
           cogs,
           order_date,
           LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_ts) AS next_order_date
    FROM orders_cc
    WHERE status = 'delivered'
),
lim AS (SELECT MAX(order_date) AS max_date FROM orders)
SELECT discount_pct,
       COUNT(*)                                                    AS orders,
       ROUND(AVG(net_revenue), 1)                                  AS aov,
       ROUND(100.0 * SUM(net_revenue - cogs) / SUM(net_revenue), 1) AS gross_margin_pct,
       ROUND(AVG(net_revenue - cogs), 1)                           AS profit_per_order,
       ROUND(100.0 * AVG(CASE WHEN next_order_date IS NOT NULL
                               AND julianday(next_order_date) - julianday(order_date) <= 30
                              THEN 1 ELSE 0 END), 1)               AS repeat_within_30d_pct
FROM seq
CROSS JOIN lim
WHERE julianday(lim.max_date) - julianday(seq.order_date) >= 30
GROUP BY discount_pct
ORDER BY discount_pct;
