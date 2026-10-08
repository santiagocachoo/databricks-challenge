"""
Step 1 (T5/T6/T7): build the CLEAN layer from the flattened Parquet tables.

Rules:
  - Nothing weird is deleted. Weird receipts get yes/no flag columns instead.
  - The only rows removed are exact copies of another receipt (dup_check.py logic).
  - Original columns are kept next to cleaned ones (e.g. gratuity next to tip).

Run:  python3 eda_work/scripts/clean.py [stage ...]
Stages: labels dups checks lines tables report   (default: all, in order)
Output: eda_work/clean/*.parquet  and  eda_work/reports/*
"""
import tempfile
DUCK_TMP = (__import__("pathlib").Path(tempfile.gettempdir()) / "duckdb_spill").as_posix()  # works on macOS, Linux and Windows
import duckdb, sys, os, json, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
P = REPO / "eda_work" / "parquet"          # flattened raw tables (from convert.py)
CK = P / "check_summary" / "check_summary.parquet"
DIM = REPO / "Applebees Challenge" / "dimensions"
OUT = REPO / "eda_work" / "clean"
REP = REPO / "eda_work" / "reports"
TMP = REPO / "eda_work" / "clean" / "_tmp"
for d in (OUT, REP, TMP): d.mkdir(parents=True, exist_ok=True)

GIANT_LINES = 200          # a receipt with more than 200 lines is not a real meal (p99 = 43 lines)
LONG_OPEN_MIN = 360        # open more than 6 hours

con = duckdb.connect()
con.execute(f"SET memory_limit='2GB'; SET threads=4; SET temp_directory='{DUCK_TMP}'; SET preserve_insertion_order=false")
for t in ["checks", "items", "item_discounts", "check_discounts", "payments", "taxes", "voids"]:
    con.execute(f"CREATE VIEW raw_{t} AS SELECT * FROM read_parquet('{P}/{t}/*.parquet', union_by_name=true)")
con.execute(f"CREATE VIEW raw_ck AS SELECT * FROM '{CK}'")
con.execute(f"CREATE TABLE loc AS SELECT * FROM read_json('{DIM}/locations/locations.json')")
con.execute(f"CREATE TABLE rc AS SELECT * FROM read_json('{DIM}/revenue_centers/revenueCenters.json')")
con.execute(f"CREATE TABLE emp AS SELECT * FROM read_json('{DIM}/employees/employees.json', sample_size=-1, maximum_object_size=100000000)")
KEY = "USING (dt, location_id, check_id)"

def log(msg): print(time.strftime("%H:%M:%S"), msg, flush=True)
def nrows(path): return con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
def save(sql, path): con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet, COMPRESSION zstd)")

