# Applebee's EDA Plan (Phase 1)

Tec de Monterrey x Sun Holdings x Databricks Data Challenge · Applebee's AI-Powered Fraud Detection track
Last updated: Oct 7, 2026, 11 PM · Live team version: https://claude.ai/code/artifact/3d05aa74-0b24-476f-b645-4fb429df27ca

## Goal

Present a 5-minute exploratory data analysis (EDA), with one presenter, that scores 4/4 on each of the five rubric rows:

1. Data understanding and context
2. Data cleaning and preparation
3. Exploratory analysis and insights
4. Visualizations
5. Presentation and communication

The organizers' structure is: quick dataset overview, key cleaning steps, top patterns, clear visuals, and a strong conclusion.

## Decisions (settled Oct 7)

- **Presentation is tomorrow, Thu Oct 8.** We run P0 tasks only. P1 tasks are optional polish.
- **Tooling:** Python, with DuckDB and pandas. Everyone analyzes the clean tables in `eda_work/clean/`. No Databricks notebook for now.
- **Repo:** code and docs live in git; data never does. Teammates set up with `README.md`, and either get `clean.zip` from Santiago or rebuild with `python eda_work/scripts/build_all.py`.
- **Deck:** on hold until the whole team understands the data.
- **Form and proof:** already submitted.
- **Framing rule:** the data has no fraud labels. We say "risk signals" and "anomalies", never "fraud". We never show employee names, only IDs.

## Status and next steps

| Step | What | Tasks | State |
|---|---|---|---|
| 0 | Ingest: 115 daily JSON files (11 GB) → 7 flat Parquet tables, profile every table | T0 | Done |
| 1 | Clean tables: positive tip, merged labels, line types, flags, anonymized employees → `eda_work/clean/` | T5 | Done |
| 2 | Duplicates: 1,800 look-alike **groups** holding 3,774 receipts → 3,545 split bills kept, 229 exact copies ($73) removed | T6 | Done |
| — | Repo: one-command rebuild (`build_all.py`), setup checker (`check_setup.py`), `README.md` for teammates | — | Done |
| 3 | Cleaning visuals: missing-values chart and cleaning funnel (`01`, `02`) | T7, T8 | Done |
| 4 | Analysis charts (`03`–`10`), one shared style, built by `charts.py` | T2, T10–T14, T19, T20 | Done; team picks which go in the deck |
| 5 | Deck, script, two timed rehearsals | T1, T3, T21–T23 | Not started |

The full pipeline has been tested end to end: a rebuild reproduces the same rows and the same cleaning numbers.

## Task list

P0 means needed for a 4/4 score. P1 means polish if time allows. T5 and T6 are done, so every chart can now read from the clean layer.

### 1. Data understanding and context

- [x] T0 (P0) Ingest and flatten all 115 days into Parquet, then profile every table.
- [ ] T1 (P0) Schema diagram: 4 reference tables and 7 fact tables, with their keys and what one row means.
- [x] T2 (P0) "Anatomy of a check" waterfall: gross $87.1M → item discounts → item sales $86.2M → check discounts → tax → tips → $99.3M collected. It shows that 99.996% of checks balance.
- [ ] T3 (P0) Context strip: 127 stores, 115 days, 2.14M checks, channel mix, and the business question: where can money leak at the register?
- [ ] T4 (P1) Ask the organizers for the job ID lookup and what `Deleted` means in the employee file.

### 2. Data cleaning and preparation

- [x] T5 (P0) Build the clean layer. Apply every cleaning decision in the table below and write `eda_work/clean/`, with flag columns: is_modifier, is_empty_check, is_unbalanced, is_dup_candidate, is_long_check.
- [x] T6 (P0) Resolve the 1,800 possible duplicate groups by comparing their item lines. Result: 3,545 split bills, and 229 exact copies ($73) removed.
- [x] T7 (P0) Missing-values chart: every column with any gap and the decision taken (`charts/01_missing_values.png`).
- [x] T8 (P0) Cleaning funnel: raw records → flagged → excluded, with counts at each step. One slide.
- [ ] T9 (P1) Cleaning log for the appendix: every decision with before and after counts, ready for Q&A.

