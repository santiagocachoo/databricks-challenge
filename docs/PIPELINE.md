# How the pipeline works, and why

This is the explainer for Phase 2: what each stage does, why we built it that way, and what each table is worth. If you only have 10 minutes, read sections 1, 2 and 6.

Contents:
1. The problem and the data
2. The flow in one picture
3. Bronze: getting the raw data in
4. Silver: cleaning and structuring
5. Gold: business-ready tables
6. Data quality: every check, by dimension
7. The job: trigger, dependencies, failures and reruns
8. Databricks features: what we used, where, and why
9. Proof that the port is correct (parity with Phase 1)
10. Results of the Databricks runs (Oct 28, 2026): 14-day demo and full 115-day run
11. Limits and what we would do next
12. Questions we expect, with answers

---

## 1. The problem and the data

- **Business question:** where can money leak at the register (voids, discounts, comps, walkouts, tips, refunds), and **who** and **where** should a manager review first?
- **Data:** point-of-sale (POS) receipts from 127 RMH Applebee's restaurants, Apr 28 – Aug 20, 2026 (115 days, 2.1M receipts, 28.6M item lines, 11 GB of JSON). One JSON file per day; each receipt nests its item lines, discounts, payments, taxes and voids. Plus lookup files: stores, sales channels (revenue centers), employees (HR file with personal data).
- **No fraud labels.** Nothing says "this was fraud". The pipeline produces **risk signals** and a **risk score**: a reason to look, not proof.
- **Phase 1 finding the pipeline is built around:** risk is about *who* and *where*, not *when*. Void rates barely move by hour or weekday (0.8–0.9%) but range 0.3–2.3% across stores and 0–7.9% across employees, and the signals stack up on the same employees (106 were top 10% on 3+ of 5 signals vs ~22 by chance).

**What we loaded:** two Databricks Free Edition workspaces, same code. **Demo workspace:** May 4–10, 2026 (7 days, includes Mother's Day), then May 11–17 to show incremental loading. **Full workspace** (a teammate's account, deployed with `databricks bundle deploy -t full`): all **115 days, 2,142,846 receipts**, so the demo workspace keeps its daily compute quota. The analysis numbers come from the full run.

## 2. The flow in one picture

```
 Volume bronze.landing                BRONZE                 SILVER                          GOLD
 checks/checks_YYYY-MM-DD.json.gz ──► st_raw_checks ──┬──► st_items, st_discounts,  ──┐
   (1 file per business day)          (Auto Loader)   │     st_payments, st_voids,     │
                                                      │     st_taxes   (streaming)     ├──► mv_checks ──┬──► mv_employee_signals ──► mv_employee_risk_score
                                                      ├──► mv_receipt_copies ──────────┤   (1 row per  ├──► mv_store_risk_score
 dimensions/*.json.gz ──────────────► mv_raw_*  ─────────► mv_stores, mv_channels, ─────┘    receipt)   ├──► mv_daily_store_kpis
   (stores, channels, employees)      (no personal data)    mv_employees                                └──► mv_data_quality_summary
                                                                                                                │
 JOB: refresh_pipeline (all of the above) ──────────────────────────────────────────────────────► quality_gate ◄┘
```

Naming: `st_` = streaming table, `mv_` = materialized view, schema = layer (`bronze`, `silver`, `gold`).

## 3. Bronze: getting the raw data in

**`bronze.st_raw_checks`** (`src/transformations/bronze/st_raw_checks.py`)

| Decision | Why |
|---|---|
| **Auto Loader, streaming table** | Each run reads only the day files that arrived since the last run (Auto Loader checkpoints the files it has seen). Day 116 costs one day of compute, not 116. |
| **Triggered, not continuous** | Files arrive once a day. A continuously running stream would burn compute 24/7 for one file a day. |
| **Explicit schema** (schema-on-read contract) | The JSON is deeply nested. Declaring the schema means types never drift between files, and the contract is written down. Anything off-contract is kept in `_rescued_data` instead of breaking the load or being lost. |
| **Gzipped files** | 11 GB of JSON compresses ~16× (a day goes from ~100 MB to ~6 MB). Spark reads `.json.gz` directly. |
| **Business day from the file name** (`dt`) | Same as Phase 1 (folder `dt=`). A WARN expectation checks it against the receipt's own BusinessDate. |
| **One row per receipt, nested lines kept** | Bronze = exactly what arrived. Silver flattens it. If a cleaning rule changes, silver can be rebuilt from bronze without re-uploading anything. |
| **`content_hash`** | SHA-256 of the whole receipt except its number. Two receipts with the same day, store and hash are exact copies (used in silver). |
| **Metadata columns** | `source_file`, `ingested_at`: every row can be traced back to its file and load time (lineage). |
| **Liquid clustering on `(dt, LocationId)`** | Our queries filter by day and store. |

