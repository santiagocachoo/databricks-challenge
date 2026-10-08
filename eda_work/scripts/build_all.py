"""
Rebuild everything from the raw data, in order:
  1. convert.py              raw JSON  -> eda_work/parquet/<table>/<date>.parquet   (~4-6 min the first time; skips days already done)
  2. build_check_summary.py  -> eda_work/parquet/check_summary/check_summary.parquet (~1 min)
  3. clean.py                -> eda_work/clean/*.parquet and eda_work/reports/*      (~30 s)
Run from anywhere:  python3 eda_work/scripts/build_all.py
"""
import subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
steps = ["convert.py", "build_check_summary.py", "clean.py"]
for s in steps:
    t0 = time.time()
    print(f"\n=== {s} ===", flush=True)
    r = subprocess.run([sys.executable, str(HERE / s)])
    if r.returncode != 0:
        sys.exit(f"\nSTOPPED: {s} failed (exit code {r.returncode}). Fix the error above, then run build_all.py again.")
    print(f"=== {s} finished in {time.time() - t0:.0f} s ===", flush=True)
print("\nAll done. Use the tables in eda_work/clean/ for analysis.")
