import duckdb, time, sys, os, glob, json, traceback
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]  # repo root (Databricks_challenge/)
ROOT = str(REPO / "Applebees Challenge" / "facts" / "checks" / "brand=rmh")
OUT = str(REPO / "eda_work" / "parquet")
tables = ["checks","items","item_discounts","check_discounts","payments","taxes","voids"]
for t in tables: os.makedirs(f"{OUT}/{t}", exist_ok=True)
files = sorted(glob.glob(f"{ROOT}/dt=*/checks.json"))
if len(sys.argv) > 1: files = [f for f in files if any(a in f for a in sys.argv[1:])]
log = open(REPO / "eda_work" / "scripts" / "convert_log.jsonl", "a")
for f in files:
    dt = f.split("dt=")[1].split("/")[0]
    if all(os.path.exists(f"{OUT}/{t}/{dt}.parquet") for t in tables):
        continue
    t0 = time.time()
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'; SET threads=4; SET temp_directory='/tmp/duck'; SET preserve_insertion_order=false")
    try:
        con.execute(f"CREATE TABLE c AS SELECT * FROM read_json('{f}', format='array', maximum_object_size=200000000, sample_size=-1, hive_partitioning=false)")
        schema = {r[0]: r[1] for r in con.execute("DESCRIBE c").fetchall()}
        n = con.execute("SELECT count(*) FROM c").fetchone()[0]
        D = f"DATE '{dt}'"
        q = {}
        q["checks"] = f"""SELECT {D} AS dt, Id::BIGINT AS check_id, LocationId::BIGINT AS location_id, BusinessDate::DATE AS business_date,
            TableName::VARCHAR AS table_name, OpenTime::VARCHAR AS open_time_raw, CloseTime::VARCHAR AS close_time_raw,
            TrafficCount::DOUBLE AS traffic_count, ServiceCharge::DOUBLE AS service_charge, LoyaltyId::VARCHAR AS loyalty_id,
            RevenueCenterId::BIGINT AS revenue_center_id,
            len(ItemsSold) AS n_items, len(Voids) AS n_voids, len(Payments) AS n_payments, len(Discounts) AS n_check_discounts, len(Tax) AS n_tax
            FROM c"""
        con.execute("""CREATE TABLE it AS SELECT Id AS check_id, LocationId AS location_id, unnest(ItemsSold) AS x,
                       unnest(generate_series(1, len(ItemsSold))) AS line_no FROM c""")
        q["items"] = f"""SELECT {D} AS dt, check_id, location_id, line_no, x.ItemId::BIGINT AS item_id, x.Quantity::DOUBLE AS quantity,
            x.GrossPrice::DOUBLE AS gross_price, x.SoldPrice::DOUBLE AS sold_price, x.EmployeeId::BIGINT AS employee_id,
            x.RevenueCenterId::BIGINT AS revenue_center_id, x.OrderTime::VARCHAR AS order_time_raw, x.Seat::BIGINT AS seat,
            x."Sequence"::BIGINT AS seq, x.ParentSequence::BIGINT AS parent_seq, x.PosSourceId::BIGINT AS pos_source_id,
            x.ItemName::VARCHAR AS item_name, x.ItemPLU::BIGINT AS item_plu, x.ItemMajorCatId::BIGINT AS major_cat_id,
            x.ItemMajorCatName::VARCHAR AS major_cat_name, x.ItemSubCatId::BIGINT AS sub_cat_id, x.ItemSubCatName::VARCHAR AS sub_cat_name,
            len(x.Discounts) AS n_item_discounts FROM it"""
        q["item_discounts"] = f"""SELECT {D} AS dt, check_id, location_id, line_no, d.DiscountId::BIGINT AS discount_id, d.Amount::DOUBLE AS amount,
            d.EmployeeId::BIGINT AS employee_id, d.ManagerId::BIGINT AS manager_id, d.DiscountName::VARCHAR AS discount_name
            FROM (SELECT check_id, location_id, line_no, unnest(x.Discounts) AS d FROM it)"""
        q["check_discounts"] = f"""SELECT {D} AS dt, check_id, location_id, d.DiscountId::BIGINT AS discount_id, d.Amount::DOUBLE AS amount,
            d.EmployeeId::BIGINT AS employee_id, d.ManagerId::BIGINT AS manager_id, d.DiscountName::VARCHAR AS discount_name
            FROM (SELECT Id AS check_id, LocationId AS location_id, unnest(Discounts) AS d FROM c)"""
        q["payments"] = f"""SELECT {D} AS dt, check_id, location_id, p.PaymentCategoryId::BIGINT AS pay_cat_id, p.Amount::DOUBLE AS amount,
            p.Gratuity::DOUBLE AS gratuity, p.EmployeeId::BIGINT AS employee_id, p.PosSourceId::BIGINT AS pos_source_id, p.PayCatNo::BIGINT AS pay_cat_no,
            p.PayCatName::VARCHAR AS pay_cat_name, p.IsCreditCard::BOOLEAN AS is_credit_card, p.IsGiftCard::BOOLEAN AS is_gift_card,
            p.IsGiftCert::BOOLEAN AS is_gift_cert, p.IsPettyCash::BOOLEAN AS is_petty_cash, p.IsNonPOS::BOOLEAN AS is_non_pos, p.IsCashDebit::BOOLEAN AS is_cash_debit
            FROM (SELECT Id AS check_id, LocationId AS location_id, unnest(Payments) AS p FROM c)"""
        q["taxes"] = f"""SELECT {D} AS dt, check_id, location_id, t.TaxCategoryId::BIGINT AS tax_cat_id, t.Amount::DOUBLE AS amount, t.TaxCategoryName::VARCHAR AS tax_cat_name
            FROM (SELECT Id AS check_id, LocationId AS location_id, unnest(Tax) AS t FROM c)"""
        q["voids"] = f"""SELECT {D} AS dt, check_id, location_id, v.ItemId::BIGINT AS item_id, v.Quantity::DOUBLE AS quantity, v.Amount::DOUBLE AS amount,
            v.EmployeeId::BIGINT AS employee_id, v.ManagerId::BIGINT AS manager_id, v.VoidCategoryId::BIGINT AS void_cat_id,
            v.VoidCategoryName::VARCHAR AS void_cat_name, v.ItemName::VARCHAR AS item_name, v.ItemPLU::BIGINT AS item_plu
            FROM (SELECT Id AS check_id, LocationId AS location_id, unnest(Voids) AS v FROM c)"""
        counts = {}
        for t in tables:
            out = f"{OUT}/{t}/{dt}.parquet"
            con.execute(f"COPY ({q[t]}) TO '{out}.tmp' (FORMAT parquet, COMPRESSION zstd)")
            os.replace(out + ".tmp", out)
            counts[t] = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
        log.write(json.dumps({"dt": dt, "ok": True, "n_checks": n, "counts": counts, "secs": round(time.time()-t0,1), "schema": schema}) + "\n")
        print(dt, "ok", round(time.time()-t0,1), counts, flush=True)
    except Exception as e:
        log.write(json.dumps({"dt": dt, "ok": False, "err": str(e)[:2000]}) + "\n")
        print(dt, "ERR", str(e)[:500], flush=True)
    finally:
        con.close(); log.flush()