**Expectations, all three levels used on purpose:**

| Level | Rule | Why this level |
|---|---|---|
| FAIL (stop the update) | `day_readable_from_file_name`: dt IS NOT NULL | A file we cannot date breaks the feed contract; better to stop than load undated data. |
| DROP (remove the row, count it) | `receipt_key_present`: Id and LocationId present | A receipt we cannot identify cannot be joined or audited. |
| WARN (keep, count) | `business_date_matches_file_day`, `fits_schema_contract` | Worth monitoring, not worth losing data over. |

**Lookup files** (`bronze/mv_raw_dimensions.py`): `mv_raw_locations`, `mv_raw_revenue_centers`, `mv_raw_employees` are materialized views, because a lookup file is a full snapshot that is replaced when it changes (a streaming table would append the same rows again).

**Privacy by design:** the HR file contains names, birth dates and payroll / location employee IDs. The employee schema simply does not declare those fields, so Spark never parses them and **they exist in no table, not even bronze**. The quality gate re-checks this on every run.

## 4. Silver: cleaning and structuring

All rules are ported from Phase 1 (`phase1_eda/scripts/convert.py`, `clean.py`), where they were decided and documented.

**`silver.st_items / st_discounts / st_payments / st_voids / st_taxes`** (`silver/st_receipt_lines.py`): streaming tables that flatten the nested arrays (row-by-row work on an append-only source, so streaming fits).

| Transformation | Why |
|---|---|
| Explode nested arrays into one table per line type; keep `line_no` | Analysis happens at line level (who voided which item, which discount, which tip). |
| `line_type`: menu item / combo part / free line / modifier | 67% of item lines are $0. A modifier is a child line with a $0 price; combo dishes are priced children, so `parent_seq > 0` alone is wrong. |
| Employee / manager id 0 → NULL | 0 means "system", not a person; otherwise "employee 0" would look like the busiest employee. |
| Times as text → timestamps (`try_to_timestamp`) | Needed for hour, duration, after-midnight. `try_` returns NULL instead of crashing; an expectation counts any NULL. |
| Tips made positive (`tip = −gratuity`), `tip_pct`, `is_tip_over_bill` | The raw gratuity is negative because the card charge includes the tip. |
| Payment methods grouped (Cash, Card, Online card, Gift card, …) | Cash share and card-only tip signals. |
| Void reason spellings merged (`SERVER ERR` → `SERV ERR`, `NOT RECEVD` → `NOT RECVD`) | Same reason, different spelling. Raw value kept next to it. |
| Discount names compared ignoring case, spaces and `%`; `is_walkout` | "WALKOUT", "Walk out" and "walkout%" are the same discount. |
| `is_self_approved` (manager = employee) | A discount approved by the same person who gave it is a control gap. |

**`silver.mv_receipt_copies`**: 0.01% of receipts (229 of 2.14M in Phase 1; 12 in May 4–10) are exact copies of another receipt: same day, store and content, only the receipt number differs. They look like the POS saving the same check twice. We keep the lowest receipt number and list every removed copy here. This is the only deletion in the whole pipeline, and it is audited.

**`silver.mv_checks`** (`silver/mv_checks.sql`): **the** clean receipt table, one row per real receipt.