### 3. Exploratory analysis and insights

- [x] T10 (P0) Trend: daily sales with a 7-day average. Per store per day, sales fell 18% ($6,574 → $5,404).
- [x] T11 (P0) Weekday × hour heatmap of check volume, plus void and discount rates by weekday and hour, to show they barely move.
- [x] T12 (P0) Lever breakdown: voids by reason, discounts by name, comps, walkouts and cash share, ranked by dollars.
- [x] T13 (P0) Concentration curve: cumulative share of walkouts, voids and discounts against the share of employees.
- [x] T14 (P0) Store comparison: void rate vs discount rate for all 127 stores, sized by sales, with Munster labeled.
- [ ] T15 (P1) Relationships: correlations among employee risk metrics (void rate, discount rate, walkouts, cash share, self-approvals, refunds, tip %). Do the signals show up in the same people?
- [ ] T16 (P1) Manager and employee pairs: the same manager repeatedly approving the same server's voids or discounts.
- [ ] T17 (P1) Munster deep dive: which employees and void reasons drive its 2.3% void rate.
- [ ] T18 (P1) Employees flagged `Deleted` vs everyone else: compare their risk metrics.
- [ ] T18b (P1) Tip padding: servers who repeatedly have card tips above 50% or 100% of the bill.

### 4. Visualizations

- [x] T19 (P0) One chart style for every slide: one palette, titles that state the finding with its number, axes with units, and a source line.
- [x] T20 (P0) Final set of 6 charts: check waterfall, cleaning funnel, trend with heatmap, lever bars, concentration curve and store scatter. Each one proves exactly one slide's claim.

### 5. Presentation and communication

- [ ] T21 (P0) Team approves the storyboard below.
- [ ] T22 (P0) Deck: 7 slides plus an appendix (data dictionary, cleaning log, backup charts) for Q&A.
- [ ] T23 (P0) Script of about 650 words, and 2 timed run-throughs under 4:45.
- [x] T24 Form and proof submitted.
- ~~T25 Databricks notebook~~ (dropped for Phase 1).

## Cleaning decisions

Core rule: in fraud work, outliers are signal, so we flag them instead of deleting them. Only structurally useless data gets dropped.

