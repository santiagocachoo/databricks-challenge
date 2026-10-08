# Applebee's Fraud Detection: Data Challenge (team repo)

Tec de Monterrey × Sun Holdings × Databricks Data Challenge · Applebee's AI-Powered Fraud Detection track.

This repo holds our code and docs. **The data is not in git.** You add it yourself in step 3 below.

**New here?** Read [`docs/TEAM_BRIEFING.md`](docs/TEAM_BRIEFING.md) first (7 minutes), then follow the setup below **in order**.

---

## What's in the repo, and what isn't

```
Databricks_challenge/                  <- the repo (folder name doesn't matter)
├── README.md                          <- this guide
├── requirements.txt                   <- Python libraries to install
├── .gitignore                         <- keeps data and your virtual environment out of git
├── docs/
│   ├── TEAM_BRIEFING.md               <- start here
│   ├── EDA_PLAN.md                    <- tasks, 5-minute storyboard, roles
│   └── EDA_LEARNINGS.md               <- every number and finding so far
├── eda_work/
│   ├── scripts/                       <- all the code (see "Scripts" below)
│   ├── reports/                       <- small cleaning reports (these ARE in git)
│   ├── parquet/                       <- NOT in git · built by the scripts
│   └── clean/                         <- NOT in git · the clean tables we analyze  <- you need this
└── Applebees Challenge/               <- NOT in git · the raw dataset (11 GB), only needed to rebuild
```

The data folders are excluded on purpose:
- They are big: 11 GB raw plus about 650 MB built. GitHub refuses files over 100 MB.
- The raw data belongs to the organizers, and the HR file contains employee names and birth dates.

---

## Setup (about 15 minutes)

### Step 0: Check what you need

| Need | How to check | If it's missing |
|---|---|---|
| Access to the GitHub repo | You received an email invite from GitHub | Ask Santiago to add you as a collaborator, then **accept the invite** in the email |
| Git | `git --version` | **Mac:** run `xcode-select --install`. **Windows:** install from git-scm.com (keep the default options) |
| Python 3.9 or newer (3.10+ recommended) | **Mac:** `python3 --version` · **Windows:** `py --version` | Install from python.org. **Windows:** tick **"Add python.exe to PATH"** in the installer |
| Disk space | — | About 1 GB if you use the prebuilt tables (step 3, path A). About 13 GB if you rebuild from raw (path B) |
| Memory | — | 8 GB RAM is enough. The scripts cap themselves at about 2 GB |

All commands below run in a terminal:
- **Mac:** use the Terminal app, or VS Code → Terminal → New Terminal.
- **Windows:** use PowerShell, or the VS Code terminal.

### Step 1: Clone the repo

**Mac:**
```bash
cd ~/Desktop
git clone <REPO_URL> Databricks_challenge
cd Databricks_challenge
```

**Windows (PowerShell):**
```powershell
cd $HOME\Desktop
git clone <REPO_URL> Databricks_challenge
cd Databricks_challenge
```

> `<REPO_URL>` is the address Santiago shares, e.g. `https://github.com/<owner>/<repo>.git`.
>
> If git asks for a password: GitHub no longer accepts your account password there. Do one of these, then run `git clone` again:
> - Run `gh auth login` (GitHub CLI), or
> - Clone with GitHub Desktop (File → Clone repository), or
> - Use a personal access token as the password (GitHub → Settings → Developer settings → Personal access tokens).

**Every command from here on is run from inside the `Databricks_challenge` folder.**

### Step 2: Create your Python environment

A virtual environment (`.venv`) keeps this project's libraries separate from the rest of your computer. Each person creates their own; it is never committed.

**Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
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

1. Download **`clean.zip`** from the Google Drive link Santiago shares (about 300 MB).
2. Unzip it **inside the `eda_work` folder**, so you end up with exactly these files:
   ```
   eda_work/clean/checks.parquet
   eda_work/clean/items.parquet
   eda_work/clean/discounts.parquet
   eda_work/clean/voids.parquet
   eda_work/clean/payments.parquet
   eda_work/clean/taxes.parquet
   eda_work/clean/stores.parquet
   eda_work/clean/channels.parquet
   eda_work/clean/employees.parquet
   eda_work/clean/removed_duplicates.parquet
   ```
   **Common mistake:** a double folder like `eda_work/clean/clean/checks.parquet`. If that happens, move the files up one level.

