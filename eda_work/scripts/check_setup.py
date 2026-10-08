"""
Checks that your machine is ready. Run from anywhere:  python3 eda_work/scripts/check_setup.py
It never changes anything; it only prints OK / MISSING and what to do next.
"""
import sys, importlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "Applebees Challenge"
status = {"python": True, "raw": True, "built": True}
section = "python"
def report(good, msg, fix=""):
    status[section] &= good
    print(("  OK       " if good else "  MISSING  ") + msg + ("" if good or not fix else f"\n           -> {fix}"))

print(f"Repo folder: {REPO}\n\n1) Python and libraries")
report(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]} (need 3.9 or newer)", "install Python 3.10+ from python.org")
for pkg in ["duckdb", "pandas", "pyarrow", "matplotlib"]:
    try:
        m = importlib.import_module(pkg); report(True, f"{pkg} {getattr(m, '__version__', '')}")
    except ImportError:
        report(False, pkg, "activate the virtual environment, then: pip install -r requirements.txt")

section = "raw"
print("\n2) Raw data (needed only to rebuild; not needed if you got eda_work/clean/ from a teammate)")
dims = ["locations/locations.json", "revenue_centers/revenueCenters.json", "items/items.json", "employees/employees.json"]
days = sorted((RAW / "facts" / "checks" / "brand=rmh").glob("dt=*/checks.json")) if RAW.exists() else []
report(RAW.is_dir(), f'folder "{RAW.name}" at the repo root', 'put the dataset folder here and name it exactly: Applebees Challenge')
for d in dims:
    report((RAW / "dimensions" / d).is_file(), f"dimensions/{d}")
report(len(days) == 115, f"{len(days)} of 115 daily files (facts/checks/brand=rmh/dt=YYYY-MM-DD/checks.json)")

section = "built"
print("\n3) Built data")
pq = REPO / "eda_work" / "parquet"
n_pq = len(list((pq / "items").glob("*.parquet"))) if pq.exists() else 0
report(n_pq == 115, f"eda_work/parquet: {n_pq} of 115 days converted", "python3 eda_work/scripts/build_all.py")
report((pq / "check_summary" / "check_summary.parquet").is_file(), "eda_work/parquet/check_summary", "python3 eda_work/scripts/build_all.py")
clean = ["checks", "items", "discounts", "voids", "payments", "taxes", "stores", "channels", "employees"]
missing = [c for c in clean if not (REPO / "eda_work" / "clean" / f"{c}.parquet").is_file()]
report(not missing, "eda_work/clean: " + ("all 9 tables" if not missing else "missing " + ", ".join(missing)),
       "get eda_work/clean/ from a teammate, or run: python3 eda_work/scripts/build_all.py")

print()
if not status["python"]:
    print("NOT READY - fix section 1 first (libraries).")
elif status["built"]:
    print("ALL GOOD - you can analyze eda_work/clean/." + ("" if status["raw"] else
          "\n(Raw data is not here, so you cannot rebuild. That is fine for analysis.)"))
elif status["raw"]:
    print("ALMOST - raw data is in place. Now run:  python eda_work/scripts/build_all.py")
else:
    print("NOT READY - you need either the clean tables from a teammate (section 3) or the raw data (section 2). See README step 3.")
