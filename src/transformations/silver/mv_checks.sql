-- SILVER - mv_checks: THE clean receipt table. One row per real receipt (exact copies removed).
--
-- Built from bronze receipts + the silver line tables. Same rules as Phase 1 (phase1_eda/scripts/clean.py):
--   * money totals per receipt (gross, discounts, net, tax, paid, tips, cash, voids)
--   * 8 data-quality flags   (flag_*)        problems in the data - KEPT and flagged, never deleted
--   * 8 risk-behavior flags  (has_*, is_fully_comped)  the levers where money can leak at the register
--   * 4 context flags        (is_*)          normal situations that explain odd-looking receipts
--
-- Expectations (WARN level): each data-quality flag is also an expectation, so every pipeline update
-- records how many receipts broke each rule (pipeline UI + event log), without dropping them.
-- In fraud work the outliers are the signal, so we monitor them instead of deleting them.
--
-- Money identity checked by flag_unbalanced:  paid + gratuity = item sales - check discounts + tax
CREATE OR REFRESH MATERIALIZED VIEW silver.mv_checks (
  CONSTRAINT balanced_receipt          EXPECT (NOT flag_unbalanced),
  CONSTRAINT has_item_lines            EXPECT (NOT flag_no_items),
  CONSTRAINT has_payment               EXPECT (NOT flag_no_payment),
  CONSTRAINT normal_size_receipt       EXPECT (NOT flag_giant),
  CONSTRAINT closed_within_6_hours     EXPECT (NOT flag_long_open),
  CONSTRAINT plausible_check_id        EXPECT (NOT flag_odd_check_id),
  CONSTRAINT no_negative_prices        EXPECT (NOT flag_negative_price),
  CONSTRAINT priced_lines_have_qty     EXPECT (NOT flag_zero_qty_priced),
  CONSTRAINT open_close_times_parsed   EXPECT (open_time IS NOT NULL AND close_time IS NOT NULL),
  CONSTRAINT closes_after_it_opens     EXPECT (duration_min >= 0),
  CONSTRAINT known_store               EXPECT (store_name IS NOT NULL),
  CONSTRAINT known_channel             EXPECT (channel IS NOT NULL)
)
CLUSTER BY (dt, location_id)
COMMENT 'Clean receipts: one row per receipt, exact copies removed, money totals, 8 data-quality flags, 8 risk-behavior flags and 4 context flags.'
TBLPROPERTIES ('quality' = 'silver')
AS
WITH receipts AS (
  SELECT
    r.dt,
    r.LocationId AS location_id,
    r.Id         AS check_id,
    r.TableName  AS table_name,
    try_to_timestamp(replace(r.OpenTime,  'T', ' '), 'yyyy-MM-dd HH:mm') AS open_time,
    try_to_timestamp(replace(r.CloseTime, 'T', ' '), 'yyyy-MM-dd HH:mm') AS close_time,
    r.RevenueCenterId AS revenue_center_id,
    r.TrafficCount    AS guests,
    CASE WHEN r.ItemsSold IS NULL THEN 0 ELSE size(r.ItemsSold) END AS n_lines,
    CASE WHEN r.Voids     IS NULL THEN 0 ELSE size(r.Voids)     END AS n_voids,
    CASE WHEN r.Payments  IS NULL THEN 0 ELSE size(r.Payments)  END AS n_payments,
    CASE WHEN r.Discounts IS NULL THEN 0 ELSE size(r.Discounts) END AS n_check_discounts
  FROM bronze.st_raw_checks r
  LEFT ANTI JOIN silver.mv_receipt_copies x
    ON x.dt = r.dt AND x.location_id = r.LocationId AND x.check_id = r.Id
),
item_totals AS (
  SELECT dt, location_id, check_id,
    sum(sold_price)            AS item_sales,
    sum(gross_price * quantity) AS gross_sales,
    count_if(line_type IN ('menu item', 'combo part / add-on')) AS n_real_items,
    count_if(is_modifier)      AS n_modifiers,
    bool_or(sold_price < 0)    AS any_negative_price,
    bool_or(quantity = 0 AND sold_price <> 0) AS any_zero_qty_priced
  FROM silver.st_items
  GROUP BY dt, location_id, check_id
),
discount_totals AS (
  SELECT dt, location_id, check_id,
    sum(CASE WHEN level = 'item'  THEN amount ELSE 0 END) AS item_discounts,
    sum(CASE WHEN level = 'check' THEN amount ELSE 0 END) AS check_discounts,
    bool_or(is_walkout AND amount <> 0)        AS any_walkout,
    bool_or(is_self_approved AND amount <> 0)  AS any_self_approved_discount
  FROM silver.st_discounts
  GROUP BY dt, location_id, check_id
),
tax_totals AS (
  SELECT dt, location_id, check_id, sum(amount) AS tax
  FROM silver.st_taxes
  GROUP BY dt, location_id, check_id
),
payment_totals AS (
  SELECT dt, location_id, check_id,
    sum(amount)   AS amount_paid,
    sum(gratuity) AS gratuity,
    sum(CASE WHEN method_group = 'Cash' THEN amount ELSE 0 END) AS cash_paid,
    bool_or(is_refund)          AS any_refund,
    bool_or(is_gift_card_sale)  AS any_gift_card_sale,
    bool_or(is_tip_over_bill)   AS any_tip_over_bill
  FROM silver.st_payments
  GROUP BY dt, location_id, check_id
),
void_totals AS (
  SELECT dt, location_id, check_id, sum(amount) AS void_amount
  FROM silver.st_voids
  GROUP BY dt, location_id, check_id
),
joined AS (
  SELECT
    c.*,
    timestampdiff(MINUTE, c.open_time, c.close_time) AS duration_min,
    coalesce(i.item_sales, 0)       AS sold,
    coalesce(i.gross_sales, 0)      AS gross_ext,
    coalesce(i.n_real_items, 0)     AS n_real_items,
    coalesce(i.n_modifiers, 0)      AS n_modifiers,
    coalesce(i.any_negative_price, false)  AS any_negative_price,
    coalesce(i.any_zero_qty_priced, false) AS any_zero_qty_priced,
    coalesce(d.item_discounts, 0)   AS idisc,
    coalesce(d.check_discounts, 0)  AS cdisc,
    coalesce(d.any_walkout, false)  AS any_walkout,
    coalesce(d.any_self_approved_discount, false) AS any_self_approved_discount,
    coalesce(t.tax, 0)              AS tax,
    coalesce(p.amount_paid, 0)      AS pay,
    coalesce(p.gratuity, 0)         AS grat,
    coalesce(p.cash_paid, 0)        AS cash,
    coalesce(p.any_refund, false)   AS any_refund,
    coalesce(p.any_gift_card_sale, false) AS any_gift_card_sale,
    coalesce(p.any_tip_over_bill, false)  AS any_tip_over_bill,
    coalesce(v.void_amount, 0)      AS void_amt
  FROM receipts c
  LEFT JOIN item_totals     i ON i.dt = c.dt AND i.location_id = c.location_id AND i.check_id = c.check_id
  LEFT JOIN discount_totals d ON d.dt = c.dt AND d.location_id = c.location_id AND d.check_id = c.check_id
  LEFT JOIN tax_totals      t ON t.dt = c.dt AND t.location_id = c.location_id AND t.check_id = c.check_id
  LEFT JOIN payment_totals  p ON p.dt = c.dt AND p.location_id = c.location_id AND p.check_id = c.check_id
  LEFT JOIN void_totals     v ON v.dt = c.dt AND v.location_id = c.location_id AND v.check_id = c.check_id
)
SELECT
  j.dt,
  dayofweek(j.dt)              AS weekday_num,      -- 1 = Sunday ... 7 = Saturday
  date_format(j.dt, 'EEEE')    AS weekday,
  j.location_id,
  s.store_name,
  j.check_id,
  j.table_name,
  j.open_time,
  j.close_time,
  hour(j.open_time)            AS open_hour,
  j.duration_min,
  j.revenue_center_id,
  ch.channel,
  ch.channel_group,
  j.guests,
  j.n_lines,
  j.n_real_items,
  j.n_modifiers,
  j.n_voids,
  j.n_payments,
  j.n_check_discounts,
  -- money
  round(j.gross_ext, 2)                   AS gross_sales,
  round(j.idisc, 2)                       AS item_discounts,
  round(j.sold, 2)                        AS item_sales,
  round(j.cdisc, 2)                       AS check_discounts,
  round(j.sold - j.cdisc, 2)              AS net_sales,
  round(j.tax, 2)                         AS tax,
  round(j.sold - j.cdisc + j.tax, 2)      AS amount_due,
  round(j.pay, 2)                         AS amount_paid,
  round(0 - j.grat, 2)                    AS tips,
  round(j.cash, 2)                        AS cash_paid,
  round(j.void_amt, 2)                    AS void_amount,
  -- risk behaviors (levers where money can leak; not errors)
  j.n_voids > 0                           AS has_void,
  j.idisc + j.cdisc > 0                   AS has_discount,
  j.any_walkout                           AS has_walkout,
  j.any_self_approved_discount            AS has_self_approved_discount,
  (j.gross_ext > 0 AND j.sold - j.cdisc <= 0.005) AS is_fully_comped,
  j.any_refund                            AS has_refund,
  j.any_gift_card_sale                    AS has_gift_card_sale,
  j.any_tip_over_bill                     AS has_tip_over_bill,
  -- context (normal, but explains odd-looking receipts)
  j.duration_min = 0                      AS is_instant,
  to_date(j.open_time) > j.dt             AS is_after_midnight,
  j.guests = 0                            AS is_zero_guests,
  j.guests <> floor(j.guests)             AS is_split_guests,
  -- data-quality flags (kept, never deleted)
  abs((j.pay + j.grat) - (j.sold - j.cdisc + j.tax)) >= 0.015 AS flag_unbalanced,
  j.n_lines = 0                           AS flag_no_items,
  j.n_payments = 0                        AS flag_no_payment,
  j.n_lines > 200                         AS flag_giant,          -- p99 is 43 lines
  j.duration_min > 360                    AS flag_long_open,      -- open more than 6 hours
  (j.check_id <= 0 OR j.check_id > 10000000) AS flag_odd_check_id,
  j.any_negative_price                    AS flag_negative_price,
  j.any_zero_qty_priced                   AS flag_zero_qty_priced
FROM joined j
LEFT JOIN silver.mv_stores   s  ON s.location_id = j.location_id
LEFT JOIN silver.mv_channels ch ON ch.revenue_center_id = j.revenue_center_id;
