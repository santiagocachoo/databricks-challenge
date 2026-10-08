# Team Briefing: Applebee's EDA

Read time: about 7 minutes. **Presentation: tomorrow, Thu Oct 8. Form already submitted.**

## TL;DR

- We have the full dataset: 115 days of receipts from 127 Applebee's restaurants, about 2.1 million receipts and $99M collected.
- It's already loaded and cleaned into a format we can analyze in seconds with Python. Nobody needs to touch the raw 11 GB files.
- Our main finding: void and discount rates are almost identical on every day and at every hour, but they vary up to 7× between stores and employees. **Risk is about who and where, not when.**
- Tomorrow we present a 5-minute EDA, with one presenter. Cleaning is done. We still need the cleaning visuals, about 6 charts, then the deck and script.
- **To get the data on your laptop, follow `README.md` at the repo root, step by step.**

## What the data is

Think of it as every receipt printed at every RMH Applebee's for 115 days (Apr 28 – Aug 20, 2026).

- **One file per day.** Each file holds every receipt ("check") from that day, between 13K and 28K of them.
- **Each receipt has:**
  - store, table, guests, channel (in-store, DoorDash, online...), and open and close time
  - every line rung up (dishes, drinks, and also sauces, sides and kitchen notes)
  - voided items, discounts, tax and payments
- **4 reference files** translate IDs into names: stores, sales channels, the menu, and employees.

A real receipt from the data (lunch for 2):

```
2 FOR 25            $0.00   combo header
  SPIN ART DIP      $4.42
    DON T MAKE FOOD $0.00   modifier
    *WITH* *MEAL*   $0.00   modifier
  HLF BABY B RIB   $14.95
    HNY BBQ 1.0     $0.00   modifier (x2)
    FRIES           $0.00   modifier
  GR CAL CHX SAL   $11.63
PEPSI               $3.99
RFL CHIPS           $0.00   free refill
---------------------------------------
VOIDED: SPIN DIP $12.49 (reason NOT RECVD, manager approved), never charged
Item sales                 $34.99
Discount "2/20 QUAL"      −$10.00
Tax                        +$2.08
Customer owes              $27.07
Card charged $37.07, Gratuity −$10.00   →   37.07 − 10.00 = 27.07 ✓
```

## Words you need to know

- **Check:** one receipt.
- **Item line:** anything punched into the register. **67% of lines are $0**, because most are modifiers (sauces, included sides, "TO GO", "NO PINK") or free things like water.
- **Modifier:** a $0 line attached to a dish that describes it.
- **Void:** an item removed from the order before payment. Void dollars = the value removed.
- **Discount:** money taken off one item or the whole bill (employee meal, manager comp, coupon, complaint). Discount dollars = the total taken off.
- **Comp:** the customer paid $0 for food that was rung up.
- **Walkout:** the customer left without paying. The server zeroes the bill with a WALKOUT discount.
- **Gratuity:** the tip. It's stored as a **negative** number, because the card charge includes the tip and the tip belongs to the server, not the restaurant.

## Why this matters for fraud

Each lever below has an honest use and a theft version.

| Lever | Honest use | Theft version | Size |
|---|---|---|---|
| Voids | Wrong item, customer changed their mind | Customer pays cash, server voids an item afterward and keeps the difference | $726K |
| Discounts and comps | Complaints, employee meals, promos | Free food for friends, or a discount added after a cash payment | $3.0M |
| Walkouts | Real dine-and-dash | Customer paid cash, server calls it a walkout and keeps the money | 2,345 receipts |
| Tips | Normal tipping | "Tip padding": raising a card tip after the customer signs | 11.7K card tips are bigger than the bill |
| Self-approval | — | An employee approving their own void or discount | 5,866 events |

## What we found so far

1. **The data is trustworthy.** Every receipt should satisfy: card charge − tip = item sales − discounts + tax. That holds for **99.996%** of 2.1M receipts. Only 78 don't add up, and those are flagged as anomalies.
2. **Normal business patterns:**
   - Friday and Saturday sell about 65% more than Monday and Tuesday.
   - The dinner peak is 17:00–18:00.
   - In-store is 77% of receipts and delivery apps about 12%.
   - Sales per store per day dropped 18% from May to August, and Mother's Day was the biggest day ($1.45M).
