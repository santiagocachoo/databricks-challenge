# Applebee's Fraud Detection: Data Challenge (team repo)

> **Phase 1 archive (Oct 28, 2026).** This was the repo README for Phase 1 (local EDA with DuckDB). It moved here unchanged except for paths: `eda_work/` is now `phase1_eda/`, and the Phase 1 docs are in `phase1_eda/docs/`. Commands below still run from the **repo root**. For Phase 2 (the Databricks pipeline), see the [root README](../README.md).

Tec de Monterrey × Sun Holdings × Databricks Data Challenge · Applebee's AI-Powered Fraud Detection track.

This repo holds our code and docs. **The data is not in git.** You add it yourself in step 3 below.

**New here?** Read [`phase1_eda/docs/TEAM_BRIEFING.md`](docs/TEAM_BRIEFING.md) first (7 minutes), then follow the setup below **in order**.

---

## What's in the repo, and what isn't

```
databricks-challenge/                  <- the repo (git clone creates this folder)
├── README.md                          <- this guide
├── requirements.txt                   <- Python libraries to install
├── .gitignore                         <- keeps data and your virtual environment out of git
├── docs/
│   ├── TEAM_BRIEFING.md               <- start here
│   ├── EDA_PLAN.md                    <- tasks, 5-minute storyboard, decisions
│   ├── EDA_LEARNINGS.md               <- every number and finding so far
│   └── DECK_GUIDE.md                  <- Phase 1 deck plan (charts embedded)
├── phase1_eda/
│   ├── scripts/                       <- all the code (see "Scripts" below)
│   ├── reports/                       <- small cleaning reports (these ARE in git)
│   ├── charts/                        <- the presentation charts as PNGs (these ARE in git)
│   ├── parquet/                       <- NOT in git · built by the scripts
│   └── clean/                         <- NOT in git · the clean tables we analyze  <- you need this
└── Applebees Challenge/               <- NOT in git · the raw dataset (11 GB), only needed to rebuild
```

The data folders are excluded on purpose:

- They are big: 11 GB raw plus about 650 MB built. GitHub refuses files over 100 MB.
- The raw data belongs to the organizers, and the HR file contains employee names and birth dates.

---

## Setup (about 15 minutes)

### Step 1: Clone the repo

**Mac:**

```bash
cd ~/Desktop
git clone https://github.com/santiagocachoo/databricks-challenge.git
cd databricks-challenge
```

**Windows (PowerShell):**

```powershell
cd $HOME\Desktop
git clone https://github.com/santiagocachoo/databricks-challenge.git
cd databricks-challenge
```

**Every command from here on is run from inside the `databricks-challenge` folder.**

### Step 2: Create your Python environment

A virtual environment (`.venv`) keeps this project's libraries separate from the rest of your computer. Each person creates their own; it is never committed.