# ---------------------------------------------------------------- labels
def stage_labels():
    """Merge spelling variants of the same label. Raw label is always kept."""
    void_map = {"SERVER ERR": "SERV ERR", "NOT RECEVD": "NOT RECVD"}
    void_desc = {"CUST CHANG": "Customer changed order", "WRONG ITEM": "Wrong item rung", "NOT RECVD": "Not received",
                 "TOO MANY": "Too many rung", "OTHER": "Other", "86'D ITEM": "Item out of stock (86'd)",
                 "SERV ERR": "Server error", "WRONG CHK": "Wrong check", "VOIDED": "Voided"}
    rows = [(k, v) for k, v in void_map.items()]
    con.execute("CREATE OR REPLACE TABLE void_map (raw VARCHAR, clean VARCHAR)")
    if rows: con.executemany("INSERT INTO void_map VALUES (?, ?)", rows)
    con.execute("CREATE OR REPLACE TABLE void_desc (clean VARCHAR, description VARCHAR)")
    con.executemany("INSERT INTO void_desc VALUES (?, ?)", list(void_desc.items()))
    # Discounts: same name once spaces, % and letter case are ignored -> same discount.
    # The display name is the most common spelling.
    con.execute("""CREATE OR REPLACE TABLE disc_map AS
        WITH a AS (SELECT discount_name raw, count(*) n FROM (SELECT discount_name FROM raw_item_discounts UNION ALL SELECT discount_name FROM raw_check_discounts) GROUP BY 1),
        k AS (SELECT raw, n, upper(regexp_replace(raw, '[\\s%]', '', 'g')) AS key FROM a)
        SELECT raw, key, first(raw ORDER BY n DESC) OVER (PARTITION BY key) AS clean, n FROM k""")
    con.execute("""CREATE OR REPLACE TABLE pay_map AS SELECT DISTINCT pay_cat_name raw, upper(pay_cat_name) clean,
        CASE WHEN upper(pay_cat_name)='CASH' THEN 'Cash'
             WHEN upper(pay_cat_name) IN ('VISA','MASTERCARD','DISCOVER','AMEX') THEN 'Card'
             WHEN upper(pay_cat_name) LIKE 'OLO%' THEN 'Online card'
             WHEN upper(pay_cat_name)='GIFT CARD' THEN 'Gift card'
             WHEN upper(pay_cat_name)='GC SOLD' THEN 'Gift card sold'
             WHEN upper(pay_cat_name)='HOUSE CHG' THEN 'House charge'
             ELSE 'Delivery app / partner' END AS method_group FROM raw_payments""")
    con.execute("""CREATE OR REPLACE TABLE channel_map AS SELECT Id AS revenue_center_id, Name AS channel,
        CASE WHEN Id=1 THEN 'Dine-in' WHEN Id=2 THEN 'To go' WHEN Id IN (3,4,24,25,26,27) THEN 'Online order'
             WHEN Id=7 THEN 'Catering' WHEN Id IN (6,11,12,13,14,15,17,18,20,21,23) THEN 'Delivery app' ELSE 'Other' END AS channel_group FROM rc""")
    # save the mapping so the team can see every merge
    con.execute(f"""COPY (
        SELECT 'void_reason' kind, raw, clean, NULL::BIGINT n FROM void_map
        UNION ALL SELECT 'discount', raw, clean, n FROM disc_map WHERE raw<>clean
        UNION ALL SELECT 'payment', raw, clean, NULL FROM pay_map WHERE raw<>clean
        ORDER BY 1, 3, 2) TO '{REP}/label_merges.csv' (HEADER)""")
    for t in ["void_map", "void_desc", "disc_map", "pay_map", "channel_map"]:
        save(f"SELECT * FROM {t}", TMP / f"{t}.parquet")
    log(f"labels: {con.execute('SELECT count(*) FROM disc_map WHERE raw<>clean').fetchone()[0]} discount spellings merged")

def load_maps():
    for t in ["void_map", "void_desc", "disc_map", "pay_map", "channel_map"]:
        con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM '{TMP / (t + '.parquet')}'")