- Money: gross sales, item and check discounts, net sales, tax, amount due, amount paid, tips, cash, void amount.
- **8 data-quality flags** (`flag_*`): unbalanced money identity, no items, no payment, giant receipt (>200 lines), open > 6 hours, odd check id, negative price, priced line with quantity 0.
- **8 risk-behavior flags**: has_void, has_discount, has_walkout, has_self_approved_discount, is_fully_comped, has_refund, has_gift_card_sale, has_tip_over_bill.
- **4 context flags**: is_instant, is_after_midnight, is_zero_guests, is_split_guests (normal situations that explain odd-looking receipts).
- Every data-quality flag is also a **WARN expectation**, so each update reports how many receipts broke each rule without dropping them. In fraud work the odd receipts are the evidence; deleting them would delete the signal.
- Liquid clustering on `(dt, location_id)`.

**`silver.mv_stores / mv_channels / mv_employees`**: clean lookups (channel grouping as in Phase 1: Dine-in, To go, Online order, Delivery app, Catering).

## 5. Gold: business-ready tables

| Table | What it answers | How |
|---|---|---|
| `mv_employee_signals` | How does each employee behave at the register? | 6 signals as **rates**: void $ / gross sales, discount $ / gross sales, walkouts per receipt, comps per receipt, cash share, card tips over the bill per card payment. Rates, so busy employees don't look worse for being busy. |
| `mv_employee_risk_score` | **Who should a manager review first?** | Among eligible employees: percentile on each of 5 signals (void, discount, walkout, comp, tips over bill), averaged → **0–100 risk score**. Plus how many signals put the employee in the top 10%, and a tier: *review first* (3+), *watch* (2), *normal*. Explainable: every point of the score traces back to a rate. |
| `mv_store_risk_score` | **Where should an auditor look first?** | Same signals per restaurant, each divided by the chain median (`void_vs_chain` = 2.0 means twice the typical store), and a 0–100 score. |
| `mv_daily_store_kpis` | How did each store do each day? | Receipts, guests, sales, discounts, voids, walkouts, comps, tips and rates per store per day. Feeds the dashboard. |
| `mv_data_quality_summary` | Can we trust today's data? | Per day: raw vs clean receipts, copies removed, unreconciled count (must be 0), % balanced, every flag count, rescued rows. |
| `quality_gate_results` | Did the last runs pass? | Written by the job's quality gate: one row per check per run. |

**Eligibility.** Phase 1 compared employees with $5,000+ in sales and 50+ card payments over 115 days; below that, one $30 void on $300 of sales is a 10% void rate. Gold scales the same bar per day to the days loaded (7 days → $304 and 4 card payments), so the table is right for 7 days or 115. With only 7 days, rates are noisier than in Phase 1; the score gets more reliable as days are added.

**Why the score is simple (average of percentiles) and not a model:** there are no labels to train or validate a model against. A transparent score that a manager can read ("top 10% on voids, walkouts and discounts") is more useful and more honest than a black box. Cash share is left out of the score because it mostly reflects the role (bartenders handle cash) and we have no job-role lookup.

## 6. Data quality: every check, by dimension

Two layers of checks: **expectations** inside the pipeline check each row as it is written; the **quality gate** (job task 2) checks things a single row cannot show.

| Dimension | Check | Where | Action |
|---|---|---|---|
| Completeness | Receipt has Id and store | bronze expectation | DROP + count |
| Completeness | Every day in bronze reached silver | quality gate | fail job |
| Completeness | No receipt without day, store or number | quality gate | fail job |
| Completeness | ≥ 99.9% of receipts from a known store; known channel | silver expectations + gate | warn / fail job |
| Completeness | Missing values per column | Phase 1 report (`phase1_eda/reports/missing_values.csv`) | led to dropping 100%-empty columns |
| Uniqueness | Exact-copy receipts (same day, store, content) | `mv_receipt_copies` | removed, listed |
| Uniqueness | No duplicate receipt key (dt + store + check) in silver | quality gate | fail job |
| Consistency | raw receipts = clean receipts + copies, every day | `mv_data_quality_summary` + gate | fail job if ≠ 0 |
| Consistency | Business date = file date | bronze expectation | warn |
| Validity / types | Schema contract; off-contract data rescued | bronze (explicit schema + `_rescued_data`) | warn + gate fails if any |
| Validity / formats | Times parse; close ≥ open | silver expectations | warn |
| Validity | Negative prices, zero-quantity priced lines, giant receipts, open > 6 h, odd check ids | silver flags + expectations | flag + warn |
| Validity | Share of flagged receipts ≤ 5% (Phase 1: 2.0%) | quality gate | fail job |
| Accuracy | Money identity: paid + gratuity = item sales − check discounts + tax | `flag_unbalanced` + gate (≥ 99.9%; Phase 1: 99.996%) | flag + fail job if below |
| Accuracy | Same numbers as the independent Phase 1 implementation | `local_dry_run.py` (section 9) | done before deploy |
| Privacy | No name / birth / payroll columns in any schema | bronze schema + quality gate | fail job |

