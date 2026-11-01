-- Monthly cohort retention: of the customers whose first delivered order was in month X,
-- what % ordered again N months later?
-- Skills: multi-step CTEs, date arithmetic, cohort analysis, self-join on customer.
WITH delivered AS (
    SELECT customer_id, strftime('%Y-%m', order_date) AS order_month
    FROM orders_cc
    WHERE status = 'delivered'
),
cohort_of AS (                                   -- first purchase month per customer
    SELECT customer_id, MIN(order_month) AS cohort_month
    FROM delivered
    GROUP BY customer_id
),
activity AS (                                    -- distinct (customer, months since first order)
    SELECT DISTINCT
           c.cohort_month,
           d.customer_id,
           (CAST(substr(d.order_month, 1, 4) AS INTEGER) - CAST(substr(c.cohort_month, 1, 4) AS INTEGER)) * 12
         + (CAST(substr(d.order_month, 6, 2) AS INTEGER) - CAST(substr(c.cohort_month, 6, 2) AS INTEGER)) AS month_idx
    FROM delivered d
    JOIN cohort_of c USING (customer_id)
),
cohort_size AS (
    SELECT cohort_month, COUNT(*) AS cohort_size
    FROM cohort_of
    GROUP BY cohort_month
)
SELECT a.cohort_month,
       a.month_idx,
       COUNT(DISTINCT a.customer_id)                                            AS retained,
       s.cohort_size,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id) / s.cohort_size, 1)          AS retention_pct
FROM activity a
JOIN cohort_size s USING (cohort_month)
GROUP BY a.cohort_month, a.month_idx
ORDER BY a.cohort_month, a.month_idx;
