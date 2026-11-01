-- Does delivery speed drive repeat purchase?
-- For every delivered order: did the same customer order again within 30 days?
-- Orders in the last 30 days of data are excluded (right-censoring) so the 30-day window is fully observed.
-- Skills: LEAD() window function, bucketing with CASE, censoring-aware metric design.
WITH seq AS (
    SELECT order_id,
           order_date,
           delivery_minutes,
           LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_ts) AS next_order_date
    FROM orders_cc
    WHERE status = 'delivered'
),
lim AS (SELECT MAX(order_date) AS max_date FROM orders)
SELECT CASE
           WHEN delivery_minutes < 10 THEN '1. < 10 min'
           WHEN delivery_minutes < 15 THEN '2. 10-15 min'
           WHEN delivery_minutes < 20 THEN '3. 15-20 min'
           WHEN delivery_minutes < 25 THEN '4. 20-25 min'
           ELSE                            '5. 25+ min'
       END AS delivery_bucket,
       COUNT(*) AS orders,
       ROUND(100.0 * AVG(CASE WHEN next_order_date IS NOT NULL
                               AND julianday(next_order_date) - julianday(order_date) <= 30
                              THEN 1 ELSE 0 END), 1) AS repeat_within_30d_pct
FROM seq
CROSS JOIN lim
WHERE julianday(lim.max_date) - julianday(seq.order_date) >= 30
GROUP BY delivery_bucket
ORDER BY delivery_bucket;
