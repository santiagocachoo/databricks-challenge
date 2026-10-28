"""
Local dry run of the whole pipeline logic with plain PySpark - no Databricks, no compute quota.

Runs the same transformation code as the pipeline (bronze -> silver -> gold), in batch instead of
streaming, on local files, then prints the parity numbers we compare with Phase 1 and every
expectation's violation count. We used it to check the Spark port before deploying: on May 4-10
it reproduces the Phase 1 DuckDB numbers exactly (140,208 raw receipts, 12 copies, 140,196 clean,
every flag count, every line count).

Usage (needs Java 17+ and `pip install pyspark==4.0.1`):
    python src/validation/local_dry_run.py <repo root> <folder with checks/ and dimensions/>
    e.g. python src/validation/local_dry_run.py . upload_test/
where checks/ holds checks_YYYY-MM-DD.json.gz files and dimensions/ the *.json.gz lookups.
"""
import builtins, glob, importlib.util, json, re, sys, time, types

from pyspark.sql import SparkSession

REPO = sys.argv[1]
DATA = sys.argv[2]  # folder with checks_*.json.gz and dimensions/

spark = (SparkSession.builder.master("local[4]").appName("local_test")
         .config("spark.sql.ansi.enabled", "true").config("spark.sql.session.timeZone", "UTC")
         .config("spark.driver.memory", "6g").config("spark.sql.shuffle.partitions", "8")
         .config("spark.sql.warehouse.dir", "/tmp/local_dry_run_warehouse").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")
spark.conf.set("landing_path", DATA)
builtins.spark = spark

expectations = {}


def _dec(kind):
    def outer(*args, **kwargs):
        def inner(fn):
            return fn
        return inner
    return outer


registry = {}


def table(name=None, **kw):
    def inner(fn):
        registry[name] = fn
        return fn
    return inner


def expect_factory(level):
    def outer(name, cond):
        def inner(fn):
            expectations.setdefault(fn.__name__, []).append((level, name, cond))
            return fn
        return inner
    return outer


stub = types.ModuleType("pyspark.pipelines")
stub.table = table
stub.materialized_view = table
stub.expect = expect_factory("warn")
stub.expect_or_drop = expect_factory("drop")
stub.expect_or_fail = expect_factory("fail")
sys.modules["pyspark.pipelines"] = stub
import pyspark
pyspark.pipelines = stub


def load(path):
    spec = importlib.util.spec_from_file_location(path.split("/")[-1][:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


for db in ["bronze", "silver", "gold"]:
    spark.sql(f"DROP DATABASE IF EXISTS {db} CASCADE")
    spark.sql(f"CREATE DATABASE {db}")


def save(df, name):
    t0 = time.time()
    df.write.mode("overwrite").saveAsTable(name)
    n = spark.table(name).count()
    print(f"{name:35s} {n:>10,} rows  {time.time()-t0:5.1f}s", flush=True)


def check_expectations(fn_name, name):
    for level, ename, cond in expectations.get(fn_name, []):
        bad = spark.table(name).where(f"NOT ({cond}) OR ({cond}) IS NULL").count()
        print(f"   expect[{level}] {ename}: {bad:,} violations")


T = f"{REPO}/src/transformations"
bronze = load(f"{T}/bronze/st_raw_checks.py")
raw = (spark.read.schema(bronze.CHECK_SCHEMA).option("multiLine", "true")
       .json(sorted(glob.glob(f"{DATA}/checks/checks_*.json.gz"))))
save(bronze.build_raw_checks(raw), "bronze.st_raw_checks")
check_expectations("st_raw_checks", "bronze.st_raw_checks")

dims = load(f"{T}/bronze/mv_raw_dimensions.py")
for nm in ["mv_raw_locations", "mv_raw_revenue_centers", "mv_raw_employees"]:
    save(getattr(dims, nm)(), f"bronze.{nm}")
print("   employee columns:", spark.table("bronze.mv_raw_employees").columns)

lines = load(f"{T}/silver/st_receipt_lines.py")
src = spark.table("bronze.st_raw_checks")
for nm, fn in [("st_items", lines.build_items), ("st_discounts", lines.build_discounts), ("st_payments", lines.build_payments),
               ("st_voids", lines.build_voids), ("st_taxes", lines.build_taxes)]:
    save(fn(src), f"silver.{nm}")
    check_expectations(nm, f"silver.{nm}")


def run_sql_file(path):
    text = open(path).read()
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    for stmt in [s.strip() for s in text.split(";") if s.strip()]:
        name = re.search(r"MATERIALIZED VIEW\s+(\S+)", stmt).group(1)
        head, query = re.split(r"\n\s*AS\s*\n", stmt, maxsplit=1)
        save(spark.sql(query), name)
        for cname, cond in re.findall(r"CONSTRAINT\s+(\w+)\s+EXPECT\s+\((.*)\)\s*,?\s*$", head, flags=re.M):
            bad = spark.table(name).where(f"NOT ({cond}) OR ({cond}) IS NULL").count()
            print(f"   expect[warn] {cname}: {bad:,} violations")


run_sql_file(f"{T}/silver/mv_dimensions.sql")
run_sql_file(f"{T}/silver/mv_receipt_copies.sql")
run_sql_file(f"{T}/silver/mv_checks.sql")
emp = load(f"{T}/gold/mv_employee_signals.py")
save(spark.sql(emp.employee_signals_sql(lambda k, d: d)), "gold.mv_employee_signals")
check_expectations("mv_employee_signals", "gold.mv_employee_signals")
for f in ["mv_employee_risk_score", "mv_store_risk_score", "mv_daily_store_kpis", "mv_data_quality_summary"]:
    run_sql_file(f"{T}/gold/{f}.sql")

print("\n=== PARITY vs Phase 1 (same days) ===")
q = lambda s: spark.sql(s).collect()[0]
print("raw receipts", q("SELECT count(*) FROM bronze.st_raw_checks")[0])
print("copies", q("SELECT count(*) FROM silver.mv_receipt_copies")[0])
flags = ['flag_unbalanced','flag_no_items','flag_no_payment','flag_giant','flag_long_open','flag_odd_check_id','flag_negative_price','flag_zero_qty_priced','has_void','has_discount','has_walkout','has_self_approved_discount','is_fully_comped','has_refund','has_gift_card_sale','has_tip_over_bill']
r = q("SELECT count(*), round(sum(item_sales),2), round(sum(gross_sales),2), round(sum(void_amount),2), round(sum(tips),2), " + ", ".join(f"count_if({f})" for f in flags) + " FROM silver.mv_checks")
print("clean", tuple(r[:5]))
print(json.dumps(dict(zip(flags, r[5:]))))
for t in ["silver.st_items", "silver.st_payments", "silver.st_voids", "silver.st_discounts"]:
    print(t, q(f"SELECT count(*) FROM {t} JOIN silver.mv_checks USING (dt, location_id, check_id)")[0])

print("\n=== GOLD peek ===")
spark.sql("SELECT count(*) n, count_if(is_eligible) eligible, max(min_sales_bar), max(min_card_payments_bar) FROM gold.mv_employee_signals").show()
spark.sql("SELECT risk_tier, count(*) n, round(avg(risk_score),1) avg_score FROM gold.mv_employee_risk_score GROUP BY 1 ORDER BY 1").show()
spark.sql("SELECT store_name, n_receipts, void_rate, void_vs_chain, risk_score, risk_rank FROM gold.mv_store_risk_score ORDER BY risk_rank LIMIT 8").show(truncate=False)
spark.sql("SELECT dt, raw_receipts, copies_removed, clean_receipts, unreconciled_receipts, pct_balanced, pct_flagged, receipts_with_rescued_data, receipts_date_mismatch FROM gold.mv_data_quality_summary ORDER BY dt").show()
spark.sql("SELECT count(*) FROM (SELECT dt, location_id, check_id FROM silver.mv_checks GROUP BY ALL HAVING count(*) > 1)").show()