| Area | Issue | Decision |
|---|---|---|
| Types | Nested single-line JSON | Flatten into 7 Parquet tables (done) |
| Types | Schema drift between days: Quantity is integer on some days and decimal on others, and check Id is 128-bit on 3 days | Cast every column to one fixed type (done) |
| Types | Times stored as text ("2026-08-18T11:02") | Parse to datetime, then derive hour, weekday and duration |
| Types | Tip stored as a negative `Gratuity` | Flip the sign into a `tip` column |
| Keys | check_id repeats across stores | Use the composite key: date + location_id + check_id (done) |
| Missing | loyalty_id is 100% null and service_charge is 100% zero | Drop both columns |
| Missing | 20 store-days missing across 7 stores | Keep the stores, normalize per open day, and flag the gaps |
| Missing | Gaps in the HR file: birth date, hire date, no job-ID lookup; employee_id 0 | Treat 0 as "system" and ask the organizers |
| Missing | Time zone field is wrong (Ohio stores are labeled Central) | Ignore it, since timestamps are already local |
| Duplicates | 3,774 checks in 1,800 groups share every header and money field | Done: 3,545 split bills kept, 229 exact copies removed |
| Duplicates | 9,108 split-check groups | Legitimate: keep them and explain |
| Duplicates | 24,558 repeated names in the HR file | Never join on name |
| Outliers | $0 checks with 5,120 and 1,424 lines (store 42) | Flag |
| Outliers | 52.5K zero-minute checks, 10.4K over 6 h, 18K after midnight | Keep and flag |
| Outliers | 167K zero-quantity lines, 766 negative prices, 3,779 negative payments (3,764 gift-card sales, 15 refunds) | Keep and flag |
| Outliers | 40% of guest counts are fractional, 190K are zero | Keep; use guest counts for dine-in only |
| Outliers | 11,508 checks with no items, 3,856 with no payment | Keep and flag |
| Consistency | Duplicate labels: SERV ERR / SERVER ERR, NOT RECVD / NOT RECEVD, Postmates / POSTMATES, Pride / PRIDE, 1.5 OZ RANCH / 1.5OZ RANCH | Normalize to one label each |
| Consistency | 67% of item lines are $0 modifiers | Add `is_modifier` (child line with $0 price; combo components are priced, so don't use parent_seq alone) |
| Privacy | Names and birth dates in the HR file | Drop names and show IDs only |

## Charts

| Chart (`eda_work/charts/`) | What it shows | Slide |
|---|---|---|
| `01_missing_values.png` | 104 of 109 columns complete; the 2 empty ones dropped | 3 (cleaning) |
| `02_cleaning_funnel.png` | 229 receipts removed, 2% flagged and kept, and why | 3 (cleaning) |
| `03_check_waterfall.png` | $87.32M menu prices → $99.29M collected; 99.996% of receipts balance | 2 (understanding) |
| `04_daily_trend.png` | Weekly rhythm, Mother's/Father's Day peaks, −18% per store-day by August | 4 (baseline) |
| `05_weekday_hour_heatmap.png` | Friday 6 PM is the busiest hour; dinner peaks every day | 4 (baseline) or appendix |
| `06_who_where_not_when.png` | Void/discount rates flat by hour and weekday, wide by store and employee | 4 or 5 (core insight) |
| `07_discounts_and_voids.png` | Manager comps top discounts ($3.02M); order changes top voids ($0.73M) | 5 (levers) |
| `08_concentration_curve.png` | 5% of employees → 39% of walked-out receipts, 20% of void $, 21% of discount $ | 5 (levers) |
| `09_store_scatter.png` | Munster voids 2.9× the chain median | 6 (stores) |
| `10_munster_by_month.png` | Munster is high every month, about 2.8× the other stores | 6 (stores) or appendix |

Rebuild all charts with `python eda_work/scripts/charts.py` (about 5 seconds), or one chart with e.g. `python eda_work/scripts/charts.py 06`.

## 5-minute storyboard

| # | Time | Slide title (the claim) | Visual | Rubric row |
|---|---|---|---|---|
| 1 | 0:00–0:30 | 127 stores, 115 days, 2.14M checks: where can money leak at the register? | Context strip, channel mix | Understanding |
| 2 | 0:30–1:10 | Every check balances to the cent, so we can trust the money | Schema and `03` waterfall | Understanding |
| 3 | 1:10–1:55 | 11 GB of nested JSON became 7 clean tables; outliers are flagged, not deleted | `02` funnel + `01` missing values | Cleaning |
| 4 | 1:55–2:35 | Sales follow the week, but voids stay near 0.8% every day and hour | `04` daily trend + `06` where/who not when | Insights |
| 5 | 2:35–3:25 | $3M in discounts and $726K in voids; 5% of employees drive 39% of walked-out receipts | `07` levers + `08` concentration curve | Insights, Visuals |
| 6 | 3:25–4:15 | Stores differ up to 7×; Munster voids nearly 3× the chain average, every month | `09` store scatter (+ `10` by month) | Insights |
| 7 | 4:15–4:50 | Risk is about who and where, so Phase 2 scores employees and stores | 3 takeaways and next step | Communication |

The appendix holds the data dictionary, the cleaning log and backup charts for Q&A.

## Roles

| Role | Owns | Tasks |
|---|---|---|
| Data lead | Clean layer, duplicates, missing values, cleaning funnel | T5–T9 |
| Insights analyst | Trends, levers, concentration, stores | T10–T18b |
| Visuals and deck | Schema, waterfall, chart style, final charts, deck | T1–T3, T19–T22 |
| Presenter | Storyboard, script, rehearsals | T21, T23 |

With 3 people, merge "Visuals and deck" with "Presenter". The presenter owns the script from the start, because delivery is a full rubric row.