# ---------------------------------------------------------------- duplicates
def stage_dups():
    """Look-alike receipts: same date, store, table, open/close minute, channel, line count, payment count,
    sales, payment total and tax. Inside a look-alike group, receipts whose item lines, payments,
    discounts and voids are ALL identical are exact copies: keep the lowest check_id, remove the rest."""
    con.execute("""CREATE OR REPLACE TABLE cand AS
    SELECT dt, location_id, check_id,
      dense_rank() OVER (ORDER BY dt, location_id, table_name, open_time_raw, close_time_raw, revenue_center_id, n_items, n_payments, round(sold,2), round(pay,2), round(tax,2)) AS grp_id,
      count(*) OVER (PARTITION BY dt, location_id, table_name, open_time_raw, close_time_raw, revenue_center_id, n_items, n_payments, round(sold,2), round(pay,2), round(tax,2)) AS grp_n
    FROM raw_ck QUALIFY grp_n > 1""")
    con.execute(f"""CREATE OR REPLACE TABLE dupres AS
    WITH i AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', seq, parent_seq, item_id, quantity, gross_price, sold_price, employee_id, order_time_raw, seat), ';' ORDER BY line_no)) s FROM raw_items SEMI JOIN cand {KEY} GROUP BY ALL),
    p AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', pay_cat_name, amount, gratuity, employee_id), ';' ORDER BY pay_cat_name, amount, gratuity)) s FROM raw_payments SEMI JOIN cand {KEY} GROUP BY ALL),
    d AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', lvl, discount_name, amount, employee_id, manager_id), ';' ORDER BY lvl, discount_name, amount)) s FROM
          (SELECT dt, location_id, check_id, 'i' lvl, discount_name, amount, employee_id, manager_id FROM raw_item_discounts UNION ALL SELECT dt, location_id, check_id, 'c', discount_name, amount, employee_id, manager_id FROM raw_check_discounts) SEMI JOIN cand {KEY} GROUP BY ALL),
    v AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', item_id, amount, void_cat_name, employee_id), ';' ORDER BY item_id, amount)) s FROM raw_voids SEMI JOIN cand {KEY} GROUP BY ALL),
    s AS (SELECT c.*, coalesce(i.s,'')||coalesce(p.s,'')||coalesce(d.s,'')||coalesce(v.s,'') AS content FROM cand c LEFT JOIN i {KEY} LEFT JOIN p {KEY} LEFT JOIN d {KEY} LEFT JOIN v {KEY})
    SELECT dt, location_id, check_id, grp_id, count(*) OVER w AS twin_n, min(check_id) OVER w AS kept_check_id FROM s WINDOW w AS (PARTITION BY grp_id, content)""")
    save("SELECT dt, location_id, check_id, kept_check_id FROM dupres WHERE twin_n>1 AND check_id<>kept_check_id", OUT / "removed_duplicates.parquet")
    save("SELECT * FROM dupres", TMP / "dupres.parquet")
    con.execute(f"COPY (SELECT * FROM '{OUT / 'removed_duplicates.parquet'}' ORDER BY ALL) TO '{REP}/removed_duplicates.csv' (HEADER)")
    r = con.execute("SELECT count(DISTINCT grp_id), count(*), count(*) FILTER (WHERE twin_n>1 AND check_id<>kept_check_id) FROM dupres").fetchone()
    log(f"dups: {r[0]} look-alike groups, {r[1]} receipts, {r[2]} exact copies removed")

# ---------------------------------------------------------------- items (lines)
def stage_lines():
    """One row per item line, with line_type and simple line flags. Exact-copy receipts removed."""
    con.execute(f"CREATE OR REPLACE TABLE removed AS SELECT dt, location_id, check_id FROM '{OUT / 'removed_duplicates.parquet'}'")
    save(f"""SELECT i.dt, i.location_id, i.check_id, i.line_no, i.seq, i.parent_seq, i.seat,
        i.item_id, i.item_name, i.item_plu, i.major_cat_name AS category, i.sub_cat_name AS subcategory,
        CASE WHEN i.parent_seq=0 AND i.gross_price<>0 THEN 'menu item'
             WHEN i.parent_seq=0 AND i.gross_price=0  THEN 'free line'
             WHEN i.parent_seq>0 AND i.gross_price<>0 THEN 'combo part / add-on'
             ELSE 'modifier' END AS line_type,
        (i.parent_seq>0 AND i.gross_price=0) AS is_modifier,
        i.quantity, i.gross_price, i.sold_price, round(i.gross_price - i.sold_price, 2) AS item_discount,
        nullif(i.employee_id, 0) AS employee_id, i.employee_id = 0 AS is_system_line,
        try_strptime(i.order_time_raw, '%Y-%m-%dT%H:%M') AS order_time, i.revenue_center_id, i.pos_source_id,
        (i.quantity = 0) AS flag_zero_qty, (i.sold_price < 0) AS flag_negative_price
      FROM raw_items i ANTI JOIN removed {KEY}""",
         OUT / "items.parquet")
    con.execute(f"""CREATE OR REPLACE TABLE line_agg AS SELECT dt, location_id, check_id,
        count(*) FILTER (WHERE line_type IN ('menu item','combo part / add-on')) AS n_real_items,
        count(*) FILTER (WHERE is_modifier) AS n_modifiers,
        bool_or(flag_negative_price) AS any_negative_price, bool_or(flag_zero_qty AND sold_price<>0) AS any_zero_qty_priced
      FROM '{OUT / 'items.parquet'}' GROUP BY ALL""")
    save("SELECT * FROM line_agg", TMP / "line_agg.parquet")
    log(f"lines: {nrows(OUT / 'items.parquet'):,} item lines written")

