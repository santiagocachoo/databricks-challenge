-- GOLD - mv_data_quality_summary: one row per business day showing what happened to the data on its
-- way from bronze to silver. This is the evidence table for the data-quality part of the presentation:
--   completeness  raw receipts in, clean receipts out, rows with rescued (off-contract) data
--   uniqueness    exact copies removed;  unreconciled_receipts must be 0 (raw = clean + copies)
--   accuracy      share of receipts whose money identity balances
--   validity      count of each data-quality flag (kept and flagged, not deleted)
CREATE OR REFRESH MATERIALIZED VIEW gold.mv_data_quality_summary
COMMENT 'Per business day: raw vs clean receipt counts, copies removed, reconciliation, balance rate and every data-quality flag.'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH raw AS (
  SELECT dt,
         count(*)                               AS raw_receipts,
         count_if(_rescued_data IS NOT NULL)    AS receipts_with_rescued_data,
         count_if(BusinessDate <> CAST(dt AS STRING)) AS receipts_date_mismatch,
         max(ingested_at)                       AS last_ingested_at
  FROM bronze.st_raw_checks
  GROUP BY dt
),
copies AS (
  SELECT dt, count(*) AS copies_removed FROM silver.mv_receipt_copies GROUP BY dt
),
clean AS (
  SELECT dt,
         count(*)                         AS clean_receipts,
         count(DISTINCT location_id)      AS stores_reporting,
         round(sum(item_sales), 2)        AS item_sales,
         count_if(flag_unbalanced)        AS flag_unbalanced,
         count_if(flag_no_items)          AS flag_no_items,
         count_if(flag_no_payment)        AS flag_no_payment,
         count_if(flag_giant)             AS flag_giant,
         count_if(flag_long_open)         AS flag_long_open,
         count_if(flag_odd_check_id)      AS flag_odd_check_id,
         count_if(flag_negative_price)    AS flag_negative_price,
         count_if(flag_zero_qty_priced)   AS flag_zero_qty_priced,
         count_if(flag_unbalanced OR flag_no_items OR flag_no_payment OR flag_giant OR flag_long_open
                  OR flag_odd_check_id OR flag_negative_price OR flag_zero_qty_priced) AS receipts_with_any_flag
  FROM silver.mv_checks
  GROUP BY dt
)
SELECT
  r.dt,
  r.raw_receipts,
  coalesce(x.copies_removed, 0)                           AS copies_removed,
  coalesce(c.clean_receipts, 0)                           AS clean_receipts,
  r.raw_receipts - coalesce(x.copies_removed, 0) - coalesce(c.clean_receipts, 0) AS unreconciled_receipts,
  c.stores_reporting,
  c.item_sales,
  round(100 * (1 - try_divide(c.flag_unbalanced, c.clean_receipts)), 3)        AS pct_balanced,
  c.receipts_with_any_flag,
  round(100 * try_divide(c.receipts_with_any_flag, c.clean_receipts), 2)       AS pct_flagged,
  c.flag_unbalanced, c.flag_no_items, c.flag_no_payment, c.flag_giant, c.flag_long_open,
  c.flag_odd_check_id, c.flag_negative_price, c.flag_zero_qty_priced,
  r.receipts_with_rescued_data,
  r.receipts_date_mismatch,
  r.last_ingested_at
FROM raw r
LEFT JOIN copies x ON x.dt = r.dt
LEFT JOIN clean  c ON c.dt = r.dt;
