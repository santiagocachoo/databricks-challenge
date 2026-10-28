# Presenter guide: Phase 2 (pipeline)

Read time: about 15 minutes. This is everything you need to present Phase 2 and answer questions. For more depth on any point, [`PIPELINE.md`](PIPELINE.md) has the full detail (section numbers are given below as §).

**Presentation: Thu Oct 29, 2026.** Screenshots referenced below are in [`docs/img/`](img/).

---

## 1. The story in five sentences

1. Applebee's franchisee RMH wants to know **where money can leak at the register**: voids, discounts, comps, walkouts, tips, refunds. The data has **no fraud labels**, so we look for risk signals, not proof.
2. In Phase 1 we found that **risk depends on who and where, not when**: the same few employees and stores stand out on several signals at once.
3. In Phase 2 we built a **Databricks pipeline** that does this automatically every day: raw receipt files go in, and out come a **risk score per employee and per store**, plus a daily data-quality report.
4. It is reliable by design: it **only reads new files**, it **checks the data at every step** and keeps odd receipts instead of deleting them, and a **quality gate stops the job** if anything doesn't add up. It reproduces the Phase 1 numbers **to the cent**.
5. Result: out of 2,114 employees, **62 are flagged "review first"**. They void 3× as much and have 13× the walkouts of everyone else. **Munster** voids 4× the chain median, as in Phase 1.

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
| **Free Edition** | The free Databricks account we used. It has a daily compute limit, which is why we loaded 14 days for the demo instead of 115. |
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
- *Show:* `01_job_run_gate_blocked.png` → `03_job_run_repaired_green.png`.
- *Numbers:* pipeline 3–4 min, gate 25 s.

**Slide 4: Bronze, incremental loading**
- *Say:* "Bronze uses Auto Loader as a streaming table, so each run reads only the new day files. We proved it: we loaded one week, then added a second week, and the second run wrote 136 thousand rows, exactly the new week, not both. We also declare the file format up front, so anything unexpected is kept aside instead of breaking the load. And the employee names and birth dates in the HR file are never even read."
- *Show:* `06_incremental_week2_only_136k.png`.
- *Numbers:* 136K rows = 136,487 new receipts (both weeks = 276,695).

**Slide 5: Silver, one clean receipt table**
- *Say:* "Silver splits each receipt into items, discounts, payments, voids and taxes, applies the cleaning rules we decided in Phase 1, and builds one clean row per receipt with its totals and 20 yes/no flags. The only thing we remove is exact copies, receipts the POS saved twice, and we keep a list of every one."
- *Numbers:* 276,695 raw → 24 copies removed → 276,671 clean.

**Slide 6: Data quality, flag don't delete**
- *Say:* "Quality is checked twice. Inside the pipeline, expectations check every row at three levels: stop if a file can't be dated, drop a receipt with no ID, and only warn on everything else, because in fraud work the odd receipts are the evidence. After the pipeline, the gate runs 12 checks by dimension: completeness, uniqueness, consistency, validity, accuracy and privacy."
- *Show:* `04_quality_gate_12_of_12.png`, `08_data_quality_summary_14_days.png`.
- *Numbers:* 12/12 checks; 99.998% of receipts balance; 1.9% flagged and kept; 0 unreconciled; 0 personal-data columns.

**Slide 7: Same numbers, two implementations**
- *Say:* "Phase 1 cleaned the data with DuckDB on a laptop; Phase 2 rewrote it in Spark on Databricks. Both give the same numbers to the cent: receipts, sales, voids, tips and every flag."
- *Show:* parity table (PIPELINE §9).

**Slide 8: Best practices**
- *Say:* "Streaming where new data arrives, materialized views where we need whole groups, liquid clustering on day and store because that's how we filter, expectations at all three levels, and everything deployed as code. We chose *not* to use continuous streaming, because one file a day doesn't need it, and *not* to train a model, because without labels we couldn't check it."
- *Show:* table from PIPELINE §8. Bonus: in `06`, Databricks labels views *Incremental* vs *Full recompute*.

**Slide 9: Who and where to look first**
- *Say:* "Out of 2,114 employees, 62 are flagged *review first*: they're in the top 10% on three or more signals. They void three times as much as the rest and have thirteen times the walkouts, and they ring under 3% of sales. By chance we'd expect about 18; we see 62, the same stacking Phase 1 found. For stores, Munster voids 3.3% of sales, four times the chain median, just like in Phase 1."
- *Show:* `09_store_risk_ranking.png`, `10_employee_risk_tiers.png` (tiers only, no IDs).

**Slide 10: Conclusion**
- *Say:* "The value is a daily, trustworthy and explainable risk ranking: a manager reviews 62 people instead of 2,000. Next steps: load all 115 days, look at manager–employee approval pairs, dig into Munster, and put a dashboard and alerts on the gold tables."

## 4. Questions you may get (short answers)

| Question | Answer |
|---|---|
| Is this fraud? | We can't say: there are no labels. It ranks where to look first; a manager confirms. |
| Why only 14 days? | Free Edition's daily compute limit is shared by the team. The code is the same for 115 days; it's just more files. |
| Why streaming if the data is historical? | In production a new file arrives every day. We showed that a second week loads only the new files. |
| Why not delete the bad rows? | Odd receipts are the evidence in fraud work. We flag them and count them; only exact copies are removed, and they're listed. |
| What if the job fails halfway? | The pipeline retries once; nothing loads twice; the gate blocks bad output and e-mails us; *Repair run* re-runs only what failed. |
| How do you know the Spark code is right? | It matches Phase 1 to the cent, and the gate checks every day that raw = clean + copies. |
| Why not a machine-learning model? | No labels to train or test against. A transparent score a manager can read is more honest. A model is a next step. |
| Why these signals and thresholds? | They're the levers where money leaves the register. Rates, so busy employees don't look worse. The sales bar comes from Phase 1 ($5K / 115 days), scaled to the days loaded. |
| Where's the personal data? | Nowhere: names, birth dates and payroll IDs are never read. The gate checks it on every run. |
| Why liquid clustering and not partitions? | Partitioning by day makes many small pieces and is fixed forever; liquid clustering adapts and can be changed later. At this size the speed-up is small; it matters as data grows. |
| Why is a 14-day score reliable? | Less reliable than 115 days: rates are noisier. But the same pattern appears (62 vs ~18 by chance), and it gets stronger with more days. |

## 5. Do and don't

- **Say** "risk signal", "anomaly", "review first". **Never say** someone committed fraud.
- **Never show** employee IDs or names. Store names are fine.
- **Do** mention the gate failure on run 1: it shows the safety net works.
- **Be honest** about limits: 14 days, no job-role lookup, no labels.