# ---------------------------------------------------------------- other child tables
def stage_tables():
    load_maps()
    con.execute(f"CREATE OR REPLACE TABLE removed AS SELECT dt, location_id, check_id FROM '{OUT / 'removed_duplicates.parquet'}'")
    # voids
    save(f"""SELECT v.dt, v.location_id, v.check_id, v.item_id, v.item_name, v.quantity, v.amount,
        v.void_cat_name AS void_reason_raw, coalesce(m.clean, v.void_cat_name) AS void_reason, d.description AS void_reason_desc,
        nullif(v.employee_id,0) AS employee_id, nullif(v.manager_id,0) AS manager_id,
        (v.manager_id = v.employee_id) AS is_self_approved, (v.amount = 0) AS is_zero_amount
      FROM raw_voids v ANTI JOIN removed {KEY} LEFT JOIN void_map m ON m.raw=v.void_cat_name LEFT JOIN void_desc d ON d.clean=coalesce(m.clean, v.void_cat_name)""",
         OUT / "voids.parquet")
    # discounts: item-level and check-level in one table
    save(f"""SELECT x.*, dm.clean AS discount_name, (x.manager_id = x.employee_id) AS is_self_approved,
        (x.manager_id IS NULL) AS no_manager, (dm.clean = 'WALKOUT') AS is_walkout, (x.amount = 0) AS is_zero_amount
      FROM (SELECT dt, location_id, check_id, 'item' AS level, line_no, discount_id, discount_name AS discount_name_raw, amount,
                   nullif(employee_id,0) employee_id, nullif(manager_id,0) manager_id FROM raw_item_discounts
            UNION ALL
            SELECT dt, location_id, check_id, 'check', NULL, discount_id, discount_name, amount, nullif(employee_id,0), nullif(manager_id,0) FROM raw_check_discounts) x
      ANTI JOIN removed {KEY} LEFT JOIN disc_map dm ON dm.raw = x.discount_name_raw""", OUT / "discounts.parquet")
    # payments
    save(f"""SELECT p.dt, p.location_id, p.check_id, p.pay_cat_name AS method_raw, pm.clean AS method, pm.method_group,
        p.amount, p.gratuity, (0 - p.gratuity) AS tip, round(p.amount + p.gratuity, 2) AS amount_before_tip,
        CASE WHEN p.amount + p.gratuity > 0 THEN round(-p.gratuity / (p.amount + p.gratuity), 4) END AS tip_pct,
        nullif(p.employee_id,0) AS employee_id, p.is_credit_card, p.is_gift_card,
        (pm.method_group='Gift card sold') AS is_gift_card_sale,
        (p.amount < 0 AND pm.method_group<>'Gift card sold') AS is_refund,
        (p.amount + p.gratuity > 0 AND -p.gratuity > p.amount + p.gratuity) AS is_tip_over_bill
      FROM raw_payments p ANTI JOIN removed {KEY} LEFT JOIN pay_map pm ON pm.raw = p.pay_cat_name""", OUT / "payments.parquet")
    save(f"SELECT dt, location_id, check_id, tax_cat_id, tax_cat_name, amount FROM raw_taxes ANTI JOIN removed {KEY}", OUT / "taxes.parquet")
    # dimensions
    save("""SELECT l.Id AS location_id, l.Name AS store_name, l.OpenDate AS open_date, l.ClosedDate AS closed_date,
        l.Id IN (SELECT DISTINCT location_id FROM raw_checks) AS active_in_data,
        (SELECT count(DISTINCT dt) FROM raw_checks c WHERE c.location_id=l.Id) AS days_with_sales FROM loc l""", OUT / "stores.parquet")
    save("SELECT * FROM channel_map", OUT / "channels.parquet")
    # employees WITHOUT personal data (no names, birth dates or payroll ids)
    save("""SELECT Id AS employee_id, LocationId AS home_store_id, PrimaryJobID AS primary_job_id, JobID AS job_ids,
        Deleted AS is_deleted_in_hr, Borrowed AS is_borrowed, HireDate AS hire_date, IsMinor AS is_minor,
        Id IN (SELECT DISTINCT employee_id FROM raw_items) AS rings_sales FROM emp""", OUT / "employees.parquet")
    log("tables: voids, discounts, payments, taxes, stores, channels, employees written")

