-- City scorecard: revenue, AOV, delivery speed, cancellations and customer satisfaction.
-- Skills: JOIN, boolean aggregation, multi-metric scorecard.
SELECT c.city,
       c.city_tier,
       COUNT(DISTINCT o.customer_id)                                                   AS active_customers,
       SUM(o.status = 'delivered')                                                     AS delivered_orders,
       ROUND(SUM(CASE WHEN o.status = 'delivered' THEN o.net_revenue END), 0)          AS revenue,
       ROUND(AVG(CASE WHEN o.status = 'delivered' THEN o.net_revenue END), 1)          AS aov,
       ROUND(AVG(o.delivery_minutes), 1)                                               AS avg_delivery_min,
       ROUND(100.0 * AVG(o.delivery_minutes > 20), 1)                                  AS late_delivery_pct,
       ROUND(100.0 * AVG(o.status = 'cancelled'), 1)                                   AS cancel_rate_pct,
       ROUND(AVG(o.rating), 2)                                                         AS avg_rating
FROM orders_f o
JOIN customers_f c USING (customer_id)
GROUP BY c.city, c.city_tier
ORDER BY revenue DESC;
