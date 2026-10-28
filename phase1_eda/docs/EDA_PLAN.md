# Applebee's EDA Plan (Phase 1)

Tec de Monterrey x Sun Holdings x Databricks Data Challenge · Applebee's AI-Powered Fraud Detection track
**Status: Phase 1 complete. The EDA was presented on Thu Oct 8, 2026.** Next: Phase 2 (brief pending).
Last updated: Oct 8, 2026, after the presentation · Live team version: https://claude.ai/code/artifact/3d05aa74-0b24-476f-b645-4fb429df27ca

## Goal

Present a 5-minute exploratory data analysis (EDA), with one presenter, that scores 4/4 on each of the five rubric rows:

1. Data understanding and context
2. Data cleaning and preparation
3. Exploratory analysis and insights
4. Visualizations
5. Presentation and communication

The organizers' structure is: quick dataset overview, key cleaning steps, top patterns, clear visuals, and a strong conclusion.

## Where things stand (after Oct 8)

Phase 1 is done: the team presented the EDA on Oct 8. Everything Phase 1 produced is in the repo:

| What | Where |
|---|---|
| 12 finished charts, full size (2400 × 1350 px, 16:9) | `phase1_eda/charts/` in this repo |
| Deck guide: the 11-slide plan, which chart goes where, design rules, appendix, cut order | `docs/DECK_GUIDE.md` (charts embedded; 1.3 MB) |
| Every number and finding | `docs/EDA_LEARNINGS.md` |
| Quick catch-up | `docs/TEAM_BRIEFING.md` |
| Context for AI assistants (start here in a new Claude session) | `CLAUDE.md` |

## Decisions

- **Presentation was Thu Oct 8.** We ran P0 tasks only. The P1 tasks are now a backlog for Phase 2.
- **Tooling:** Python, with DuckDB and pandas. Everyone analyzes the clean tables in `phase1_eda/clean/`. No Databricks notebook for Phase 1.
- **Repo:** code and docs live in git; data never does. Teammates set up with `README.md`, and either get `clean.zip` (shared by the team) or rebuild with `python phase1_eda/scripts/build_all.py`.
- **Deck and presentation:** built from the deck guide. The storyboard below is the 11-slide plan we presented.
- **Form and proof:** already submitted.
- **Framing rule:** the data has no fraud labels. We say "risk signals" and "anomalies", never "fraud" as a finding. No employee names or IDs on slides.

## Status

| Step | What | Tasks | State |
|---|---|---|---|
| 0 | Ingest: 115 daily JSON files (11 GB) → 7 flat Parquet tables, profile every table | T0 | Done |
| 1 | Clean tables: positive tip, merged labels, line types, flags, anonymized employees → `phase1_eda/clean/` | T5 | Done |
| 2 | Duplicates: 1,800 look-alike **groups** holding 3,774 receipts → 3,545 split bills kept, 229 exact copies ($73) removed | T6 | Done |
| — | Repo: one-command rebuild (`build_all.py`), setup checker (`check_setup.py`), `README.md` for teammates | — | Done |
| 3 | Cleaning visuals: missing-values chart and cleaning funnel (`01`, `02`) | T7, T8 | Done |
| 4 | Analysis charts (`03`–`11`) and the data model diagram (`00`), one shared style, built by `charts.py` | T1, T2, T10–T15, T19, T20 | Done |
| 5 | Storyboard and deck guide | T21 | Done |
| 6 | Deck (11 slides + appendix), rehearsals, presentation | T3, T22, T23 | Done: presented Oct 8 |

The full pipeline has been tested end to end: a rebuild reproduces the same rows and the same cleaning numbers.

## Task list

P0 means needed for a 4/4 score. P1 means polish; the open P1 tasks are the Phase 2 backlog.

### 1. Data understanding and context

- [x] T0 (P0) Ingest and flatten all 115 days into Parquet, then profile every table.
- [x] T1 (P0) Data model diagram: receipts in the middle, 5 detail tables and 4 lookup tables, with their keys and row counts (`charts/00_data_model.png`).
- [x] T2 (P0) "Anatomy of a check" waterfall: menu prices $87.32M → item discounts → item sales $86.25M → check discounts → net sales $84.29M → tax → tips → $99.29M collected. It shows that 99.996% of receipts balance (`charts/03_check_waterfall.png`).
- [x] T3 (P0) Context slide: 127 stores, 115 days, 2.1M receipts, $99.3M collected, and the business question. Specified in the deck guide, slide 1.
- [ ] T4 (P1) Ask the organizers for the job ID lookup and what `Deleted` means in the employee file.