You can analyze everything with this. You won't be able to rebuild from raw, which is fine.

#### Path B: rebuild from the raw data (if you want to run the whole pipeline)

1. Get the raw dataset, either from the organizers' dataset link or from Santiago.
2. Put it at the root of the repo, named **exactly** `Applebees Challenge`: a space between the words, capital A and capital C. If your download is named something else (e.g. `Applebees_Clean_Dataset`), rename it. It must look like this:
   ```
   Databricks_challenge/Applebees Challenge/dimensions/locations/locations.json
   Databricks_challenge/Applebees Challenge/dimensions/revenue_centers/revenueCenters.json
   Databricks_challenge/Applebees Challenge/dimensions/items/items.json
   Databricks_challenge/Applebees Challenge/dimensions/employees/employees.json
   Databricks_challenge/Applebees Challenge/facts/checks/brand=rmh/dt=2026-04-28/checks.json
   ... (115 dt= folders, from 2026-04-28 to 2026-08-20)
   ```
   **Common mistake:** a double folder after unzipping, like `Applebees Challenge/Applebees Challenge/dimensions`. Move the contents up one level.
3. Run the whole pipeline with one command:
   ```bash
   python eda_work/scripts/build_all.py
   ```
   - It takes about 4–6 minutes the first time and prints one line per day converted.
   - If it gets interrupted, just run it again: finished days are skipped, and a half-written day is never kept.
   - The result is identical to everyone else's: we tested that a rebuild reproduces the same rows.

### Step 4: Verify your setup

```bash
python eda_work/scripts/check_setup.py
```

It checks Python, the libraries, the raw data and the built tables, and tells you what to fix. It never changes anything.

- **Ready:** the last line says **`ALL GOOD - you can analyze eda_work/clean/.`**
- **Path A users:** section 2 (raw data) will say MISSING. That's expected and still ends in ALL GOOD.

### Step 5: First look (proves it works)

Run this from the repo folder with the environment active (`python`, then paste it):

```python
import pandas as pd
checks = pd.read_parquet("eda_work/clean/checks.parquet")
print(len(checks))   # must print 2142617
print(checks[["dt", "store_name", "channel_group", "net_sales", "tips", "has_void", "flag_unbalanced"]].head())
```

The same data in SQL, with DuckDB:

```python
import duckdb
duckdb.sql("""
    SELECT store_name, round(sum(void_amount) / sum(gross_sales) * 100, 2) AS void_pct
    FROM 'eda_work/clean/checks.parquet'
    GROUP BY store_name ORDER BY void_pct DESC LIMIT 3
""").df()
# Munster 2.29 · Grand Island 1.73 · Clinton 1.69
```

**Paths are relative to the repo folder.** A notebook in a subfolder such as `notebooks/` must use `../eda_work/clean/checks.parquet`.

---

## The clean tables (`eda_work/clean/`)

A receipt is identified by **`dt` + `location_id` + `check_id`**. Use all three to join tables: `check_id` alone repeats across stores.

| File | One row is | Rows | Notes |
|---|---|---|---|
| `checks.parquet` | one receipt | 2,142,617 | 53 columns: times, store, channel, money totals, and three kinds of flags (below) |
| `items.parquet` | one line on a receipt | 28,558,894 | `line_type` = menu item / combo part / add-on / modifier / free line. Large: load only the columns you need |
| `discounts.parquet` | one discount line | 516,689 | Item- and check-level together (`level`). `discount_name` is cleaned; `discount_name_raw` is the original |
| `voids.parquet` | one voided item | 178,293 | `void_reason` is cleaned, plus `void_reason_desc` in plain English |
| `payments.parquet` | one payment | 2,232,076 | `tip` is positive, `tip_pct`, `method_group` (Card, Cash, Delivery app…) |
| `taxes.parquet` | one tax line | 2,569,632 | |
| `stores.parquet` | one store | 185 | `active_in_data` is true for the 127 stores with sales |
| `channels.parquet` | one sales channel | 23 | `channel_group`: Dine-in, To go, Online order, Delivery app, Catering, Other |
| `employees.parquet` | one employee record | 156,975 | **No names or birth dates.** `rings_sales` marks the 3,183 who appear in sales |
| `removed_duplicates.parquet` | one removed exact copy | 229 | Which receipt each copy duplicated (`kept_check_id`) |

