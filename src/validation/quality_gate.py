# Databricks notebook source
# MAGIC %md
# MAGIC # Quality gate (job task 2 of 2)
# MAGIC
# MAGIC Runs after every pipeline update. Expectations inside the pipeline check **rows** one at a time;
# MAGIC this gate checks things a single row cannot show: duplicates across rows, row counts that must
# MAGIC add up between layers, whole-table rates, and privacy.
# MAGIC
# MAGIC Every result is appended to `gold.quality_gate_results` (one row per check per run).
# MAGIC If any check fails, the notebook raises an error, the **job run fails**, and the job's failure
# MAGIC e-mail goes out, so bad data never reaches the dashboard silently.

# COMMAND ----------

import datetime

dbutils.widgets.text("catalog", "workspace")  # noqa: F821 - dbutils/spark are provided by Databricks
catalog = dbutils.widgets.get("catalog")  # noqa: F821
spark.sql(f"USE CATALOG {catalog}")  # noqa: F821
run_at = datetime.datetime.now(datetime.timezone.utc)


def scalar(sql):
    return spark.sql(sql).collect()[0][0]  # noqa: F821


CHECKS = [
    # (dimension, check name, SQL returning one number, rule as text, pass test)
    ("uniqueness", "no duplicate receipt keys in silver.mv_checks",
     "SELECT count(*) FROM (SELECT dt, location_id, check_id FROM silver.mv_checks GROUP BY ALL HAVING count(*) > 1)",
     "= 0", lambda v: v == 0),
    ("uniqueness", "no exact-copy receipt left in silver.mv_checks",
     "SELECT count(*) FROM silver.mv_checks c JOIN silver.mv_receipt_copies x USING (dt, location_id, check_id)",
     "= 0", lambda v: v == 0),
    ("consistency", "bronze receipts = silver receipts + copies removed (every day)",
     "SELECT coalesce(sum(abs(unreconciled_receipts)), 0) FROM gold.mv_data_quality_summary",
     "= 0", lambda v: v == 0),
    ("completeness", "every day in bronze reached silver",
     "SELECT count(*) FROM (SELECT DISTINCT dt FROM bronze.st_raw_checks) b LEFT ANTI JOIN (SELECT DISTINCT dt FROM silver.mv_checks) s USING (dt)",
     "= 0", lambda v: v == 0),
    ("completeness", "no receipt without day, store or number",
     "SELECT count(*) FROM silver.mv_checks WHERE dt IS NULL OR location_id IS NULL OR check_id IS NULL",
     "= 0", lambda v: v == 0),
    ("completeness", "share of receipts from a known store (%)",
     "SELECT 100 * avg(CASE WHEN store_name IS NOT NULL THEN 1 ELSE 0 END) FROM silver.mv_checks",
     ">= 99.9", lambda v: v is not None and v >= 99.9),
    ("accuracy", "share of receipts whose money identity balances (%)",
     "SELECT 100 * avg(CASE WHEN flag_unbalanced THEN 0 ELSE 1 END) FROM silver.mv_checks",
     ">= 99.9 (Phase 1: 99.996)", lambda v: v is not None and v >= 99.9),
    ("validity", "share of receipts with any data-quality flag (%)",
     "SELECT 100 * sum(receipts_with_any_flag) / sum(clean_receipts) FROM gold.mv_data_quality_summary",
     "<= 5 (Phase 1: 2.0)", lambda v: v is not None and v <= 5),
    ("validity", "receipts with off-contract (rescued) data",
     "SELECT coalesce(sum(receipts_with_rescued_data), 0) FROM gold.mv_data_quality_summary",
     "= 0", lambda v: v == 0),
    ("validity", "risk scores inside 0-100",
     "SELECT count(*) FROM gold.mv_employee_risk_score WHERE risk_score < 0 OR risk_score > 100 OR risk_score IS NULL",
     "= 0", lambda v: v == 0),
    ("validity", "eligible employees available for the score",
     "SELECT count(*) FROM gold.mv_employee_risk_score",
     ">= 100", lambda v: v >= 100),
    # Store and channel tables legitimately have a "Name" column (place names), so a bare "name"
    # column only counts as personal data in an employee table.
    ("privacy", "no personal-data columns in bronze, silver or gold",
     f"""SELECT count(*) FROM {catalog}.information_schema.columns
         WHERE table_schema IN ('bronze', 'silver', 'gold')
           AND (lower(column_name) RLIKE '(first_?name|last_?name|full_?name|birth|payroll|locationemployeeid|alternateemployeeid)'
                OR (lower(table_name) LIKE '%employee%' AND lower(column_name) RLIKE '^(name|employee_?name)$'))""",
     "= 0", lambda v: v == 0),
]

results = []
for dimension, name, sql, rule, passes in CHECKS:
    try:
        value = scalar(sql)
        value = float(value) if value is not None else None
        ok = bool(passes(value))
        error = None
    except Exception as e:  # a check that cannot run counts as failed
        value, ok, error = None, False, str(e)[:500]
    results.append((run_at, dimension, name, rule, value, ok, error))
    print(f"{'PASS' if ok else 'FAIL'}  [{dimension}] {name}: {value} (rule {rule})" + (f"  ERROR {error}" if error else ""))

# COMMAND ----------

schema = "run_at TIMESTAMP, dimension STRING, check_name STRING, rule STRING, value DOUBLE, passed BOOLEAN, error STRING"
(spark.createDataFrame(results, schema)  # noqa: F821
     .write.mode("append").option("mergeSchema", "true")
     .saveAsTable(f"{catalog}.gold.quality_gate_results"))

failed = [r for r in results if not r[5]]
print(f"\n{len(results) - len(failed)} of {len(results)} checks passed.")
if failed:
    raise Exception("Quality gate FAILED: " + "; ".join(r[2] for r in failed))
