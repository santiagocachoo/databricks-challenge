"""
Build eda_work/parquet/check_summary/check_summary.parquet:
one row per receipt with its money totals (item sales, gross, discounts, tax, payments, tips, voids).
Needs: eda_work/parquet/ from convert.py.  Used by: clean.py.  Takes about 30-60 s.
"""
import tempfile
import duckdb
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P = (REPO / "eda_work" / "parquet").as_posix()
OUT = REPO / "eda_work" / "parquet" / "check_summary"
OUT.mkdir(parents=True, exist_ok=True)
DUCK_TMP = (Path(tempfile.gettempdir()) / "duckdb_spill").as_posix()

con = duckdb.connect()
con.execute(f"SET memory_limit='2GB'; SET threads=4; SET temp_directory='{DUCK_TMP}'; SET preserve_insertion_order=false")
for t in ["checks", "items", "item_discounts", "check_discounts", "payments", "taxes", "voids"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{P}/{t}/*.parquet', union_by_name=true)")

K = "USING (dt, location_id, check_id)"
con.execute(f"""COPY (
WITH it AS (SELECT dt, location_id, check_id, sum(sold_price) sold, sum(gross_price*quantity) gross_ext, sum(gross_price) gross FROM items GROUP BY ALL),
cd AS (SELECT dt, location_id, check_id, sum(amount) cdisc FROM check_discounts GROUP BY ALL),
idc AS (SELECT dt, location_id, check_id, sum(amount) idisc FROM item_discounts GROUP BY ALL),
tx AS (SELECT dt, location_id, check_id, sum(amount) tax FROM taxes GROUP BY ALL),
py AS (SELECT dt, location_id, check_id, sum(amount) pay, sum(gratuity) grat FROM payments GROUP BY ALL),
vd AS (SELECT dt, location_id, check_id, sum(amount) void_amt FROM voids GROUP BY ALL)
SELECT c.*, coalesce(sold,0) sold, coalesce(gross,0) gross, coalesce(gross_ext,0) gross_ext, coalesce(cdisc,0) cdisc,
       coalesce(idisc,0) idisc, coalesce(tax,0) tax, coalesce(pay,0) pay, coalesce(grat,0) grat, coalesce(void_amt,0) void_amt
FROM checks c LEFT JOIN it {K} LEFT JOIN cd {K} LEFT JOIN idc {K} LEFT JOIN tx {K} LEFT JOIN py {K} LEFT JOIN vd {K}
) TO '{(OUT / "check_summary.parquet").as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
n, sold = con.execute(f"SELECT count(*), round(sum(sold)) FROM '{(OUT / 'check_summary.parquet').as_posix()}'").fetchone()
print(f"check_summary: {n:,} receipts, item sales ${sold:,.0f}")