# ---------------------------------------------------------------- checks
def stage_checks():
    load_maps()
    con.execute(f"CREATE OR REPLACE TABLE removed AS SELECT dt, location_id, check_id FROM '{OUT / 'removed_duplicates.parquet'}'")
    con.execute(f"CREATE OR REPLACE TABLE line_agg AS SELECT * FROM '{TMP / 'line_agg.parquet'}'")
    con.execute(f"CREATE OR REPLACE TABLE dupres AS SELECT * FROM '{TMP / 'dupres.parquet'}'")
    con.execute(f"""CREATE OR REPLACE TABLE pay_agg AS SELECT dt, location_id, check_id,
        sum(amount) FILTER (WHERE method_group='Cash') AS cash_paid, bool_or(is_refund) AS any_refund,
        bool_or(is_gift_card_sale) AS any_gift_card_sale, bool_or(is_tip_over_bill) AS any_tip_over_bill
      FROM '{OUT / 'payments.parquet'}' GROUP BY ALL""")
    con.execute(f"""CREATE OR REPLACE TABLE disc_agg AS SELECT dt, location_id, check_id,
        bool_or(is_walkout) AS any_walkout, bool_or(is_self_approved) AS any_self_approved_discount
      FROM '{OUT / 'discounts.parquet'}' WHERE amount<>0 GROUP BY ALL""")
    save(f"""SELECT c.dt, weekday(c.dt) AS weekday_num, dayname(c.dt) AS weekday, c.location_id, s.Name AS store_name, c.check_id,
        c.table_name, strptime(c.open_time_raw,'%Y-%m-%dT%H:%M') AS open_time, strptime(c.close_time_raw,'%Y-%m-%dT%H:%M') AS close_time,
        hour(strptime(c.open_time_raw,'%Y-%m-%dT%H:%M')) AS open_hour,
        date_diff('minute', strptime(c.open_time_raw,'%Y-%m-%dT%H:%M'), strptime(c.close_time_raw,'%Y-%m-%dT%H:%M')) AS duration_min,
        c.revenue_center_id, ch.channel, ch.channel_group, c.traffic_count AS guests,
        c.n_items AS n_lines, coalesce(la.n_real_items,0) AS n_real_items, coalesce(la.n_modifiers,0) AS n_modifiers,
        c.n_voids, c.n_payments, c.n_check_discounts,
        round(c.gross_ext,2) AS gross_sales, round(c.idisc,2) AS item_discounts, round(c.sold,2) AS item_sales,
        round(c.cdisc,2) AS check_discounts, round(c.sold - c.cdisc,2) AS net_sales, round(c.tax,2) AS tax,
        round(c.sold - c.cdisc + c.tax,2) AS amount_due, round(c.pay,2) AS amount_paid, round(0 - c.grat, 2) + 0.0 AS tips,
        round(coalesce(pa.cash_paid,0),2) AS cash_paid, round(c.void_amt,2) AS void_amount,
        -- behaviour (risk levers, not errors)
        (c.n_voids > 0) AS has_void, (c.idisc + c.cdisc > 0) AS has_discount, coalesce(da.any_walkout,false) AS has_walkout,
        coalesce(da.any_self_approved_discount,false) AS has_self_approved_discount,
        (c.gross_ext > 0 AND c.sold - c.cdisc <= 0.005) AS is_fully_comped,
        coalesce(pa.any_refund,false) AS has_refund, coalesce(pa.any_gift_card_sale,false) AS has_gift_card_sale,
        coalesce(pa.any_tip_over_bill,false) AS has_tip_over_bill,
        -- context (normal, but good to know)
        (date_diff('minute', strptime(c.open_time_raw,'%Y-%m-%dT%H:%M'), strptime(c.close_time_raw,'%Y-%m-%dT%H:%M')) = 0) AS is_instant,
        (strptime(c.open_time_raw,'%Y-%m-%dT%H:%M')::DATE > c.dt) AS is_after_midnight,
        (c.traffic_count = 0) AS is_zero_guests, (c.traffic_count <> floor(c.traffic_count)) AS is_split_guests,
        (d.grp_id IS NOT NULL) AS is_lookalike_split,
        -- data-quality flags (kept, never deleted)
        (abs((c.pay + c.grat) - (c.sold - c.cdisc + c.tax)) >= 0.015) AS flag_unbalanced,
        (c.n_items = 0) AS flag_no_items, (c.n_payments = 0) AS flag_no_payment,
        (c.n_items > {GIANT_LINES}) AS flag_giant,
        (date_diff('minute', strptime(c.open_time_raw,'%Y-%m-%dT%H:%M'), strptime(c.close_time_raw,'%Y-%m-%dT%H:%M')) > {LONG_OPEN_MIN}) AS flag_long_open,
        (c.check_id <= 0 OR c.check_id > 10000000) AS flag_odd_check_id,
        coalesce(la.any_negative_price,false) AS flag_negative_price,
        coalesce(la.any_zero_qty_priced,false) AS flag_zero_qty_priced
      FROM raw_ck c ANTI JOIN removed {KEY}
      LEFT JOIN loc s ON s.Id = c.location_id LEFT JOIN channel_map ch ON ch.revenue_center_id = c.revenue_center_id
      LEFT JOIN line_agg la {KEY} LEFT JOIN pay_agg pa {KEY} LEFT JOIN disc_agg da {KEY}
      LEFT JOIN (SELECT DISTINCT dt, location_id, check_id, grp_id FROM dupres) d {KEY}
      ORDER BY c.dt, c.location_id, c.check_id""", OUT / "checks.parquet")
    log(f"checks: {nrows(OUT / 'checks.parquet'):,} receipts written")