Where to see the results: pipeline UI (each table shows its expectations and violation counts), `gold.mv_data_quality_summary`, `gold.quality_gate_results`.

Results (Databricks, May 4–17): 276,695 raw receipts → 24 copies removed → 276,671 clean, 0 unreconciled on every day, 0 rescued rows, 99.97–100% balanced per day, 1.75–2.25% flagged per day; quality gate 12 of 12. Full detail in section 10. Local dry run on May 4–10: 140,208 raw receipts → 12 copies removed → 140,196 clean; 0 unreconciled; 0 rescued rows; 0 date mismatches; 99.998% balanced (3 unbalanced); 1.9–2.3% of receipts flagged per day (most common: priced lines with quantity 0, 1,118; no items, 831; open > 6 h, 600).

## 7. The job: trigger, dependencies, failures and reruns

`resources/jobs/daily_orchestration_job.yml`:

```
refresh_pipeline  ──►  quality_gate
```

| Topic | Decision |
|---|---|
| **Trigger** | Schedule: every day 06:00 Monterrey time, after the previous business day's file lands. Deployed **paused** (Free Edition compute quota); runs on demand with `databricks bundle run`. Alternative considered: a *file arrival* trigger on the landing volume (runs as soon as a file lands). |
| **Dependencies** | `quality_gate` runs only if `refresh_pipeline` succeeds. Inside the pipeline, Databricks works out the table order from the code (bronze → silver → gold) and runs independent tables in parallel. |
| **Failures** | `refresh_pipeline` retries once after 5 minutes (transient errors). `quality_gate` never retries: a failed check needs a person. Any failure e-mails the job owner. Timeouts: 1 h per task, 2 h per job. Max 1 concurrent run, so two runs never write the same tables. |
| **Reruns** | Safe by design. Auto Loader checkpoints mean a rerun never loads a file twice; materialized views recompute from their inputs, so a rerun gives the same result (idempotent). If a cleaning rule changes: run a **full refresh** of the pipeline (rebuilds every table from the files still in the volume). To repair one bad day: replace the file and full-refresh. |

## 8. Databricks features: what we used, where, and why

| Feature | Used? | Where | Why / why not |
|---|---|---|---|
| **Streaming tables** | Yes | Bronze ingestion (Auto Loader) and silver line tables | New files arrive daily and are append-only; streaming processes each file exactly once. Triggered mode, because continuous streaming makes no sense for one file a day. |
| **Materialized views** | Yes | Lookups, `mv_checks`, `mv_receipt_copies`, all of gold | Logic that needs whole groups (copies within a day, totals per receipt, percentiles across employees) does not fit append-only streaming; an MV recomputes correctly when inputs change, and Databricks refreshes it incrementally when it can. |
| **Liquid clustering** | Yes | `(dt, location_id)` on receipts and lines; `employee_id` on employee signals; `risk_tier, main_store_id` on the score | Clustering keys match how the tables are filtered (a day, a store, an employee). Replaces partitioning; can be changed later without rewriting. Honest caveat: at this data size the speed gain is small; it matters as the data grows. |
| **Expectations** | Yes, all 3 levels | Bronze (fail / drop / warn), silver (warn on every flag), gold (warn) | Matches our rule "flag, don't delete": most rules warn and count, only unusable rows are dropped, only a broken feed stops the pipeline. |
| **Unity Catalog** | Yes | `workspace.bronze/silver/gold`, managed volume for raw files | One governed place for files and tables; table comments and properties (`quality`, `contains_pii`) document every table. |
| **Asset Bundles (code-first)** | Yes | `databricks.yml`, `resources/` | Pipeline, job, schemas and volume deploy from git with one command; nothing configured by hand. |
| Serverless compute | Yes | Pipeline and job | No clusters to size or manage (the only option in Free Edition). |
| Continuous streaming | No | | One file a day; triggered runs are cheaper and simpler. |
| A trained ML model | Not yet | | No labels to train or validate on; an explainable score comes first. |

