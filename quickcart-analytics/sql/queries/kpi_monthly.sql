-- Monthly business KPIs with month-over-month growth.
-- Skills: CTE, conditional aggregation, LAG() window function.
WITH monthly AS (
    SELECT strftime('%Y-%m', order_date)                                           AS month,
           COUNT(*)                                                                AS total_orders,
           SUM(status = 'delivered')                                               AS delivered_orders,
           SUM(CASE WHEN status = 'delivered' THEN net_revenue END)                AS revenue,
           SUM(CASE WHEN status = 'delivered' THEN gross_value END)                AS gmv,
           SUM(CASE WHEN status = 'delivered' THEN net_revenue - cogs END)         AS gross_profit,
           COUNT(DISTINCT CASE WHEN status = 'delivered' THEN customer_id END)     AS active_customers,
           AVG(delivery_minutes)                                                   AS avg_delivery_min
    FROM orders_f
    GROUP BY 1
)
SELECT month,
       total_orders,
       delivered_orders,
       ROUND(revenue, 0)                                                   AS revenue,
       ROUND(gmv, 0)                                                       AS gmv,
       ROUND(gross_profit, 0)                                              AS gross_profit,
       ROUND(revenue * 1.0 / delivered_orders, 1)                          AS aov,
       ROUND(100.0 * gross_profit / revenue, 1)                            AS gross_margin_pct,
       active_customers,
       ROUND(avg_delivery_min, 1)                                          AS avg_delivery_min,
       ROUND(100.0 * (total_orders - delivered_orders) / total_orders, 1)  AS cancel_rate_pct,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
                   / LAG(revenue) OVER (ORDER BY month), 1)                AS revenue_mom_pct
FROM monthly
ORDER BY month;