# ---------------------------------------------------------------- report
def stage_report():
    # 1) missing / zero values per column of the RAW tables (what we found before cleaning)
    rows = []
    for t in ["checks", "items", "payments", "voids", "item_discounts", "check_discounts", "taxes"]:
        cols = con.execute(f"DESCRIBE raw_{t}").fetchall()
        exprs = ["count(*)"]
        for name, typ, *_ in cols:
            q = f'"{name}"'
            zero = f"count(*) FILTER (WHERE {q} = 0)" if any(k in typ for k in ("INT", "DOUBLE", "DECIMAL")) else \
                   (f"count(*) FILTER (WHERE trim({q}) = '')" if "VARCHAR" in typ else "NULL")
            exprs += [f"count(*) FILTER (WHERE {q} IS NULL)", zero]
        r = con.execute(f"SELECT {', '.join(exprs)} FROM raw_{t}").fetchone()
        n = r[0]
        for i, (name, typ, *_) in enumerate(cols):
            nul, zer = r[1 + 2 * i], r[2 + 2 * i]
            rows.append((t, name, typ, n, nul, round(100 * nul / n, 2), zer, None if zer is None else round(100 * zer / n, 2)))
    for name, src in [("employees (HR file)", "emp"), ("locations", "loc")]:
        cols = con.execute(f"DESCRIBE {src}").fetchall()
        n = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
        for c, typ, *_ in cols:
            nul = con.execute(f'SELECT count(*) FILTER (WHERE "{c}" IS NULL) FROM {src}').fetchone()[0]
            rows.append((name, c, typ, n, nul, round(100 * nul / n, 2), None, None))
    con.execute("CREATE OR REPLACE TABLE mv (table_name VARCHAR, column_name VARCHAR, type VARCHAR, n_rows BIGINT, n_null BIGINT, pct_null DOUBLE, n_zero_or_blank BIGINT, pct_zero_or_blank DOUBLE)")
    con.executemany("INSERT INTO mv VALUES (?,?,?,?,?,?,?,?)", rows)
    con.execute(f"COPY mv TO '{REP}/missing_values.csv' (HEADER)")

    # 2) funnel + flag counts on the CLEAN checks
    c = f"read_parquet('{OUT / 'checks.parquet'}')"
    raw_n = con.execute("SELECT count(*) FROM raw_ck").fetchone()[0]
    removed = con.execute(f"SELECT count(*) FROM '{OUT / 'removed_duplicates.parquet'}'").fetchone()[0]
    flags = ["flag_unbalanced", "flag_no_items", "flag_no_payment", "flag_giant", "flag_long_open", "flag_odd_check_id", "flag_negative_price", "flag_zero_qty_priced"]
    behav = ["has_void", "has_discount", "has_walkout", "has_self_approved_discount", "is_fully_comped", "has_refund", "has_gift_card_sale", "has_tip_over_bill"]
    ctx = ["is_instant", "is_after_midnight", "is_zero_guests", "is_split_guests", "is_lookalike_split"]
    allc = flags + behav + ctx
    r = con.execute(f"SELECT count(*), {', '.join(f'count(*) FILTER (WHERE {f})' for f in allc)}, count(*) FILTER (WHERE {' OR '.join(flags)}) FROM {c}").fetchone()
    clean_n, counts, any_flag = r[0], dict(zip(allc, r[1:-1])), r[-1]
    dup = con.execute(f"SELECT count(DISTINCT grp_id), count(*) FROM '{TMP / 'dupres.parquet'}'").fetchone()
    money = con.execute(f"SELECT round(sum(sold),2) FROM raw_ck JOIN '{OUT / 'removed_duplicates.parquet'}' {KEY}").fetchone()[0]
    summary = {"raw_receipts": raw_n, "lookalike_groups": dup[0], "lookalike_receipts": dup[1],
               "exact_copies_removed": removed, "exact_copies_sales_usd": money, "clean_receipts": clean_n,
               "receipts_with_any_data_quality_flag": any_flag, "receipts_clean_and_unflagged": clean_n - any_flag,
               "data_quality_flags": {k: counts[k] for k in flags}, "behaviour_flags": {k: counts[k] for k in behav},
               "context_flags": {k: counts[k] for k in ctx},
               "columns_dropped": ["checks.loyalty_id (100% empty)", "checks.service_charge (always 0)", "employees.IsEmancipated (100% empty)",
                                   "employees: Name, DateOfBirth, LocationEmployeeId, PayrollEmployeeId, AlternateEmployeeId (privacy)"],
               "thresholds": {"giant_lines_gt": GIANT_LINES, "long_open_minutes_gt": LONG_OPEN_MIN}}
    (REP / "cleaning_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    log("report: " + json.dumps({k: summary[k] for k in ["raw_receipts", "exact_copies_removed", "clean_receipts", "receipts_with_any_data_quality_flag"]}))
    print(json.dumps(summary, indent=1, default=str))

STAGES = {"labels": stage_labels, "dups": stage_dups, "lines": stage_lines, "tables": stage_tables, "checks": stage_checks, "report": stage_report}
for s in (sys.argv[1:] or list(STAGES)):
    t0 = time.time(); STAGES[s](); log(f"stage {s} done in {time.time()-t0:.0f}s")