## 9. Proof that the port is correct (parity with Phase 1)

Phase 1 cleaned the data with DuckDB on a laptop. Phase 2 re-implements the same rules in Spark. Before deploying, we ran the Spark code locally (`src/validation/local_dry_run.py`) on May 4–10 and compared it with the Phase 1 tables for the same days:

| Number (May 4–10) | Phase 1 (DuckDB) | Phase 2 (Spark) |
|---|---|---|
| Raw receipts | 140,208 | 140,208 |
| Exact copies removed | 12 | 12 |
| Clean receipts | 140,196 | 140,196 |
| Item sales | $5,968,512.13 | $5,968,512.13 |
| Gross sales | $6,025,097.69 | $6,025,097.69 |
| Void amount | $45,302.92 | $45,302.92 |
| Tips | $588,483.30 | $588,483.30 |
| Item lines / payments / voids / discounts | 1,866,480 / 146,591 / 10,689 / 33,509 | identical |
| All 8 quality flags + 8 risk flags | e.g. unbalanced 3, no items 831, walkouts 144, fully comped 4,053 | identical, all 16 |

Two independent implementations give the same numbers to the cent.

**Then on the full data, in Databricks (115 days):**

| Number (Apr 28 – Aug 20) | Phase 1 (DuckDB) | Phase 2 (Databricks) |
|---|---|---|
| Raw receipts | 2,142,846 | 2,142,846 |
| Exact copies removed | 229 | 229 |
| Clean receipts | 2,142,617 | 2,142,617 |
| Receipts whose money identity balances | 99.996% | 99.996% |
| Employees compared ($5K+ sales, 50+ card payments) | 2,516 | 2,516 |
| Employees top 10% on 3+ of 5 signals | 106 | 106 |
| Munster void rate / vs chain median | 2.29% / 2.9× | 2.29% / 2.87× |
| Top 5 stores by void rate | Munster, Grand Island, Clinton, Columbus, Corpus Christi | same 5, same order |

## 10. Results of the Databricks runs (Oct 28, 2026): 14-day demo and full 115-day run

Workspace: Databricks Free Edition, catalog `workspace`. Screenshots in [`docs/img/`](img/).

### Demo workspace runs (14 days, `dbc-992f5532-5ec3`)

| # | What | Result | Evidence |
|---|---|---|---|
| 1 | `bundle deploy`, upload May 4–10, `bundle run` | Pipeline succeeded in 3 min (all 15 tables). **Quality gate failed 1 of 12 checks** (privacy) and blocked the job | `01_job_run_gate_blocked.png`, `02_gate_failure_message.png` |
| 1b | Cause: the privacy check flagged the `Name` column of the **store** and **channel** lookups (place names, not people). Fix: a bare `name` column only counts as personal data in an employee table. Redeployed, then **Repair run** re-ran only the failed task | Job green, **12 of 12** checks passed, without re-running the pipeline | `03_job_run_repaired_green.png`, `04_quality_gate_12_of_12.png` |
| 2 | Uploaded May 11–17, ran the job again | `st_raw_checks` wrote **136K** rows = exactly the 136,487 receipts of the new week (two weeks = 276,695): **only the new files were read**. `st_voids` wrote 13K = the week's 13,013 voids. The pipeline UI labels materialized views as *Incremental* or *Full recompute*: Databricks picks incremental refresh when it can | `06_incremental_week2_only_136k.png`, `07_job_run_week2_green.png` |

Pipeline graph with every table and dependency: `05_pipeline_graph.png`.

### Data quality, May 4–17 (`gold.mv_data_quality_summary`, `08_data_quality_summary_14_days.png`)