**Mac:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r phase1_eda/requirements.txt
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r phase1_eda/requirements.txt
```

- When the environment is active, your prompt starts with `(.venv)`.
- **Activate it again every time you open a new terminal:**
  - Mac: `source .venv/bin/activate`
  - Windows: `.venv\Scripts\Activate.ps1`
- **Windows:** if PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, answer `Y`, then activate again.
- **VS Code:** press `Cmd/Ctrl+Shift+P` → "Python: Select Interpreter" → choose the one inside `.venv`.
- **Jupyter notebooks in VS Code** also need this: `pip install ipykernel`.

### Step 3: Get the data (choose ONE path)

#### Path A: prebuilt clean tables (fastest, recommended)

1. Download **`clean.zip`**
2. Unzip it **inside the `phase1_eda` folder**, so you end up with exactly these files:
   ```
   phase1_eda/clean/checks.parquet
   phase1_eda/clean/items.parquet
   phase1_eda/clean/discounts.parquet
   phase1_eda/clean/voids.parquet
   phase1_eda/clean/payments.parquet
   phase1_eda/clean/taxes.parquet
   phase1_eda/clean/stores.parquet
   phase1_eda/clean/channels.parquet
   phase1_eda/clean/employees.parquet
   phase1_eda/clean/removed_duplicates.parquet
   ```
   **Common mistake:** a double folder like `phase1_eda/clean/clean/checks.parquet`. If that happens, move the files up one level.

You can analyze everything with this. You won't be able to rebuild from raw, which is fine.

#### Path B: rebuild from the raw data (if you want to run the whole pipeline)

1. Get the raw dataset from the organizers' dataset link.
2. Put it at the root of the repo, named **exactly** `Applebees Challenge`: a space between the words, capital A and capital C. If your download is named something else (e.g. `Applebees_Clean_Dataset`), rename it. It must look like this:
   ```
   databricks-challenge/Applebees Challenge/dimensions/locations/locations.json
   databricks-challenge/Applebees Challenge/dimensions/revenue_centers/revenueCenters.json
   databricks-challenge/Applebees Challenge/dimensions/items/items.json
   databricks-challenge/Applebees Challenge/dimensions/employees/employees.json
   databricks-challenge/Applebees Challenge/facts/checks/brand=rmh/dt=2026-04-28/checks.json
   ... (115 dt= folders, from 2026-04-28 to 2026-08-20)
   ```
   **Common mistake:** a double folder after unzipping, like `Applebees Challenge/Applebees Challenge/dimensions`. Move the contents up one level.
3. Run the whole pipeline with one command:

   ```bash
   python phase1_eda/scripts/build_all.py
   ```

   - It takes about 4–6 minutes the first time and prints one line per day converted.
   - If it gets interrupted, just run it again: finished days are skipped, and a half-written day is never kept.
   - The result is identical to everyone else's: we tested that a rebuild reproduces the same rows.

### Step 4: Verify your setup

```bash
python phase1_eda/scripts/check_setup.py
```

It checks Python, the libraries, the raw data and the built tables, and tells you what to fix. It never changes anything.

- **Ready:** the last line says **`ALL GOOD - you can analyze phase1_eda/clean/.`**
- **Path A users:** section 2 (raw data) will say MISSING. That's expected and still ends in ALL GOOD.

### Step 5: First look (proves it works)

Run this from the repo folder with the environment active (`python`, then paste it):

```python
import pandas as pd
checks = pd.read_parquet("phase1_eda/clean/checks.parquet")
print(len(checks))   # must print 2142617
print(checks[["dt", "store_name", "channel_group", "net_sales", "tips", "has_void", "flag_unbalanced"]].head())
```

The same data in SQL, with DuckDB:

```python
import duckdb
duckdb.sql("""
    SELECT store_name, round(sum(void_amount) / sum(gross_sales) * 100, 2) AS void_pct
    FROM 'phase1_eda/clean/checks.parquet'
    GROUP BY store_name ORDER BY void_pct DESC LIMIT 3
""").df()
# Munster 2.29 · Grand Island 1.73 · Clinton 1.69
```

**Paths are relative to the repo folder.** A notebook in a subfolder such as `notebooks/` must use `../phase1_eda/clean/checks.parquet`.

---

## The clean tables (`phase1_eda/clean/`)

A receipt is identified by **`dt` + `location_id` + `check_id`**. Use all three to join tables: `check_id` alone repeats across stores.

| File                         | One row is             | Rows       | Notes                                                                                                       |
| ---------------------------- | ---------------------- | ---------- | ----------------------------------------------------------------------------------------------------------- |
| `checks.parquet`             | one receipt            | 2,142,617  | 53 columns: times, store, channel, money totals, and three kinds of flags (below)                           |
| `items.parquet`              | one line on a receipt  | 28,558,894 | `line_type` = menu item / combo part / add-on / modifier / free line. Large: load only the columns you need |
| `discounts.parquet`          | one discount line      | 516,689    | Item- and check-level together (`level`). `discount_name` is cleaned; `discount_name_raw` is the original   |
| `voids.parquet`              | one voided item        | 178,293    | `void_reason` is cleaned, plus `void_reason_desc` in plain English                                          |
| `payments.parquet`           | one payment            | 2,232,076  | `tip` is positive, `tip_pct`, `method_group` (Card, Cash, Delivery app…)                                    |
| `taxes.parquet`              | one tax line           | 2,569,632  |                                                                                                             |
| `stores.parquet`             | one store              | 185        | `active_in_data` is true for the 127 stores with sales                                                      |
| `channels.parquet`           | one sales channel      | 23         | `channel_group`: Dine-in, To go, Online order, Delivery app, Catering, Other                                |
| `employees.parquet`          | one employee record    | 156,975    | **No names or birth dates.** `rings_sales` marks the 3,183 who appear in sales                              |
| `removed_duplicates.parquet` | one removed exact copy | 229        | Which receipt each copy duplicated (`kept_check_id`)                                                        |

Flag columns on `checks.parquet`. **Nothing flagged was deleted**; filter with them as needed:

- **`flag_*`: data-quality problems.** Examples: `flag_unbalanced`, `flag_no_items`, `flag_no_payment`, `flag_giant`, `flag_long_open`.
- **`has_*` / `is_fully_comped`: risk behaviors.** Examples: `has_void`, `has_walkout`, `has_tip_over_bill`, `has_refund`.
- **`is_*`: normal context.** Examples: `is_instant` (to-go and delivery), `is_after_midnight`, `is_split_guests`, `is_lookalike_split`.

The full cleaning results are in `phase1_eda/reports/`:

- `cleaning_summary.json`: the funnel and flag counts
- `missing_values.csv`: null % and zero % for every column
- `label_merges.csv`: every label we merged
- `removed_duplicates.csv`: the receipts we removed

---

## Scripts (`phase1_eda/scripts/`)

Run every script from the repo folder, e.g. `python phase1_eda/scripts/check_setup.py`.

| Script                                     | What it does                                                                               | When to run it                                                           |
| ------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ |
| `check_setup.py`                           | Checks your setup; changes nothing                                                         | After setup, or whenever something looks wrong                           |
| `build_all.py`                             | Runs the 3 build steps below, in order                                                     | Path B, or after changing a cleaning rule                                |
| `convert.py`                               | Raw JSON → `phase1_eda/parquet/<table>/<date>.parquet` (7 flat tables)                       | Through `build_all.py`                                                   |
| `build_check_summary.py`                   | One row per receipt with its totals → `phase1_eda/parquet/check_summary/`                    | Through `build_all.py`                                                   |
| `clean.py`                                 | Builds `phase1_eda/clean/` and `phase1_eda/reports/` (flags, merged labels, duplicate removal) | Through `build_all.py`                                                   |
| `charts.py`                                | Builds every presentation chart into `phase1_eda/charts/` (~5 s)                             | After `clean/` exists, or after editing a chart                          |
| `dup_check.py`                             | The duplicate analysis, step by step                                                       | To understand or re-check the duplicate decision                         |
| `q.py` + `p1.py`…`p12.py`, `e1.py`…`e3.py` | The original profiling queries behind every number in `phase1_eda/docs/`                              | Optional. Example: `python phase1_eda/scripts/q.py phase1_eda/scripts/p6.py` |
| `peek.py`                                  | Shows the structure of one raw day file                                                    | Optional                                                                 |

---

## Working together with git

1. **Before you start working:** `git pull`
2. **Work in your own files.** Name notebooks with your initials (e.g. `notebooks/sc_trends.ipynb`). Two people editing the same notebook almost always causes a conflict.
3. **Commit small and often, saying what and why:**
   ```bash
   git status                      # check what changed: no .parquet, .json data or .zip files should appear
   git add <the files you changed>
   git commit -m "add weekday x hour heatmap for voids"
   git pull --rebase               # get teammates' work first
   git push
   ```
4. **Never commit data.** `.gitignore` blocks the data folders. If `git status` ever lists a `.parquet`, a `.zip` or anything under `Applebees Challenge/`, stop and ask.
5. **Changing a cleaning rule:**
   - Edit `clean.py`.
   - Run `python phase1_eda/scripts/build_all.py`.
   - Commit the script **and** the updated `phase1_eda/reports/` together, with the reason in the message. That way git keeps the history of every cleanup decision and its effect on the numbers.
   - Then tell the team to rebuild, or share a new `clean.zip`.
6. **Never show employee names.** Use IDs only. The data has no fraud labels, so say "risk signal" or "anomaly", never "fraud".

---

## Troubleshooting

| Problem                                                     | Fix                                                                                                                           |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'duckdb'` (or pandas) | The environment isn't active. Run `source .venv/bin/activate` (Mac) or `.venv\Scripts\Activate.ps1` (Windows), then try again |
| `command not found: python` (Mac, outside the environment)  | Use `python3`. Inside `.venv`, `python` works                                                                                 |
| `'python3' is not recognized` (Windows)                     | Use `py`, or reinstall Python with "Add python.exe to PATH" ticked                                                            |
| `check_setup.py` shows `0 of 115 daily files`               | The raw folder is misnamed or nested. It must be exactly `Applebees Challenge/facts/checks/brand=rmh/...` at the repo root    |
| `FileNotFoundError: ... phase1_eda/clean/checks.parquet`      | You're not in the repo folder (`cd` into it), or path A unzipped to the wrong place                                           |
| Rebuild is very slow or the computer freezes                | Close other heavy apps and run `build_all.py` again. It resumes where it stopped                                              |
| `git push` is rejected                                      | Someone pushed first. Run `git pull --rebase`, then `git push`                                                                |
| Merge conflict in a notebook                                | Keep your version under a new name, take theirs, and tell the team. Next time, use separate notebooks                         |

---
