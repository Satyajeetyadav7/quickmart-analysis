-- Demand heatmap input: orders by day-of-week x hour of day (staffing / rider planning).
-- dow: 0 = Monday ... 6 = Sunday
SELECT dow,
       order_hour                    AS hour,
       COUNT(*)                      AS orders,
       ROUND(AVG(delivery_minutes), 1) AS avg_delivery_min
FROM orders_f
WHERE status = 'delivered'
GROUP BY dow, order_hour
ORDER BY dow, order_hour;