3. **Timing doesn't explain risk.** The void rate stays at about 0.8% of sales on every weekday and at every hour.
4. **People and stores do:**
   - The **top 5% of employees account for 39% of walked-out receipts**, 20% of void dollars and 21% of discount dollars.
   - The median server voids 0.77% of their sales; the top 1% void more than 4.2%.
   - Store void rates range from 0.32% to 2.29%.
5. **Munster (store 80)** has the highest void rate in the chain, about 2.3% against a chain average of 0.83%, and it's high in every month. It also has the most comped receipts. Its missing days in mid-August are shared with 3 nearby Indiana stores, so that part looks like a regional outage, not anything suspicious.

**Rule for the presentation:** the data has no fraud labels, so we say "risk signals" and "anomalies", never "fraud". We never show employee names, only IDs.

## Data problems we found (and what we do about them)

| Problem | Decision |
|---|---|
| Receipt numbers repeat across stores | Identify a receipt by date + store + receipt number |
| 2 empty columns (loyalty ID, service charge) | Drop them |
| 20 store-days missing across 7 stores | Keep the stores and compare per open day |
| 1,800 look-alike groups (3,774 receipts) that look identical from the outside | Checked inside: 3,545 receipts are split bills (kept); 229 are exact copies worth $73 in total (removed) |
| Split bills look like duplicates and give fractional guest counts (0.5, 0.67) | Legitimate; keep them |
| Weird receipts: a $0 receipt with 5,120 lines, receipts open more than 6 hours, real refunds | Flag them; don't delete. In fraud work, outliers are the signal. 42,291 receipts (2%) carry at least one flag. |
| Typos in labels ("SERV ERR" vs "SERVER ERR") | Merge into one label |
| The HR file has names and birth dates, and no explanation of job IDs | Use IDs only; ask the organizers |

## How to open the data yourself

Setup is in `README.md`: clone the repo, create the Python environment, then either unzip `clean.zip` from Santiago (fastest) or rebuild with `python eda_work/scripts/build_all.py`. Check it worked with `python eda_work/scripts/check_setup.py`.

The clean tables are in `eda_work/clean/`. Parquet is like CSV, but compressed and fast: the 11 GB became about 300 MB.

```python
import pandas as pd
checks = pd.read_parquet("eda_work/clean/checks.parquet")      # 2.1M receipts, 53 columns incl. totals and flags
voids  = pd.read_parquet("eda_work/clean/voids.parquet")       # 178K voided items, merged reasons
disc   = pd.read_parquet("eda_work/clean/discounts.parquet")   # item + check discounts in one table
pays   = pd.read_parquet("eda_work/clean/payments.parquet")    # positive tip, tip_pct, method_group
# items has 28.6M rows: load only the columns you need
items = pd.read_parquet("eda_work/clean/items.parquet", columns=["location_id", "item_name", "line_type", "sold_price"])
```

The key to join tables is `dt` + `location_id` + `check_id`.

## The 5-minute story (draft)

1. **Context:** 127 stores, 115 days, 2.1M receipts. Where can money leak at the register?
2. **Understanding:** how a receipt works, and proof that 99.996% balance.
3. **Cleaning:** 11 GB of nested JSON became 7 clean tables; what we fixed and what we flagged.
4. **Baseline:** sales follow the week, but the void rate stays flat.
5. **Levers:** $3M in discounts and $726K in voids, and 5% of employees drive 39% of walked-out receipts.
6. **Stores:** up to a 7× difference; Munster voids nearly 3× the average.
7. **Takeaway:** risk is about who and where, so in Phase 2 we score employees and stores.

## What's left before tomorrow

- [x] Finish the clean tables and settle the possible duplicates (done: `eda_work/clean/`)
- [x] Repo ready for the team: `README.md`, one-command rebuild, setup checker
- [x] Cleaning visuals and all analysis charts: 10 PNGs in `eda_work/charts/` (list and suggested slide for each in `EDA_PLAN.md`, section "Charts")
- [ ] Team picks which charts go in the deck
- [ ] Build the 7-slide deck and write the script (about 650 words)
- [ ] Do 2 timed run-throughs, staying under 4:45

More detail: `EDA_PLAN.md` (tasks, storyboard, status) and `EDA_LEARNINGS.md` (every number and finding).