### 2. Data cleaning and preparation

- [x] T5 (P0) Build the clean layer. Apply every cleaning decision in the table below and write `phase1_eda/clean/`, with 21 yes/no flag columns (`flag_*`, `has_*`, `is_*`).
- [x] T6 (P0) Resolve the 1,800 possible duplicate groups by comparing their full contents. Result: 3,545 split bills kept, and 229 exact copies ($73) removed.
- [x] T7 (P0) Missing-values chart: the 3 always-empty fields that were dropped, and the one partly empty field kept (`charts/01_missing_values.png`).
- [x] T8 (P0) Cleaning funnel: raw → removed → clean → flagged → unflagged, plus the reasons for each flag (`charts/02_cleaning_funnel.png`).
- [ ] T9 (P1) Cleaning log for the appendix. Covered for now by the cleaning table in the deck guide (appendix A5) and `phase1_eda/reports/`.

### 3. Exploratory analysis and insights

- [x] T10 (P0) Trend: daily sales with a 7-day average. Per store per day, sales fell 18% ($6,574 → $5,404).
- [x] T11 (P0) Weekday × hour heatmap of check volume, plus void and discount rates by hour, weekday, store and employee, to show they barely move by time.
- [x] T12 (P0) Lever breakdown: discounts by name and voids by reason, ranked by dollars.
- [x] T13 (P0) Concentration curve: cumulative share of walkouts, voids and discounts against the share of employees.
- [x] T14 (P0) Store comparison: void rate vs discount rate for all 127 stores, sized by sales, with Munster labeled; plus Munster by month.
- [x] T15 (P0, promoted for the rubric's "relationships") Do the risk signals show up in the same people? Yes: top-10% voiders are 2.7× as likely to be top-10% for walkouts and 2.6× for discounts; 106 employees are top 10% on 3+ of 5 signals vs ~22 by chance (`charts/11_signals_stack_up.png`).
- [ ] T16 (P1) Manager and employee pairs: the same manager repeatedly approving the same server's voids or discounts.
- [ ] T17 (P1) Munster deep dive: which employees and void reasons drive its 2.3% void rate.
- [ ] T18 (P1) Employees flagged `Deleted` vs everyone else: compare their risk metrics.
- [ ] T18b (P1) Tip padding: servers who repeatedly have card tips above 50% or 100% of the bill.

### 4. Visualizations

- [x] T19 (P0) One chart style for every slide: one palette, titles that state the finding with its number, axes with units, and a source line.
- [x] T20 (P0) Final set: 12 charts. 9 go on slides and 3 go in the appendix (see "Charts" below). Each one proves exactly one claim.

### 5. Presentation and communication

- [x] T21 (P0) Storyboard: 11 slides plus appendix (below), written up in the deck guide.
- [x] T22 (P0) Build the deck from the deck guide, with a PDF backup.
- [x] T23 (P0) Rehearse with a timer (4:45 or under) and present. Presented Oct 8.
- [x] T24 Form and proof submitted.
- ~~T25 Databricks notebook~~ (dropped for Phase 1).

## Cleaning decisions

Core rule: in fraud work, outliers are signal, so we flag them instead of deleting them. Only structurally useless data gets dropped.

| Area | Issue | Decision |
|---|---|---|
| Types | Nested single-line JSON | Flatten into 7 Parquet tables (done) |
| Types | Schema drift between days: Quantity is integer on some days and decimal on others, and check Id is 128-bit on 3 days | Cast every column to one fixed type (done) |
| Types | Times stored as text ("2026-08-18T11:02") | Parse to datetime, then derive hour, weekday and duration (done) |
| Types | Tip stored as a negative `Gratuity` | Flip the sign into a `tip` column, keep the original (done) |
| Keys | check_id repeats across stores | Use the composite key: date + location_id + check_id (done) |
| Missing | Always empty: receipts' loyalty_id (100% empty) and service_charge (always $0), employees' IsEmancipated (100% empty) | Dropped all 3 (done) |
| Missing | 20 store-days missing across 7 stores | Keep the stores, normalize per open day |
| Missing | Gaps in the HR file: birth date, hire date, no job-ID lookup; employee_id 0 | Treat 0 as "system" and ask the organizers |
| Missing | Time zone field is wrong (Ohio stores are labeled Central) | Ignore it, since timestamps are already local |
| Duplicates | 3,774 receipts in 1,800 groups share every header and money field | Done: 3,545 split bills kept, 229 exact copies removed |
| Duplicates | 9,108 split-check groups | Legitimate: keep them and explain |
| Duplicates | 24,558 repeated names in the HR file | Never join on name |
| Outliers | $0 checks with 5,120 and 1,424 lines (store 42) | Flag (`flag_giant`) |
| Outliers | 52.5K zero-minute checks, 10.4K over 6 h, 18K after midnight | Keep and flag |
| Outliers | 167K zero-quantity lines, 766 negative prices, 3,779 negative payments (3,764 gift-card sales, 15 refunds) | Keep and flag |
| Outliers | 40% of guest counts are fractional, 190K are zero | Keep; use guest counts for dine-in only |
| Outliers | 11,508 checks with no items, 3,856 with no payment | Keep and flag |
| Outliers | 9 receipt numbers outside the normal 1–2.4M range: 3 card refunds numbered −1 with no original sale, 6 normal meals from a backup register | Keep and flag (`flag_odd_check_id`); the 3 unlinked refunds are a risk signal |
| Consistency | Duplicate labels: SERV ERR / SERVER ERR, NOT RECVD / NOT RECEVD, Postmates / POSTMATES, Pride / PRIDE, 1.5 OZ RANCH / 1.5OZ RANCH, 9 discount spellings | Normalize to one label each (`reports/label_merges.csv`) |
| Consistency | 67% of item lines are $0 | `line_type` on every line: menu item, combo part / add-on, modifier (child line with a $0 price), free line |
| Privacy | Names, birth dates and payroll IDs in the HR file | Dropped from `clean/employees.parquet`; IDs only (done) |

## Charts

All in `phase1_eda/charts/`, 2400 × 1350 px. Rebuild all with `python phase1_eda/scripts/charts.py` (about 5 seconds), or one with e.g. `python phase1_eda/scripts/charts.py 06`.

| Chart | What it shows | Slide |
|---|---|---|
| `00_data_model.png` | Every detail table links to one receipt (date + store + receipt #); 4 lookup tables turn IDs into names | 2 |
| `03_check_waterfall.png` | $87.32M menu prices → $99.29M collected; 99.996% of receipts balance | 3 |
| `02_cleaning_funnel.png` | 229 receipts removed, 2% flagged and kept, and why | 4 |
| `01_missing_values.png` | Only 3 fields were always empty and were dropped; ClosedDate is empty only for open stores | 5 |
| `04_daily_trend.png` | Weekly rhythm, Mother's/Father's Day peaks, −18% per store-day by August | 6 |
| `06_who_where_not_when.png` | Void/discount rates flat by hour and weekday, wide by store and employee | 7 (core insight) |
| `08_concentration_curve.png` | 5% of employees → 39% of walked-out receipts, 20% of void $, 21% of discount $ | 8 |
| `11_signals_stack_up.png` | Top-10% voiders are 2.7× as likely to be top-10% for walkouts, 2.6× for discounts; 106 employees on 3+ of 5 signals vs ~22 by chance | 9 ("relationships") |
| `09_store_scatter.png` | Munster voids 2.9× the chain median | 10 |
| `05_weekday_hour_heatmap.png` | Friday 6 PM is the busiest hour; dinner peaks every day | Appendix A1 |
| `07_discounts_and_voids.png` | Manager comps top discounts ($3.02M); order changes top voids ($0.73M) | Appendix A2 |
| `10_munster_by_month.png` | Munster is high every month, about 2.8× the other stores | Appendix A3 |

## 5-minute storyboard (11 slides, 4:50)

| # | Time | Slide (the claim) | Visual | Rubric row |
|---|---|---|---|---|
| 1 | 0:00–0:20 | Where can money leak at the register? 127 stores · 115 days · 2.1M receipts · $99.3M | KPI strip, no chart | Understanding |
| 2 | 0:20–0:50 | Every detail links back to one receipt | `00` data model | Understanding |
| 3 | 0:50–1:15 | Every receipt balances: 99.996% to the cent | `03` waterfall | Understanding |
| 4 | 1:15–1:50 | Only 229 receipts removed; 2% flagged and kept | `02` cleaning funnel | Cleaning |
| 5 | 1:50–2:15 | Only 3 fields were always empty; types fixed | `01` missing values + "Also fixed" list | Cleaning |
| 6 | 2:15–2:40 | Sales peak on weekends and holidays, and drift down 18% | `04` daily trend | Insights (trend) |
| 7 | 2:40–3:20 | Voids and discounts depend on where and who, not when | `06` who/where not when | Insights (pattern) |
| 8 | 3:20–3:45 | 5% of employees account for 39% of walked-out receipts | `08` concentration curve | Insights (comparison) |
| 9 | 3:45–4:10 | Risk signals stack up on the same employees | `11` signals stack up | Insights (relationship) |
| 10 | 4:10–4:30 | Munster voids 2.9× the chain median | `09` store scatter | Insights (comparison) |
| 11 | 4:30–4:50 | Risk is about who and where, not when → Phase 2 risk score | 3 takeaways, no chart | Communication |

**Appendix** (not presented, for Q&A): A1 heatmap (`05`), A2 discount and void reasons (`07`), A3 Munster by month (`10`), A4 glossary, A5 cleaning decisions, A6 method notes.

**If the rehearsal runs over 4:45:** first move slide 5 to the appendix, then slide 3. Never cut slides 7 or 9; they carry the main insight and the "relationships" item of the rubric.

## Notes for the script and Q&A

Short answers to the questions judges were likely to ask:

- **Which employees we compared:**
  - Chart 08 uses everyone who rang up sales: 3,183 people, excluding "system" lines. It shows shares of totals, so small sellers can't distort it.
  - Chart 06 keeps those with at least $5,000 in sales over the 115 days: 2,522. Below that, rates are noise: one $30 void on $300 of sales looks like a 10% void rate. The median employee sold $20.7K, so the cutoff mainly drops trainees, short stints and managers who rarely ring.
  - Chart 11 also requires at least 50 card payments, so the tip rate means something: 2,516.
  - Every signal is a rate (per dollar of sales, per receipt or per payment), so busy employees don't look worse just for being busy.
  - "Top 10%" means ranking all 2,516 on each rate separately and taking the highest 252.
  - "~22 by chance": if the 5 signals were unrelated, P(top 10% on 3+ of 5) ≈ 0.86%, and 0.86% × 2,516 ≈ 22.
  - Voids and discounts count against the employee who entered them, not the approving manager.
- **"Is this fraud?"** We can't say. The data has no fraud labels, so these are risk signals. Phase 2 turns them into a combined risk score per employee and store.
- **"What's a walkout?"** A customer who left without paying. The server zeroes the bill with a WALKOUT discount. The risk is a server who takes cash and then records it as a walkout.
- **"Why is Munster high?"** We don't know the cause. Its void rate is about 2.8× the other stores, every month. Its missing days (Aug 12–17) overlap with gaps at 3 nearby Indiana stores, so they look like a regional outage and aren't part of the story.
- **"What's an odd receipt number?"** 9 receipts numbered outside the normal 1 to 2.4 million range. 3 are card refunds with no original sale, 2 of them by the same employee. The other 6 come from a backup register.
- **"Why only 229 receipts removed?"** Weird receipts are the signal in fraud work, so we flag them instead of deleting them. Only exact copies were removed, worth $73 in total.
- **"Why did sales drop 18%?"** The data doesn't say why. It's per store per day, so missing stores don't explain it, and our risk signals are rates, so it doesn't affect them.
- **Role caveat:** job roles are unknown (the organizers gave no lookup for job IDs). Some overlap, like cash and voids, may come from the role (bartenders) rather than behavior.

## Phase 2 backlog

The Phase 2 brief (dates, deliverables, rubric) isn't in the repo yet. Add it here when the organizers publish it.


- Combine the signals (void, discount, walkout, comp, cash share, tips over the bill, self-approval) into one risk score per employee and per store.
- Open P1 tasks: T4 (job ID lookup, `Deleted` meaning), T16 (manager–employee pairs), T17 (Munster deep dive), T18 (`Deleted` employees), T18b (tip padding).
- Open questions for the organizers are listed in `EDA_LEARNINGS.md`, section 15.
