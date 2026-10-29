"""
GOLD - mv_employee_signals: one row per employee who rang a sale, with the 6 risk signals as RATES.

Same definitions as the Phase 1 "signals stack up" analysis (phase1_eda/scripts/charts.py, chart 11):
  void_rate        void $            / gross sales
  discount_rate    discount $        / gross sales
  walkout_rate     walked-out receipts / receipts
  comp_rate        fully comped receipts / receipts
  cash_share       cash $            / $ paid
  tip_over_bill_rate  card payments with a tip larger than the bill / card payments
Rates, not totals, so busy employees do not look worse just for being busy.

Eligibility (is_eligible): Phase 1 compared employees with $5,000+ in sales and 50+ card payments
over 115 days; below that a single $30 void can make a 10% void rate. Here the same bar is scaled
to the number of days loaded (same bar per day), so the table works for 7 days or for all 115.

Only clean receipts count: every line table is joined to silver.mv_checks, which drops exact copies.
Employee IDs are anonymous POS ids; no names exist anywhere in the pipeline. Individual employees are not shown in reports.
"""
try:
    from pyspark import pipelines as dp
except ImportError:  # older Databricks runtimes expose the same API as `dlt`
    import dlt as dp

materialized_view = getattr(dp, "materialized_view", dp.table)

EMPLOYEE_SIGNALS_SQL = """
WITH clean AS (
  SELECT dt, location_id, check_id, is_fully_comped FROM silver.mv_checks
),
days AS (SELECT count(DISTINCT dt) AS n_days FROM clean),
lines AS (
  SELECT i.* FROM silver.st_items i
  JOIN clean c ON c.dt = i.dt AND c.location_id = i.location_id AND c.check_id = i.check_id
  WHERE i.employee_id IS NOT NULL
),
sales AS (
  SELECT employee_id,
         mode(location_id)                       AS main_store_id,
         sum(gross_price * quantity)             AS gross_sales,
         count(DISTINCT dt, location_id, check_id) AS n_receipts
  FROM lines GROUP BY employee_id
),
voids AS (
  SELECT v.employee_id, sum(v.amount) AS void_amount
  FROM silver.st_voids v
  JOIN clean c ON c.dt = v.dt AND c.location_id = v.location_id AND c.check_id = v.check_id
  WHERE v.employee_id IS NOT NULL GROUP BY v.employee_id
),
discounts AS (
  SELECT d.employee_id,
         sum(d.amount) AS discount_amount,
         count(DISTINCT CASE WHEN d.is_walkout AND d.amount > 0
                             THEN concat_ws('|', d.dt, d.location_id, d.check_id) END) AS n_walkout_receipts
  FROM silver.st_discounts d
  JOIN clean c ON c.dt = d.dt AND c.location_id = d.location_id AND c.check_id = d.check_id
  WHERE d.employee_id IS NOT NULL GROUP BY d.employee_id
),
payments AS (
  SELECT p.employee_id,
         sum(CASE WHEN p.method_group = 'Cash' THEN p.amount ELSE 0 END) AS cash_paid,
         sum(CASE WHEN p.amount > 0 THEN p.amount ELSE 0 END)            AS amount_paid,
         count_if(p.method_group = 'Card')                               AS n_card_payments,
         count_if(p.method_group = 'Card' AND p.is_tip_over_bill)        AS n_tip_over_bill
  FROM silver.st_payments p
  JOIN clean c ON c.dt = p.dt AND c.location_id = p.location_id AND c.check_id = p.check_id
  WHERE p.employee_id IS NOT NULL GROUP BY p.employee_id
),
comps AS (
  SELECT l.employee_id, count(*) AS n_comped_receipts
  FROM (SELECT DISTINCT dt, location_id, check_id, employee_id FROM lines) l
  JOIN clean c ON c.dt = l.dt AND c.location_id = l.location_id AND c.check_id = l.check_id
  WHERE c.is_fully_comped GROUP BY l.employee_id
)
SELECT
  s.employee_id,
  s.main_store_id,
  round(s.gross_sales, 2)                    AS gross_sales,
  s.n_receipts,
  coalesce(p.n_card_payments, 0)             AS n_card_payments,
  round(try_divide(coalesce(v.void_amount, 0), s.gross_sales), 5)          AS void_rate,
  round(try_divide(coalesce(d.discount_amount, 0), s.gross_sales), 5)      AS discount_rate,
  round(try_divide(coalesce(d.n_walkout_receipts, 0), s.n_receipts), 5)    AS walkout_rate,
  round(try_divide(coalesce(k.n_comped_receipts, 0), s.n_receipts), 5)     AS comp_rate,
  round(try_divide(coalesce(p.cash_paid, 0), p.amount_paid), 5)            AS cash_share,
  round(try_divide(coalesce(p.n_tip_over_bill, 0), p.n_card_payments), 5)  AS tip_over_bill_rate,
  days.n_days                                                              AS days_loaded,
  round({min_sales} * days.n_days / {phase1_days}, 2)                      AS min_sales_bar,
  ceil({min_cards} * days.n_days / {phase1_days})                          AS min_card_payments_bar,
  s.gross_sales >= {min_sales} * days.n_days / {phase1_days}
    AND coalesce(p.n_card_payments, 0) >= ceil({min_cards} * days.n_days / {phase1_days}) AS is_eligible
FROM sales s
CROSS JOIN days
LEFT JOIN voids     v ON v.employee_id = s.employee_id
LEFT JOIN discounts d ON d.employee_id = s.employee_id
LEFT JOIN payments  p ON p.employee_id = s.employee_id
LEFT JOIN comps     k ON k.employee_id = s.employee_id
WHERE s.gross_sales > 0
"""


def employee_signals_sql(conf_get):
    return EMPLOYEE_SIGNALS_SQL.format(
        min_sales=float(conf_get("min_sales_phase1", "5000")),
        min_cards=float(conf_get("min_card_payments_phase1", "50")),
        phase1_days=float(conf_get("phase1_days", "115")),
    )


@materialized_view(
    name="gold.mv_employee_signals",
    comment="One row per employee who rang a sale: 6 risk signals as rates + is_eligible (Phase 1 sales/card bar scaled to the days loaded).",
    cluster_by=["employee_id"],
    table_properties={"quality": "gold"},
)
@dp.expect("rates_between_0_and_1", "void_rate BETWEEN 0 AND 1 AND walkout_rate BETWEEN 0 AND 1 AND comp_rate BETWEEN 0 AND 1")
def mv_employee_signals():
    return spark.sql(employee_signals_sql(spark.conf.get))  # noqa: F821 - `spark` is provided by the pipeline runtime
