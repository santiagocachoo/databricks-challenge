# Presenter guide: Phase 2 (pipeline)

Read time: about 15 minutes. This is everything you need to present Phase 2 and answer questions. For more depth on any point, [`PIPELINE.md`](PIPELINE.md) has the full detail (section numbers are given below as §).

**Presentation: Thu Oct 29, 2026.** Screenshots referenced below are in [`docs/img/`](img/).

---

## 1. The story in five sentences

1. Applebee's franchisee RMH wants to know **where money can leak at the register**: voids, discounts, comps, walkouts, tips, refunds. The data has **no fraud labels**, so we look for risk signals, not proof.
2. In Phase 1 we found that **risk depends on who and where, not when**: the same few employees and stores stand out on several signals at once.
3. In Phase 2 we built a **Databricks pipeline** that does this automatically every day: raw receipt files go in, and out come a **risk score per employee and per store**, plus a daily data-quality report.
4. It is reliable by design: it **only reads new files**, it **checks the data at every step** and keeps odd receipts instead of deleting them, and a **quality gate stops the job** if anything doesn't add up. It reproduces the Phase 1 numbers **to the cent**.
5. Result on all 115 days (2.14M receipts): out of 2,516 employees, **106 are flagged "review first"**. They void 2.6× as much, discount 2.5× as much and have 7.6× the walkouts of everyone else, while ringing under 3% of sales. **Munster** voids 2.9× the chain median, exactly as in Phase 1.

## 2. Glossary in plain words

| Term | What it means here |
|---|---|
| **Pipeline** | The chain of steps that turns raw files into final tables. In Databricks you write "this table = this query" and Databricks works out the order and runs it. Ours is a *Lakeflow Declarative Pipeline* (formerly called Delta Live Tables / DLT). |
| **Job** | What presses "run". Ours has 2 steps (tasks): run the pipeline, then run the quality gate. It also holds the schedule, retries and failure e-mail. |
| **Bronze / silver / gold** | The 3 layers (the "medallion architecture" from the Databricks courses). **Bronze** = the data exactly as it arrived. **Silver** = cleaned and organized. **Gold** = final tables that answer the business question. |
| **Volume** | A folder of files inside Databricks. Our raw files land in `bronze.landing`. |
| **Auto Loader** | The Databricks feature that reads new files from a folder and remembers which ones it already read. |
| **Streaming table** (`st_` in our names) | A table that only processes new data on each run. Day 116 costs one day of work, not 116. |
| **Materialized view** (`mv_`) | A saved query result that Databricks keeps up to date. Used where a step needs to see whole groups of rows (totals per receipt, rankings). |
| **Liquid clustering** | Telling Databricks to store a table sorted by the columns we filter on most (day and store), so queries skip what they don't need. |
| **Expectation** | A data-quality rule on a table, with an action: **warn** (keep the row, count it), **drop** (remove the row, count it) or **fail** (stop everything). |
| **Quality gate** | Our second job task: 12 checks on the finished tables (duplicates, counts that must add up, privacy...). If any fails, the job fails and sends an e-mail. |
| **Asset Bundle** | The pipeline, job and storage written as files in the repo (`databricks.yml`, `resources/`) and deployed with one command. Nothing was set up by clicking. |
| **Serverless** | Databricks runs the compute for us; there are no servers to configure. |
| **Free Edition** | The free Databricks account we used. It has a daily compute limit, so we used two: one for the demo (14 days, incremental loading) and a teammate's for the full 115 days. Same code, deployed with one command to each. |
| **AI/BI dashboard** | Databricks' built-in dashboards. Ours reads the gold tables and shows the counters, store ranking, employee tiers and daily trend. We wrote the 5 queries; Genie (the built-in assistant) laid out the charts. |
| **Risk score** | 0–100 per employee or store: the average of where they rank (percentile) on 5 signals. 50 = typical, near 100 = high on everything. |
| **Signals** (all are rates) | Void $ ÷ sales · discount $ ÷ sales · walkouts per receipt · fully comped receipts per receipt · card tips larger than the bill per card payment. |

