-- GOLD - mv_employee_risk_score: one explainable risk score per eligible employee.
--
-- Phase 1 found that the risk signals stack up on the same people (106 employees were top 10% on
-- 3+ of 5 signals, about 5x what chance gives). This table turns that finding into a ranking:
--
--   pct_*            percentile of the employee on each signal among eligible employees (0 = lowest, 1 = highest)
--   risk_score       average of the 5 percentiles x 100  (0-100; 50 = typical)
--   n_top10_signals  on how many of the 5 signals the employee is in the top 10%
--   risk_tier        'review first' (top 10% on 3+ signals), 'watch' (2), 'normal' (0-1)
--
-- The 5 signals are the Phase 1 ones: void, discount, walkout, comp, card tips over the bill.
-- Cash share is reported in mv_employee_signals but left out of the score (it mostly reflects the
-- role - e.g. bartenders - and we have no job-role lookup).
--
-- A high score is a reason to LOOK, not proof of anything: the data has no fraud labels.
CREATE OR REFRESH MATERIALIZED VIEW gold.mv_employee_risk_score
CLUSTER BY (risk_tier, main_store_id)
COMMENT 'Explainable 0-100 risk score per eligible employee (average percentile on 5 signals) + top-10% signal count and tier. A reason to review, not proof.'
TBLPROPERTIES ('quality' = 'gold')
AS
WITH eligible AS (
  SELECT * FROM gold.mv_employee_signals WHERE is_eligible
),
ranked AS (
  SELECT
    *,
    percent_rank() OVER (ORDER BY void_rate)          AS pct_void,
    percent_rank() OVER (ORDER BY discount_rate)      AS pct_discount,
    percent_rank() OVER (ORDER BY walkout_rate)       AS pct_walkout,
    percent_rank() OVER (ORDER BY comp_rate)          AS pct_comp,
    percent_rank() OVER (ORDER BY tip_over_bill_rate) AS pct_tip_over_bill,
    ntile(10) OVER (ORDER BY void_rate DESC)          = 1 AS top10_void,
    ntile(10) OVER (ORDER BY discount_rate DESC)      = 1 AS top10_discount,
    ntile(10) OVER (ORDER BY walkout_rate DESC)       = 1 AS top10_walkout,
    ntile(10) OVER (ORDER BY comp_rate DESC)          = 1 AS top10_comp,
    ntile(10) OVER (ORDER BY tip_over_bill_rate DESC) = 1 AS top10_tip_over_bill
  FROM eligible
),
scored AS (
  SELECT
    *,
    round(100 * (pct_void + pct_discount + pct_walkout + pct_comp + pct_tip_over_bill) / 5, 1) AS risk_score,
    CAST(top10_void AS INT) + CAST(top10_discount AS INT) + CAST(top10_walkout AS INT)
      + CAST(top10_comp AS INT) + CAST(top10_tip_over_bill AS INT) AS n_top10_signals
  FROM ranked
)
SELECT
  employee_id,
  main_store_id,
  gross_sales,
  n_receipts,
  void_rate, discount_rate, walkout_rate, comp_rate, tip_over_bill_rate, cash_share,
  round(pct_void, 3) AS pct_void,
  round(pct_discount, 3) AS pct_discount,
  round(pct_walkout, 3) AS pct_walkout,
  round(pct_comp, 3) AS pct_comp,
  round(pct_tip_over_bill, 3) AS pct_tip_over_bill,
  top10_void, top10_discount, top10_walkout, top10_comp, top10_tip_over_bill,
  n_top10_signals,
  risk_score,
  CASE WHEN n_top10_signals >= 3 THEN 'review first'
       WHEN n_top10_signals = 2  THEN 'watch'
       ELSE 'normal' END AS risk_tier,
  rank() OVER (ORDER BY n_top10_signals DESC, risk_score DESC) AS risk_rank
FROM scored;