Flag columns on `checks.parquet`. **Nothing flagged was deleted**; filter with them as needed:
- **`flag_*`: data-quality problems.** Examples: `flag_unbalanced`, `flag_no_items`, `flag_no_payment`, `flag_giant`, `flag_long_open`.
- **`has_*` / `is_fully_comped`: risk behaviors.** Examples: `has_void`, `has_walkout`, `has_tip_over_bill`, `has_refund`.
- **`is_*`: normal context.** Examples: `is_instant` (to-go and delivery), `is_after_midnight`, `is_split_guests`, `is_lookalike_split`.

The full cleaning results are in `eda_work/reports/`:
- `cleaning_summary.json`: the funnel and flag counts
- `missing_values.csv`: null % and zero % for every column
- `label_merges.csv`: every label we merged
- `removed_duplicates.csv`: the receipts we removed

---

## Scripts (`eda_work/scripts/`)

Run every script from the repo folder, e.g. `python eda_work/scripts/check_setup.py`.

| Script | What it does | When to run it |
|---|---|---|
| `check_setup.py` | Checks your setup; changes nothing | After setup, or whenever something looks wrong |
| `build_all.py` | Runs the 3 build steps below, in order | Path B, or after changing a cleaning rule |
| `convert.py` | Raw JSON → `eda_work/parquet/<table>/<date>.parquet` (7 flat tables) | Through `build_all.py` |
| `build_check_summary.py` | One row per receipt with its totals → `eda_work/parquet/check_summary/` | Through `build_all.py` |
| `clean.py` | Builds `eda_work/clean/` and `eda_work/reports/` (flags, merged labels, duplicate removal) | Through `build_all.py` |
| `dup_check.py` | The duplicate analysis, step by step | To understand or re-check the duplicate decision |
| `q.py` + `p1.py`…`p12.py`, `e1.py`…`e3.py` | The original profiling queries behind every number in `docs/` | Optional. Example: `python eda_work/scripts/q.py eda_work/scripts/p6.py` |
| `peek.py` | Shows the structure of one raw day file | Optional |

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
   - Run `python eda_work/scripts/build_all.py`.
   - Commit the script **and** the updated `eda_work/reports/` together, with the reason in the message. That way git keeps the history of every cleanup decision and its effect on the numbers.
   - Then tell the team to rebuild, or share a new `clean.zip`.
6. **Never show employee names.** Use IDs only. The data has no fraud labels, so say "risk signal" or "anomaly", never "fraud".

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'duckdb'` (or pandas) | The environment isn't active. Run `source .venv/bin/activate` (Mac) or `.venv\Scripts\Activate.ps1` (Windows), then try again |
| `command not found: python` (Mac, outside the environment) | Use `python3`. Inside `.venv`, `python` works |
| `'python3' is not recognized` (Windows) | Use `py`, or reinstall Python with "Add python.exe to PATH" ticked |
| `check_setup.py` shows `0 of 115 daily files` | The raw folder is misnamed or nested. It must be exactly `Applebees Challenge/facts/checks/brand=rmh/...` at the repo root |
| `FileNotFoundError: ... eda_work/clean/checks.parquet` | You're not in the repo folder (`cd` into it), or path A unzipped to the wrong place |
| Rebuild is very slow or the computer freezes | Close other heavy apps and run `build_all.py` again. It resumes where it stopped |
| `git push` is rejected | Someone pushed first. Run `git pull --rebase`, then `git push` |
| Merge conflict in a notebook | Keep your version under a new name, take theirs, and tell the team. Next time, use separate notebooks |

---

## For Santiago (repo owner, one-time setup)

1. **Create the GitHub repo.** On github.com: New repository → **Private** → name it → **do not** add a README, `.gitignore` or license (we already have them) → Create.
2. **Push this folder to it:**
   ```bash
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
3. **Add the teammates.** Repo → Settings → Collaborators → Add people.
4. **Replace `<REPO_URL>` in this README** with the real URL, then commit and push.
5. **Share the clean tables** (path A). Run this from the repo folder:
   ```bash
   cd eda_work && zip -r ../clean.zip clean -x "clean/_tmp/*" && cd ..
   ```
   Then upload `clean.zip` to Google Drive and share it with the team only. `*.zip` is already ignored by git.
6. **Share the raw data** (path B) the same way, privately. It includes employee names.