| Day | Raw | Copies | Clean | Unreconciled | % balanced | % flagged |
|---|---|---|---|---|---|---|
| May 4 | 15,409 | 1 | 15,408 | 0 | 100 | 1.90 |
| May 5 | 15,620 | 3 | 15,617 | 0 | 100 | 2.25 |
| May 6 | 16,445 | 1 | 16,444 | 0 | 100 | 1.92 |
| May 7 | 17,650 | 1 | 17,649 | 0 | 100 | 1.95 |
| May 8 | 24,038 | 1 | 24,037 | 0 | 99.992 | 1.96 |
| May 9 | 23,164 | 1 | 23,163 | 0 | 99.996 | 1.97 |
| May 10 (Mother's Day) | 27,882 | 4 | 27,878 | 0 | 100 | 1.75 |
| May 11 | 16,185 | 1 | 16,184 | 0 | 100 | 1.85 |
| May 12 | 15,872 | 1 | 15,871 | 0 | 99.994 | 1.93 |
| May 13 | 17,331 | 3 | 17,328 | 0 | 99.977 | 1.90 |
| May 14 | 19,066 | 1 | 19,065 | 0 | 99.974 | 2.15 |
| May 15 | 25,321 | 3 | 25,318 | 0 | 99.988 | 2.11 |
| May 16 | 22,971 | 2 | 22,969 | 0 | 100 | 1.88 |
| May 17 | 19,741 | 1 | 19,740 | 0 | 99.995 | 1.87 |
| **Total** | **276,695** | **24** | **276,671** | **0** | | |

Every total matches the Phase 1 tables for the same 14 days (raw 276,695, clean 276,671).

### Demo workspace: stores, 14 days (`gold.mv_store_risk_score`, `09_store_risk_ranking.png`)

| Rank | Store | Receipts | Void % | Void vs chain median | Discount % | Walkout % | Score |
|---|---|---|---|---|---|---|---|
| 1 | Hilliard Rome | 1,600 | 1.11 | 1.39× | 6.23 | 0.250 | 91.6 |
| 2 | Frankfort | 1,474 | 1.21 | 1.52× | 5.70 | 0.136 | 85.4 |
| 3 | Richmond IN | 1,776 | 1.18 | 1.49× | 5.97 | 0.113 | 85.2 |
| 4 | **Munster** | 2,186 | **3.27** | **4.13×** | 3.86 | 0.183 | 84.1 |
| 5 | Chillicothe | 1,546 | 1.12 | 1.42× | 5.39 | 0.323 | 83.8 |
| 6 | Ireland Road | 2,173 | 1.16 | 1.46× | 6.99 | 0.092 | 83.7 |
| 7 | Desert Sky | 2,067 | 1.06 | 1.33× | 3.36 | 0.387 | 81.3 |
| 8 | Merrillville | 1,622 | 1.61 | 2.03× | 3.75 | 0.308 | 80.3 |
| 9 | Ocean Springs | 1,099 | 1.74 | 2.20× | 4.87 | 0.455 | 80.2 |
| 10 | Danville | 1,819 | 0.95 | 1.20× | 5.95 | 0.275 | 78.4 |

Read it as: the top stores are high on **several** signals at once (Hilliard Rome: discounts, walkouts and voids all above the chain). **Munster** is the outlier on one signal: it voids 3.27% of gross sales, 4.1× the chain median, which matches Phase 1 (2.29% over 115 days, 2.9× the median, every month). The pipeline confirms in a few seconds what took Phase 1 a manual analysis.

### Demo workspace: employees, 14 days (`gold.mv_employee_risk_score`, `10_employee_risk_tiers.png`)

2,114 employees met the (scaled) sales and card-payment bar for May 4–17.

| Tier | Employees | Avg score | Avg void % | Avg walkout % | Gross sales |
|---|---|---|---|---|---|
| review first (top 10% on 3+ of 5 signals) | **62** (2.9%) | 72.6 | **2.44** | **0.962** | $309K (2.7%) |
| watch (top 10% on 2) | 162 | 59.7 | 1.82 | 0.311 | $774K |
| normal | 1,890 | 34.4 | 0.81 | 0.074 | $10.47M |

- The 62 *review first* employees void **3× as much** of their sales as the rest (2.44% vs 0.81%) and have **13× the walkout rate** (0.96% vs 0.07% of receipts), while ringing only 2.7% of sales. A manager can review 62 people instead of 2,114.
- If the 5 signals were unrelated, about **18** employees would be top 10% on 3+ of them by chance (0.86% × 2,114). We see **62, 3.4× chance**, the same stacking Phase 1 found over 115 days (106 vs ~22). The pattern holds in two weeks of data, computed automatically by the pipeline.
- Employee IDs exist in the table for managers, but stay off slides.


### Full run: all 115 days (teammate's workspace, `dbc-23a888d3-fb75`)

| # | What | Result | Evidence |
|---|---|---|---|
| 3 | `bundle deploy -t full` (6 resources created), uploaded 115 day files (969 MB gzipped), `bundle run -t full` | Pipeline **succeeded in 10.5 min** within the Free Edition quota, but Databricks had to **retry it automatically** ("Refresh all (Automatic recovery)": two failed attempts, then success). The **quality gate failed 2 of 12 checks** and blocked the job: 229 exact copies were still in `silver.mv_checks`, and 0% of receipts had a store name | `11_full_run_gate_blocked.png`, `12_full_run_gate_10_of_12.png` |
| 3b | Diagnosis: bronze, the copy list and the stores table were all correct; only `mv_checks` was wrong (2,142,846 rows instead of 2,142,617, every store name empty). During the automatic recovery `mv_checks` was recomputed as if `mv_receipt_copies` and `mv_stores` were still empty. The same code passed 12/12 in the demo workspace, so it is the recovery, not the logic (we did not confirm the exact internal mechanism) | | `13_full_run_mv_checks_wrong_counts.png`, `14_full_run_pipeline_graph_recovery.png` |
| 3c | Fix: **full refresh of the 6 affected tables only** (`mv_checks` + the 5 gold tables; no re-ingestion of the 115 files), then **Repair run** of the quality gate | Counts exactly as Phase 1, gate **12 of 12**, job green | `15_full_refresh_selected_tables.png`, `16_full_run_counts_fixed.png`, `17_full_run_job_green.png` |

**Why this matters:** the safety net worked on real data. A silent error in the main table would have produced wrong risk scores; instead the gate stopped the job, the cause was found with two SQL counts, and only the broken tables were rebuilt. Lesson for production: after an automatic recovery, the gate is what tells you whether the result can be trusted.

### Stores, 115 days (`18_full_store_risk_ranking.png`, `20_full_top_void_stores.png`)

| Rank | Store | Receipts | Void % | Void vs chain | Discount % | Walkout % | Score |
|---|---|---|---|---|---|---|---|
| 1 | Ireland Road | 16,385 | 1.12 | 1.40× | 7.20 | 0.189 | 91.9 |
| 2 | Hilliard Rome | 12,258 | 1.14 | 1.42× | 5.58 | 0.220 | 90.3 |
| 3 | Danville | 13,990 | 1.13 | 1.41× | 5.74 | 0.136 | 86.5 |
| 4 | Desert Sky | 15,721 | 1.04 | 1.30× | 3.98 | 0.280 | 86.0 |
| 5 | **Munster** | 15,858 | **2.29** | **2.87×** | 4.67 | 0.233 | 83.8 |
| 6 | Morse Road | 18,201 | 0.73 | 0.91× | 5.82 | **0.626** | 81.0 |
| 7 | Frankfort | 10,443 | 1.00 | 1.25× | 5.23 | 0.153 | 80.8 |
| 8 | Corpus Christi | 17,914 | 1.59 | 1.99× | 4.27 | 0.296 | 78.6 |
| 9 | Chillicothe | 13,090 | 1.01 | 1.26× | 5.19 | 0.122 | 77.5 |
| 10 | Nicholasville | 9,779 | 1.55 | 1.93× | 4.55 | 0.092 | 76.8 |

- **Two kinds of risky store.** Most of the top 10 are above the chain on *several* signals at once (Ireland Road: 7.2% discounts, the highest; voids 1.4× the median). Others stand out on *one*: **Munster** voids 2.29% of sales, 2.87× the chain median; **Morse Road** has normal voids but the highest walkout rate in the top 10 (0.63% of receipts).
- **Top 5 by void rate:** Munster 2.29%, Grand Island 1.73%, Clinton 1.69%, Columbus 1.65%, Corpus Christi 1.59%: exactly the Phase 1 list. The pipeline now produces it automatically every day.
- Hilliard Rome, Desert Sky, Danville, Chillicothe and Munster were also in the 14-day top 10: the ranking is stable.

### Employees, 115 days (`19_full_employee_risk_tiers.png`)

2,516 employees with $5,000+ in sales and 50+ card payments (the Phase 1 bar).

| Tier | Employees | Avg score | Avg void % | Avg walkout % | Avg discount % | Gross sales |
|---|---|---|---|---|---|---|
| review first (top 10% on 3+ of 5 signals) | **106** (4.2%) | 78.2 | **2.26** | **0.661** | **7.56** | $2.50M (2.9%) |
| watch (top 10% on 2) | 182 | 67.5 | 1.51 | 0.280 | 5.63 | $5.86M |
| normal | 2,228 | 43.0 | 0.86 | 0.087 | 3.02 | $77.39M |

- The 106 *review first* employees void **2.6× as much** of their sales as everyone else (2.26% vs 0.86%), give **2.5× the discounts** (7.56% vs 3.02%) and have **7.6× the walkout rate** (0.66% vs 0.09% of receipts), while ringing **2.9% of sales**. A manager can start with 106 people instead of 2,516.
- If the 5 signals were unrelated, about **22** employees would be top 10% on 3 or more by chance (0.86% × 2,516). The pipeline finds **106, 4.9× chance**: exactly the Phase 1 number, now produced automatically.
- Employee IDs exist in the table for managers, but stay off slides.

## 11. Limits and what we would do next

- **Free Edition limits:** the full load needed an automatic recovery, and the recovery left one table wrong until we rebuilt it (section 10). On a paid workspace we would size compute for the initial backfill and keep the gate as the final check.
- **Short windows are noisy.** With 14 days the employee rates move more than with 115; the bar is scaled to the days loaded, and the full run gives the reliable numbers.
- **Job roles are unknown** (no lookup for job IDs), so part of a signal may come from the role (e.g. bartenders handle cash and voids).
- **Not built yet:** manager–employee approval pairs, the Munster (store 80) deep dive, repeated tip padding, a Databricks dashboard / Genie space on the gold tables, alerting on score changes.

## 12. Questions we expect, with answers

- **"Is this fraud?"** No labels exist, so we can't say. The score ranks where to look first; a manager confirms.
- **"Why not delete the bad rows?"** In fraud work the odd rows are the evidence. We flag and count them (WARN expectations); only exact copies are removed, and they're listed.
- **"Did you run all the data?"** Yes: all 115 days (2.14M receipts) in a second workspace, deployed from the same repo with one command. The numbers match Phase 1 exactly. The demo workspace shows incremental loading with 2 weeks.
- **"What went wrong?"** On the full load, Databricks retried the pipeline automatically and one table came out wrong. The quality gate caught it and blocked the job; we rebuilt only the affected tables and it passed. That's the safety net doing its job.
- **"Why streaming if the data is historical?"** In production a new file lands every day. Auto Loader reads only new files; we show it by loading a second week and seeing only those 7 files processed.
- **"Why materialized views in silver and gold?"** Finding copies, totaling receipts and ranking employees need whole groups of rows, which append-only streaming can't recompute when inputs change. MVs can.
- **"What happens if the job fails halfway?"** The pipeline retries once; checkpoints mean nothing is loaded twice; the quality gate blocks bad output and e-mails us. Reruns are idempotent.
- **"How do you know the Spark code is right?"** It reproduces the Phase 1 numbers exactly (section 9), and the quality gate re-checks reconciliation on every run.
- **"Why liquid clustering and not partitioning?"** Partitioning by day would make 115 small partitions per table and is fixed forever; liquid clustering adapts file layout to the filter columns and can be changed later.
- **"Where is the personal data?"** Nowhere in the tables: the HR file's personal fields are never parsed. The gate checks every run.
- **"Why these thresholds ($5K, 50 card payments)?"** Below them a single event swings the rate. Phase 1 chose them; gold scales them to the days loaded.
