-- RFM segmentation: Recency, Frequency, Monetary scored 1-5 with NTILE, then mapped to named segments.
-- Skills: NTILE window function, CROSS JOIN reference date, CASE-based business rules.
WITH base AS (
    SELECT customer_id,
           MAX(order_date)       AS last_order,
           COUNT(*)              AS frequency,
           SUM(net_revenue)      AS monetary
    FROM orders_cc
    WHERE status = 'delivered'
    GROUP BY customer_id
),
ref AS (SELECT MAX(order_date) AS ref_date FROM orders),
scored AS (
    SELECT b.customer_id,
           CAST(julianday(r.ref_date) - julianday(b.last_order) AS INTEGER) AS recency_days,
           b.frequency,
           b.monetary,
           NTILE(5) OVER (ORDER BY julianday(r.ref_date) - julianday(b.last_order) DESC) AS r_score,  -- 5 = most recent
           NTILE(5) OVER (ORDER BY b.frequency, b.monetary)                              AS f_score,
           NTILE(5) OVER (ORDER BY b.monetary)                                           AS m_score
    FROM base b
    CROSS JOIN ref r
)
SELECT s.customer_id,
       c.city,
       c.acquisition_channel,
       s.recency_days,
       s.frequency,
       ROUND(s.monetary, 0) AS monetary,
       s.r_score, s.f_score, s.m_score,
       CASE
           WHEN s.r_score >= 4 AND s.f_score >= 4 THEN 'Champions'
           WHEN s.r_score >= 3 AND s.f_score >= 3 THEN 'Loyal'
           WHEN s.r_score <= 2 AND s.f_score >= 4 THEN 'At Risk (High Value)'
           WHEN s.r_score <= 2 AND s.f_score  = 3 THEN 'Needs Attention'
           WHEN s.r_score >= 4                    THEN 'New / Promising'
           WHEN s.r_score <= 2                    THEN 'Hibernating'
           ELSE                                        'Potential Loyalist'
       END AS segment
FROM scored s
JOIN customers_f c USING (customer_id);