## 3. Slide-by-slide script

About 8–10 minutes. If the slot is 5 minutes, merge slides 4+5 and drop slide 8 (keep it for questions).

**Slide 1: Objective**
- *Say:* "RMH runs 127 Applebee's. The question is where money can leak at the register. There are no fraud labels, so we don't accuse anyone: we build risk signals that tell a manager where to look first. Phase 1 showed risk depends on *who* and *where*, not *when*. Phase 2 turns that into a pipeline that runs every day."
- *Numbers:* 127 restaurants, 2.1M receipts, 115 days, no labels.

**Slide 2: Architecture**
- *Say:* "Raw receipt files land in a volume. Bronze loads them as they are, silver cleans and organizes them, gold builds the risk tables. Everything is code in our GitHub repo and deploys with one command."
- *Show:* the architecture diagram (README) or `05_pipeline_graph.png`, plus the repo tree.

**Slide 3: The job**
- *Say:* "One job, two tasks: first the pipeline, then a quality gate. It's scheduled daily at 6 AM. If the pipeline fails it retries once, if the gate fails it stops and e-mails us. Reruns are safe: files already loaded are never loaded twice. On our first run the gate actually blocked the job: it flagged store names as possible personal data. We fixed the rule and used *Repair run*, which re-ran only the failed task."
- *Say (if time):* "It happened again on the full 115 days, and this time it was real: Databricks had to retry the pipeline automatically, and in the retry the main receipts table came out wrong, with the copies still in and no store names. The gate caught it and blocked the job, two SQL counts showed which table was wrong, and we rebuilt only that table and the gold tables, without reloading the 115 files."
- *Show:* `01_job_run_gate_blocked.png` → `03_job_run_repaired_green.png`; full run: `12_full_run_gate_10_of_12.png` → `16_full_run_counts_fixed.png` → `17_full_run_job_green.png`.
- *Numbers:* demo pipeline 3–4 min; full 115 days 10.5 min; gate 25 s.

**Slide 4: Bronze, incremental loading**
- *Say:* "Bronze uses Auto Loader as a streaming table, so each run reads only the new day files. We proved it: we loaded one week, then added a second week, and the second run wrote 136 thousand rows, exactly the new week, not both. We also declare the file format up front, so anything unexpected is kept aside instead of breaking the load. And the employee names and birth dates in the HR file are never even read."
- *Show:* `06_incremental_week2_only_136k.png`.
- *Numbers:* 136K rows = 136,487 new receipts (both weeks = 276,695).

**Slide 5: Silver, one clean receipt table**
- *Say:* "Silver splits each receipt into items, discounts, payments, voids and taxes, applies the cleaning rules we decided in Phase 1, and builds one clean row per receipt with its totals and 20 yes/no flags. The only thing we remove is exact copies, receipts the POS saved twice, and we keep a list of every one."
- *Numbers (115 days):* 2,142,846 raw → 229 copies removed → 2,142,617 clean.

**Slide 6: Data quality, flag don't delete**
- *Say:* "Quality is checked twice. Inside the pipeline, expectations check every row at three levels: stop if a file can't be dated, drop a receipt with no ID, and only warn on everything else, because in fraud work the odd receipts are the evidence. After the pipeline, the gate runs 12 checks by dimension: completeness, uniqueness, consistency, validity, accuracy and privacy."
- *Show:* `04_quality_gate_12_of_12.png`, `08_data_quality_summary_14_days.png`.
- *Numbers (115 days):* 12/12 checks; 99.996% of receipts balance; 2.0% flagged and kept; 0 unreconciled; 0 personal-data columns.

**Slide 7: Same numbers, two implementations**
- *Say:* "Phase 1 cleaned the data with DuckDB on a laptop; Phase 2 rewrote it in Spark on Databricks. On all 115 days both give exactly the same numbers: 2,142,617 clean receipts, 229 copies, 2,516 employees compared, 106 flagged, and the same top-5 void stores in the same order."
- *Show:* parity table (PIPELINE §9) + `16_full_run_counts_fixed.png`.

