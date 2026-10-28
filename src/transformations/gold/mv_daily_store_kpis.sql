-- GOLD - mv_daily_store_kpis: one row per restaurant per business day. Feeds the dashboard trend charts
-- (sales rhythm, void and discount rates over time, walkouts) and lets a manager spot a bad day fast.
CREATE OR REFRESH MATERIALIZED VIEW gold.mv_daily_store_kpis
CLUSTER BY (dt, location_id)
COMMENT 'Daily KPIs per restaurant: receipts, guests, sales, discounts, voids, walkouts, comps, tips and their rates.'
TBLPROPERTIES ('quality' = 'gold')
AS
SELECT
  dt,
  first(weekday, true)                 AS weekday,
  location_id,
  first(store_name, true)              AS store_name,
  count(*)                             AS n_receipts,
  round(sum(guests), 1)                AS guests,
  round(sum(gross_sales), 2)           AS gross_sales,
  round(sum(net_sales), 2)             AS net_sales,
  round(sum(item_discounts + check_discounts), 2) AS discount_amount,
  round(sum(void_amount), 2)           AS void_amount,
  round(sum(tips), 2)                  AS tips,
  round(sum(cash_paid), 2)             AS cash_paid,
  count_if(has_walkout)                AS n_walkouts,
  count_if(is_fully_comped)            AS n_fully_comped,
  count_if(has_void)                   AS n_receipts_with_void,
  round(try_divide(sum(void_amount), sum(gross_sales)), 5)                     AS void_rate,
  round(try_divide(sum(item_discounts + check_discounts), sum(gross_sales)), 5) AS discount_rate,
  count_if(flag_unbalanced OR flag_no_items OR flag_no_payment OR flag_giant OR flag_long_open
           OR flag_odd_check_id OR flag_negative_price OR flag_zero_qty_priced) AS n_flagged_receipts
FROM silver.mv_checks
GROUP BY dt, location_id;
