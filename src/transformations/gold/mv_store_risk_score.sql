-- GOLD - mv_store_risk_score: the same signals per restaurant, a 0-100 score and a comparison with the chain.
--
-- Phase 1: risk depends on WHO and WHERE, not WHEN. Store void rates ranged 0.3% - 2.3% of gross sales;
-- Munster (store 80) voided 2.29%, 2.9x the chain median, every month.
--   *_vs_chain   the store's rate divided by the chain median (2.0 = twice the typical store)
--   risk_score   average percentile on the 5 signals x 100, among stores with 200+ receipts
-- Store names are fine on slides (they are places, not people).
CREATE OR REFRESH MATERIALIZED VIEW gold.mv_store_risk_score
COMMENT 'Risk signals per restaurant as rates, ratio to the chain median and a 0-100 score (stores with 200+ receipts).'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH store AS (
  SELECT
    location_id,
    first(store_name, true)        AS store_name,
    count(*)                       AS n_receipts,
    count(DISTINCT dt)             AS n_days,
    sum(gross_sales)               AS gross_sales,
    sum(void_amount)               AS void_amount,
    sum(item_discounts + check_discounts) AS discount_amount,
    count_if(has_walkout)          AS n_walkout_receipts,
    count_if(is_fully_comped)      AS n_comped_receipts,
    count_if(has_void)             AS n_receipts_with_void
  FROM silver.mv_checks
  GROUP BY location_id
),
cards AS (
  SELECT p.location_id,
         count_if(p.method_group = 'Card') AS n_card_payments,
         count_if(p.method_group = 'Card' AND p.is_tip_over_bill) AS n_tip_over_bill
  FROM silver.st_payments p
  JOIN silver.mv_checks c ON c.dt = p.dt AND c.location_id = p.location_id AND c.check_id = p.check_id
  GROUP BY p.location_id
),
rates AS (
  SELECT
    s.*,
    round(try_divide(s.void_amount, s.gross_sales), 5)             AS void_rate,
    round(try_divide(s.discount_amount, s.gross_sales), 5)         AS discount_rate,
    round(try_divide(s.n_walkout_receipts, s.n_receipts), 5)       AS walkout_rate,
    round(try_divide(s.n_comped_receipts, s.n_receipts), 5)        AS comp_rate,
    round(try_divide(c.n_tip_over_bill, c.n_card_payments), 5)     AS tip_over_bill_rate
  FROM store s LEFT JOIN cards c ON c.location_id = s.location_id
  WHERE s.n_receipts >= 200
),
chain AS (
  SELECT percentile(void_rate, 0.5) AS med_void, percentile(discount_rate, 0.5) AS med_discount,
         percentile(walkout_rate, 0.5) AS med_walkout, percentile(comp_rate, 0.5) AS med_comp
  FROM rates
),
ranked AS (
  SELECT
    r.*,
    round(try_divide(r.void_rate, chain.med_void), 2)         AS void_vs_chain,
    round(try_divide(r.discount_rate, chain.med_discount), 2) AS discount_vs_chain,
    round(try_divide(r.walkout_rate, chain.med_walkout), 2)   AS walkout_vs_chain,
    round(try_divide(r.comp_rate, chain.med_comp), 2)         AS comp_vs_chain,
    percent_rank() OVER (ORDER BY r.void_rate)          AS pct_void,
    percent_rank() OVER (ORDER BY r.discount_rate)      AS pct_discount,
    percent_rank() OVER (ORDER BY r.walkout_rate)       AS pct_walkout,
    percent_rank() OVER (ORDER BY r.comp_rate)          AS pct_comp,
    percent_rank() OVER (ORDER BY r.tip_over_bill_rate) AS pct_tip_over_bill
  FROM rates r CROSS JOIN chain
)
SELECT
  location_id, store_name, n_days, n_receipts, round(gross_sales, 2) AS gross_sales,
  void_rate, discount_rate, walkout_rate, comp_rate, tip_over_bill_rate,
  void_vs_chain, discount_vs_chain, walkout_vs_chain, comp_vs_chain,
  round(100 * (pct_void + pct_discount + pct_walkout + pct_comp + pct_tip_over_bill) / 5, 1) AS risk_score,
  rank() OVER (ORDER BY (pct_void + pct_discount + pct_walkout + pct_comp + pct_tip_over_bill) DESC) AS risk_rank
FROM ranked;