**Slide 8: Best practices**
- *Say:* "Streaming where new data arrives, materialized views where we need whole groups, liquid clustering on day and store because that's how we filter, expectations at all three levels, and everything deployed as code. We chose *not* to use continuous streaming, because one file a day doesn't need it, and *not* to train a model, because without labels we couldn't check it."
- *Show:* table from PIPELINE §8. Bonus: in `06`, Databricks labels views *Incremental* vs *Full recompute*.

**Slide 9: Who and where to look first**
- *Say:* "On all 115 days, out of 2,516 employees, 106 are flagged *review first*: top 10% on three or more signals. They void 2.6 times as much as the rest, discount 2.5 times as much and have 7.6 times the walkouts, while ringing under 3% of sales. By chance we'd expect about 22; we see 106, five times chance. For stores there are two patterns: stores high on several signals, like Ireland Road and Hilliard Rome at the top of the score, and stores with one extreme signal, like Munster, which voids 2.3% of sales, almost three times the chain median, every month."
- *Show:* **the dashboard** `22_dashboard_overview.png`: it reads the gold tables, so it updates after every run. Point at the 4 counters, then the store bars, then the employee tiers. Backup: `18`, `19`, `20` (SQL results).
- *If asked about the line chart:* voids are flat every day; discounts are steady at 3–4% with a few July spikes (likely promotions). Neither depends on the weekday.

**Slide 10: Conclusion**
- *Say:* "The value is a daily, trustworthy and explainable risk ranking: a manager starts with 106 people instead of 2,516, and an auditor with a short list of stores. Next steps: manager–employee approval pairs, a Munster deep dive, a dashboard and alerts on the gold tables, and a paid workspace sized for backfills."

## 4. Questions you may get (short answers)

| Question | Answer |
|---|---|
| Is this fraud? | We can't say: there are no labels. It ranks where to look first; a manager confirms. |
| Did you run all the data? | Yes: all 115 days (2.14M receipts) in a second workspace, deployed from the same repo with `-t full`. It matches Phase 1 exactly. The demo workspace has 2 weeks to show incremental loading. |
| What went wrong along the way? | Twice the gate blocked the job: once a false alarm in our own privacy check (store names), once a real error after Databricks' automatic retry on the full load. Both times we fixed it and re-ran only what failed. |
| Why streaming if the data is historical? | In production a new file arrives every day. We showed that a second week loads only the new files. |
| Why not delete the bad rows? | Odd receipts are the evidence in fraud work. We flag them and count them; only exact copies are removed, and they're listed. |
| What if the job fails halfway? | The pipeline retries once; nothing loads twice; the gate blocks bad output and e-mails us; *Repair run* re-runs only what failed. |
| How do you know the Spark code is right? | It matches Phase 1 to the cent, and the gate checks every day that raw = clean + copies. |
| Why not a machine-learning model? | No labels to train or test against. A transparent score a manager can read is more honest. A model is a next step. |
| Why these signals and thresholds? | They're the levers where money leaves the register. Rates, so busy employees don't look worse. The sales bar comes from Phase 1 ($5K / 115 days), scaled to the days loaded. |
| Where's the personal data? | Nowhere: names, birth dates and payroll IDs are never read. The gate checks it on every run. |
| Why liquid clustering and not partitions? | Partitioning by day makes many small pieces and is fixed forever; liquid clustering adapts and can be changed later. At this size the speed-up is small; it matters as data grows. |
| Is the score stable? | Yes: with 14 days we got 62 *review first* (3.4× chance); with 115 days 106 (4.9× chance, same as Phase 1). Five of the 14-day top-10 stores are still in the 115-day top 10. |

## 5. Do and don't

- **Say** "risk signal", "anomaly", "review first". **Never say** someone committed fraud.
- **Never show** employee IDs or names. Store names are fine.
- **Do** mention the gate failure on run 1: it shows the safety net works.
- **Be honest** about limits: no job-role lookup, no labels, Free Edition limits (the full load needed a retry).
