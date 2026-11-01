-- Category GMV, margin and share of sales.
-- Skills: multi-table JOIN, window over aggregate (SUM(SUM()) OVER), RANK().
SELECT p.category,
       ROUND(SUM(oi.quantity * oi.unit_price), 0)                                              AS gmv,
       ROUND(SUM(oi.quantity * (oi.unit_price - p.cost)), 0)                                   AS gross_profit,
       ROUND(100.0 * SUM(oi.quantity * (oi.unit_price - p.cost))
                   / SUM(oi.quantity * oi.unit_price), 1)                                      AS margin_pct,
       SUM(oi.quantity)                                                                        AS units,
       COUNT(DISTINCT oi.order_id)                                                             AS orders,
       ROUND(100.0 * SUM(oi.quantity * oi.unit_price)
                   / SUM(SUM(oi.quantity * oi.unit_price)) OVER (), 1)                         AS gmv_share_pct,
       RANK() OVER (ORDER BY SUM(oi.quantity * oi.unit_price) DESC)                            AS gmv_rank
FROM order_items oi
JOIN orders_f o  ON o.order_id = oi.order_id AND o.status = 'delivered'
JOIN products p  ON p.product_id = oi.product_id
GROUP BY p.category
ORDER BY gmv DESC;
