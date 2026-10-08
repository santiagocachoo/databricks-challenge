import duckdb, sys, os
con = duckdb.connect()
con.execute("SET memory_limit='2GB'; SET threads=4; SET temp_directory='/tmp/duck'")
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]  # repo root (Databricks_challenge/)
P = str(REPO / "eda_work" / "parquet")
CK = f"{P}/check_summary/check_summary.parquet"  # one row per check with totals (built by p4.py)
for t in ["checks","items","item_discounts","check_discounts","payments","taxes","voids"]:  # check_summary is read separately via CK
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{P}/{t}/*.parquet', union_by_name=true)")
D = str(REPO / "Applebees Challenge" / "dimensions")
con.execute(f"CREATE TABLE loc AS SELECT * FROM read_json('{D}/locations/locations.json')")
con.execute(f"CREATE TABLE rc AS SELECT * FROM read_json('{D}/revenue_centers/revenueCenters.json')")
con.execute(f"CREATE TABLE itm AS SELECT * FROM read_json('{D}/items/items.json', sample_size=-1)")
con.execute(f"CREATE TABLE emp AS SELECT * FROM read_json('{D}/employees/employees.json', sample_size=-1, maximum_object_size=100000000)")
def show(title, sql, n=60):
    print(f"\n## {title}")
    r = con.execute(sql); cols=[d[0] for d in r.description]; rows=r.fetchmany(n)
    print(" | ".join(cols))
    for row in rows: print(" | ".join(str(round(v,2)) if isinstance(v,float) else str(v) for v in row))
import os
exec(open(sys.argv[1]).read())
