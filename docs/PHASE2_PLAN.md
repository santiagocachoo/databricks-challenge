# Phase 2 plan, status and presentation outline

**Presentation: Thu Oct 29, 2026.** Brief and rubric: [`PHASE2_BRIEF.md`](PHASE2_BRIEF.md). How everything works: [`PIPELINE.md`](PIPELINE.md).

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Workspace | Databricks **Free Edition** (owner's account, teammates invited); catalog `workspace` | No workspace was provided by the organizers |
| Data loaded | **May 4–10** (7 days, 140,208 receipts), then **May 11–17** to demo incremental loading | Free Edition has a daily compute quota shared by the team; same code runs all 115 days |
| Repo layout | Organizers' template + `bronze/`, `src/validation/`, `databricks.yml`; Phase 1 moved to `phase1_eda/` | Template has no raw layer; bundles need `databricks.yml` |
| Deployment | Databricks Asset Bundles from the CLI (`databricks bundle deploy`) | Everything as code, one command |
| Risk score | Average percentile on 5 signals + top-10% count + tier | No labels: explainable beats a black box |
| Job schedule | Daily 06:00, deployed **paused**; run on demand | Saves quota; shows the scheduling design |

## Team rules for the quota

1. Nobody runs anything heavy in the workspace without telling the team.
2. Never upload or run more than the planned days before the presentation.
3. If the quota runs out, compute stops for the rest of the day: the final run must be done **today**, not tomorrow morning.

## Status checklist

- [x] Repo restructured (Phase 1 → `phase1_eda/`)
- [x] Pipeline code: bronze, silver, gold; job + pipeline YAML; quality gate
- [x] Local parity test: Spark reproduces Phase 1 numbers exactly for May 4–10
- [x] Raw files compressed into `upload/` (week 1, week 2, dimensions)
- [x] Docs: README, PIPELINE, PHASE2_BRIEF, PHASE2_PLAN
- [x] Databricks CLI installed and logged in
- [x] `databricks bundle deploy` (6 resources created)
- [x] Upload dimensions + week 1 to the volume
- [x] Run the job (week 1): pipeline green; quality gate caught a false positive (store/channel `Name`), fixed, Repair run → 12/12
- [x] Screenshots in `docs/img/` (job graph, gate output, pipeline graph, incremental run, data-quality summary, store ranking, employee tiers)
- [x] Upload week 2, run again: `st_raw_checks` wrote 136K rows = only the new week
- [ ] Optional: full 115-day run in a teammate's workspace (`databricks bundle deploy -t full`, files in `upload/all_days/`)
- [ ] Optional: dashboard on gold tables
- [ ] Deck (6 sections below) + rehearsal ×2
- [ ] Commit and push (user)

## Run commands (from the repo root)

```bash
databricks auth login --host https://dbc-992f5532-5ec3.cloud.databricks.com
databricks bundle validate
databricks bundle deploy

V=dbfs:/Volumes/workspace/bronze/landing
databricks fs mkdir $V/checks          # create the two folders once
databricks fs mkdir $V/dimensions
for f in upload/dimensions/locations.json.gz upload/dimensions/revenue_centers.json.gz upload/dimensions/employees.json.gz; do databricks fs cp "$f" "$V/dimensions/$(basename $f)"; done
for f in upload/week1_may04_10/*.json.gz; do databricks fs cp "$f" "$V/checks/$(basename $f)"; done
databricks bundle run daily_orchestration_job

# incremental demo
for f in upload/week2_may11_17/*.json.gz; do databricks fs cp "$f" "$V/checks/$(basename $f)"; done
databricks bundle run daily_orchestration_job
```

## Presentation outline (follows the organizers' 6 sections)

Length is unknown; this fits ~8–10 minutes. Cut slide 7 or 9 if it is 5 minutes. Never show employee IDs or names; store names are fine.

| # | Section | Slide | Say | Show |
|---|---|---|---|---|
| 1 | Objective | Where can money leak at the register? | 127 restaurants, 2.1M receipts, no fraud labels → we build **risk signals**, not accusations. Phase 1: risk is about who and where, not when. | One sentence + 3 numbers |
| 2 | Architecture | From JSON to a risk score | Medallion: files in a volume → bronze → silver → gold → quality gate. Everything is code in the repo, deployed with one command. | Architecture diagram (README) + repo tree |
| 3 | Architecture | The job | 2 tasks: pipeline → quality gate. Daily 06:00 schedule (paused in Free Edition). Retries, timeouts, failure e-mail, idempotent reruns. | Job task-graph screenshot |
| 4 | Transformations | Bronze: incremental, contract-first | Auto Loader reads only new day files; explicit schema; off-contract data rescued; personal data never parsed. | Pipeline graph screenshot + incremental demo numbers |
| 5 | Transformations | Silver: one clean receipt table | Flatten nested lines; rules from Phase 1; exact copies removed and audited; 8 quality + 8 risk + 4 context flags. | `mv_checks` columns, copies table |
| 6 | Data quality | Flag, don't delete | Expectations at 3 levels (fail / drop / warn) + quality gate by dimension (completeness, uniqueness, consistency, validity, accuracy, privacy). | Expectations panel + `mv_data_quality_summary` + gate results |
| 7 | Data quality | Same numbers, two implementations | Spark port reproduces Phase 1 to the cent on May 4–10. | Parity table (PIPELINE.md §9) |
| 8 | Best practices | Streaming, MVs, liquid clustering | Where each is used and why; what we chose not to use (continuous streaming, ML without labels). | Table (PIPELINE.md §8) |
| 9 | Analysis | Who and where to look first | Store ranking vs chain median (Munster voids 3.27%, 4.1× the chain median); 62 *review first* employees: 3× the void rate, 13× the walkout rate. | Gold query results / dashboard |
| 10 | Conclusion | Value + next steps | Value: a daily, trustworthy, explainable risk ranking. Next: all 115 days, manager–employee approval pairs, Munster deep dive, dashboard + alerts. | 3 bullets |

### Numbers for the slides (Databricks run, May 4–17, 276,671 clean receipts)

Full tables and screenshots: [`PIPELINE.md` §10](PIPELINE.md#10-results-of-the-databricks-runs-oct-28-2026).

| Slide | Number | Screenshot |
|---|---|---|
| 3 Job | 2 tasks, pipeline 3–4 min, gate 25 s; gate blocked run 1 → fix → Repair run re-ran only the gate | `01`, `03` |
| 4 Bronze | Week 2 load wrote 136K rows = only the 136,487 new receipts (not 276,695) | `06` |
| 5 Silver | 276,695 raw → 24 exact copies removed → 276,671 clean, 0 unreconciled | `08` |
| 6 Quality | Gate 12/12; 99.998% balanced; 1.9% flagged and kept; 0 rescued rows; 0 personal-data columns | `04`, `08` |
| 7 Parity | Spark = Phase 1 to the cent (May 4–10 locally; May 4–17 totals in Databricks) | PIPELINE §9 |
| 9 Stores | Munster voids 3.27% of sales, 4.1× the chain median (Phase 1: 2.9× over 115 days); top 3 by score: Hilliard Rome, Frankfort, Richmond IN | `09` |
| 9 Employees | 62 of 2,114 employees are *review first*: 3× the void rate, 13× the walkout rate, 2.7% of sales; 62 vs ~18 by chance (3.4×) | `10` |

Queries used (SQL Editor):

```sql
SELECT dt, raw_receipts, copies_removed, clean_receipts, unreconciled_receipts, pct_balanced, pct_flagged
FROM workspace.gold.mv_data_quality_summary ORDER BY dt;

SELECT risk_rank, store_name, n_receipts, round(100*void_rate,2) AS void_pct, void_vs_chain,
       round(100*discount_rate,2) AS discount_pct, round(100*walkout_rate,3) AS walkout_pct, risk_score
FROM workspace.gold.mv_store_risk_score ORDER BY risk_rank LIMIT 10;

SELECT risk_tier, count(*) AS employees, round(avg(risk_score),1) AS avg_score,
       round(100*avg(void_rate),2) AS avg_void_pct, round(100*avg(walkout_rate),3) AS avg_walkout_pct,
       round(sum(gross_sales)) AS gross_sales
FROM workspace.gold.mv_employee_risk_score GROUP BY risk_tier ORDER BY avg_score DESC;
```
