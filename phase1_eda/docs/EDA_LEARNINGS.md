# Applebee's Dataset: Everything We've Learned

Phase 1 (EDA) · profiled and cleaned Oct 7, 2026 · presented Oct 8 · all 115 days, every row
Numbers come from queries over the full dataset, not a sample.

**The story in four sentences** (what the presentation argues):

1. **The data is understood and trustworthy:** 2.1M receipts from 127 stores over 115 days, and 99.996% balance to the cent.
2. **It was cleaned without losing evidence:** only 229 exact copies removed; 2% of receipts flagged and kept, because in fraud work outliers are the signal.
3. **Risk is about who and where, not when:** void and discount rates barely move by hour or weekday, but vary about 7× between stores and far more between employees.
4. **The signals stack up on the same people:** 106 employees are top 10% on 3+ of 5 signals, about 5× chance. Phase 2 turns this into a risk score.

---

## 1. The business context

- **Brand:** RMH, an Applebee's franchisee.
- **Period:** Apr 28 – Aug 20, 2026, which is 115 consecutive days with no missing day files.
- **Stores:** 127 active restaurants. The locations file lists 185, but the other 58 are closed and never appear in the sales data.
- **Our track:** AI-Powered Fraud Detection. The question behind the EDA is where money can leak at the register, and whether the data shows it.
- **No labels:** nothing in the data says "this was fraud". Everything we find is a risk signal or anomaly, not proof.

## 2. How the files are organized

```
Applebees Challenge/
├── dimensions/                         reference files that translate IDs into names
│   ├── locations/locations.json        185 stores (Id, Name, OpenDate, ClosedDate, TimeZoneName)
│   ├── revenue_centers/revenueCenters.json   23 sales channels (In-Store, To Go, DoorDash...)
│   ├── items/items.json                16,697 menu items (Id, Name, Plu, SalesCategoryId)
│   └── employees/employees.json        156,975 employee records (NOT in the official guide)
└── facts/checks/brand=rmh/dt=YYYY-MM-DD/checks.json   one file per day, 115 files, 11 GB
```

Each daily file is a single line of text, between 63 and 168 MB. It holds a JSON list of every receipt ("check") from all stores that day, between 13.6K and 27.9K receipts per day.

## 3. What one check (receipt) contains

A real example from the data: check #1408789 at Superstition Springs (store 145), Aug 14, 2026, table 41, 2 guests, In-Store, opened 12:23 and closed 13:25, server 159506.

| Part | Field in the JSON | On this receipt |
|---|---|---|
| Header | Id, LocationId, BusinessDate, TableName, OpenTime, CloseTime, TrafficCount (guests), RevenueCenterId (channel) | Store 145, table 41, 2 guests, In-Store |
| Item lines | `ItemsSold[]`: ItemName, GrossPrice, SoldPrice, Quantity, EmployeeId, Sequence, ParentSequence, category, plus each line's own `Discounts[]` | 11 lines: 4 priced dishes and drinks, 7 lines at $0 |
| Voids | `Voids[]`: ItemName, Amount, VoidCategoryName (reason), EmployeeId, ManagerId | SPIN DIP $12.49 removed, reason NOT RECVD, approved by manager 158099 |
| Check discounts | `Discounts[]`: DiscountName, Amount, EmployeeId, ManagerId | "2/20 QUAL" promo, −$10.00 |
| Tax | `Tax[]`: TaxCategoryName, Amount | $2.08 |
| Payments | `Payments[]`: PayCatName, Amount, Gratuity, IsCreditCard... | MASTERCARD charged $37.07, Gratuity −$10.00 |
| Unused | `LoyaltyId` (always null), `ServiceCharge` (always 0) | — |

The item lines on that receipt:

```
2 FOR 25            $0.00   combo header (the dishes under it carry the price)
  SPIN ART DIP      $4.42   menu item
    DON T MAKE FOOD $0.00   modifier (kitchen instruction)
    *WITH* *MEAL*   $0.00   modifier
  HLF BABY B RIB   $14.95   menu item
    HNY BBQ 1.0     $0.00   modifier (sauce choice)
    HNY BBQ 1.0     $0.00   modifier
    FRIES           $0.00   modifier (included side)
  GR CAL CHX SAL   $11.63   menu item
PEPSI               $3.99   menu item
RFL CHIPS           $0.00   free refill
```

## 4. Key concepts, in plain words

- **Check:** one receipt.
- **Item line:** anything punched into the register, not just food. That includes sauces, sides, kitchen notes ("TO GO", "FIRST OUT", "NO PINK"), combo headers, and free water.
- **Modifier:** a line attached to a dish that changes or describes it. `ParentSequence` points to the dish's `Sequence` (0 means a top-level line). Most modifiers cost $0.
- **GrossPrice vs SoldPrice:** GrossPrice is the menu price. SoldPrice is the price after item-level discounts. Both are unit prices; quantity is almost always 1.
- **Void:** removing an item from the order before payment (wrong item, customer changed their mind). Void dollars = the value of removed items. They are never charged, so they don't enter the receipt's math.
- **Discount:** lowering the price, either of one item (item discount) or of the whole check (check discount). Examples: EMP 50 (employee meal), MANAGER (manager comp), TASTE (complaint), KIDS FREE, MILTARY 10. Discount dollars = the total taken off.
- **Comp / fully comped check:** a receipt where food was rung up but the customer paid $0.
- **Walkout:** a customer left without paying (dine-and-dash). The server zeroes the bill with a discount named WALKOUT.
- **Manager approval:** voids and discounts carry the approving manager's ID. "Self-approved" means the employee approved their own void or discount.
- **Revenue center:** the sales channel, such as In-Store, To Go, Online, DoorDash or Uber Eats.
- **Split check:** a table that pays separately gets several receipts with the same table and times.
- **Business date:** the restaurant's "day" runs past midnight, so a check opened at 00:30 belongs to the previous date.

## 5. How the money flows (validated)

Every check satisfies:

```
Payment Amount + Gratuity  =  sum(SoldPrice) − check discounts + tax
     (card charge)  (tip, negative)   (item sales)
```

On the example: 37.07 + (−10.00) = 27.07 = 34.99 − 10.00 + 2.08.

This holds for **2,142,768 of 2,142,846 checks (99.996%)**. That proves we read every column correctly, and that the data is trustworthy. The 78 checks that break it:

- 16 have items but no payment (−$575 in total)
- 29 were underpaid (−$273)
- 33 were overpaid (+$125)

**Why the tip is negative:** the payment `Amount` is the full card charge, meaning bill plus tip. The tip belongs to the server, not the restaurant, so the register records it as negative to take it back out. (This is our interpretation; the organizers confirmed it is negative but didn't say why.)

**Chain totals (115 days):**

| Measure | Amount |
|---|---|
| Menu prices (sum of GrossPrice per line; the waterfall's first bar) | $87.32M |
| Item discounts | $1.07M |
| Item sales (SoldPrice) | $86.25M |
| Check discounts | $1.95M |
| Tax | $6.16M |
| Tips | $8.83M |
| Total collected (payments) | $99.29M |
| Voided (removed, never charged) | $0.73M |

Menu prices − item discounts = item sales exactly ($87.32M − $1.07M = $86.25M), because the receipt math works on line prices. Multiplying GrossPrice by quantity gives a slightly lower $87.07M, since some lines have quantity 0 but still carry a price (see `flag_zero_qty_priced`). Net sales (item sales − check discounts) are $84.29M.

## 6. The flattened tables (what we built)

| Table | One row is | Rows |
|---|---|---|
| checks | one receipt | 2,142,846 |
| items | one item line | 28,558,925 |
| item_discounts | a discount on one item line | 275,991 |
| check_discounts | a discount on a whole receipt | 240,699 |
| payments | one payment | 2,232,092 |
| taxes | one tax line | 2,569,636 |
| voids | one voided item | 178,303 |
| check_summary | one receipt with its totals (sold, gross, discounts, tax, payment, tip, voids) | 2,142,846 |

- **Unique key for a receipt:** date + location_id + check_id. check_id alone repeats across stores, since 42K check numbers are shared between stores on the same day.
- **Join between items and item_discounts:** date + location_id + check_id + line_no.
- **Employees:** employees always ring sales at their own store (0 cross-store cases).

## 7. Business baseline (what "normal" looks like)

- **Trend:** per store per day, sales fell 18%, from $6,574 (week of May 4) to $5,404 (week of Aug 10). Chain totals: $5.97M a week (140.2K checks) → $4.83M (119.6K checks). Store gaps are too small to explain it.
- **Holidays:** Mother's Day (Sun May 10) is the biggest day at $1.45M, and Father's Day (Sun Jun 21) is second at $1.12M. July 4 fell on a Saturday but sold only $0.69M, low for a Saturday.
- **Weekday:** Fri ($961K a day) and Sat ($944K) are 65% above Mon ($578K) and Tue ($575K).
- **Hour:** check openings peak at 17:00–18:00 (about 258K each). Lunch peaks at 12:00. The busiest single slot is Friday 18:00, with about 3,000 checks opened chain-wide on an average Friday. Sunday lunch is the biggest lunch.
- **Channels (share of checks):**

  | Channel | Checks | Share |
  |---|---|---|
  | In-Store | 1,649,922 | 77% |
  | DoorDash | 197,995 | 9.2% |
  | Online | 138,305 | 6.5% |
  | To Go | 95,357 | 4.5% |
  | Uber Eats | 47,914 | 2.2% |
  | Grubhub | 7,020 | <1% |

  The other 11 channels are each under 0.2%.

- **Payments:**

  | Method | Amount |
  |---|---|
  | Visa | $45.5M |
  | Mastercard | $21.4M |
  | Cash | $14.5M (487K payments) |
  | DoorDash | $8.0M |
  | Gift card | $2.8M |
  | Discover | $2.3M |
  | Uber Eats | $2.1M |
  | Amex | $2.0M |

- **Typical check:** median $35.68, 99th percentile $132, maximum $1,982. A median of 12 item lines.
- **Typical duration:** median 46 minutes, 95th percentile 131 minutes.
- **Menu mix (item sales):**

  | Category | Item sales |
  |---|---|
  | Food | $71.4M |
  | Liquor | $5.6M |
  | Non-alcoholic beverages | $4.7M |
  | Draft beer | $3.1M |
  | Bottled beer | $0.9M |
  | Wine | $0.3M |

## 8. Item lines: why 67% are $0

| Line type | Lines | Example |
|---|---|---|
| Top-level, priced | 7.75M | PEPSI, a burger |
| Child, priced | 1.74M | Dishes inside a combo, paid add-ons |
| Top-level, $0 | 4.13M | ONLINE ORDR (1.21M), WATER W/LEMON (639K), 2 FOR 25 (372K), RAILS delivery info lines |
| Child, $0 (modifiers) | 14.94M | TO GO (2.50M), FIRST OUT (967K), FRIES (904K), WITH MEAL (483K), NO PINK (346K) |

Rule for a modifier: a child line (`parent_seq > 0`) with a $0 price. Don't use `parent_seq > 0` alone, because combo dishes are priced children. Counting "items per check" without removing $0 lines overcounts by about 3×.

## 9. Fraud levers (where money can leak)

| Lever | Volume | Dollars | How it can hide theft |
|---|---|---|---|
| Check discounts | 240,699 lines | $1.95M | Free food for friends, or a discount added after a cash payment |
| Fully comped checks | 58,082 checks | $1.11M gross | Same, at 100% |
| Item discounts | 275,991 lines | $1.07M | Same, smaller and harder to notice |
| Voids | 178,303 lines on 55,120 checks | $726K | Customer pays cash, server voids an item afterward and keeps the difference |
| Walkouts | 2,345 receipts (27,306 discount lines: every item on the receipt gets its own WALKOUT line) | $93K | Customer paid cash, server records a walkout and keeps the cash |
| Self-approved voids and discounts | 5,866 events | $32.9K | Skips the manager check |
| Refunds | 15 payments | $151 | Fake refunds. 3 card refunds ($79.50) were posted as standalone receipts numbered −1, with no items and no original sale: 1 at Topeka, 2 at Warsaw by the same employee. The other 12 are small cash corrections (mostly under $10). The other 3,764 negative payments are gift-card sales ("GC Sold"), which the register books as negative. |
| Unbalanced checks | 78 checks | about $1K net | Errors or manipulation |
| Card tips above 100% of the bill | 11,744 payments | not yet measured | Tip padding: server raises the tip after the customer signs |

**Biggest discounts by dollars:**

- Check level: MANAGER $367K, EMP 50 $252K, KIDS FREE $177K, MILTARY 10 $117K, FREEAPP $110K, TRAINER $106K.
- Item level: TASTE $247K, GST CORECT $181K, SERVERERR $134K, KITCHNERR $133K, WALKOUT $93K.
- There are 73 check-discount names and 33 item-discount names.

**Void reasons:**

| Reason | Voids | Dollars | Self-approved |
|---|---|---|---|
| CUST CHANG | 50,192 | $207K | 3% |
| WRONG ITEM | 30,911 | $131K | 4% |
| NOT RECVD | 29,214 | $116K | 0% |
| TOO MANY | 18,348 | $65K | 1% |
| OTHER | 14,557 | $57K | 6% |
| 86'D ITEM | 11,673 | $57K | 1% |
| SERV ERR | 11,338 | $44K | 0% |
| SERVER ERR | 7,921 | $32K | 11% |
| WRONG CHK | 3,795 | $15K | 2% |
| NOT RECEVD | 351 | $1K | 100% |
| VOIDED | 3 | $3 | 100% |

98,071 of the 178,303 void lines are $0, meaning voided modifiers.

**System discounts:** the loyalty discounts PUNCHHOLO (92%) and GC BONUS (100%) have no manager. They are applied automatically, which is normal.

**Tips (card payments only):**

- Median tip is 15.7% of the bill.
- 371K card payments have no tip.
- 40,670 have a tip above 50% of the bill, and 11,744 above 100%. The largest tip is $570.
- None of the 486,509 cash payments has a tip recorded, so cash tips are invisible.

## 10. The main insight: risk is about who and where, not when

**When (flat):** the void rate stays between 0.78% and 0.88% of gross sales on every weekday. The discount rate only moves between 3.2% (Sat) and 3.8% (Mon). By hour, discounts sit between 3% and 4.6%; 23:00 has the highest rate.

**Who (concentrated), among 3,183 employees who rang sales (2,522 with $5K+):**

| Employee metric | Median | 90th percentile | 99th percentile | Max |
|---|---|---|---|---|
| Void rate | 0.77% | 1.83% | 4.18% | 8% |
| Discount rate | 3.1% | 5.5% | 9.3% | 19% |

The top 5% of employees account for 39% of walked-out receipts, 20% of void dollars and 21% of discount dollars. The top 1% account for 13.5%, 6% and 6%. 1,095 of the 3,183 employees have at least one walked-out receipt, and the most any single employee has is 22.

**Where (big spread between stores):**

| Store metric | Min | Median | Max |
|---|---|---|---|
| Void rate | 0.32% | 0.80% | 2.29% |
| Discount rate | 1.56% | 3.42% | 7.2% |
| Cash share | 7.4% | 14.6% | 22.0% |
| Fully comped checks | — | 2.66% | 6.11% |
| Walked-out receipts | — | 16 | 114 (Morse Road, 174) |

- Next most walked-out receipts: Brice Road (155) with 76 and Cabela Drive (65) with 64.
- Highest void rates: Munster (80) 2.29%, Grand Island (19) 1.73%, Clinton (69) 1.69%, Columbus (24) 1.65%, Corpus Christi (39) 1.59%, Nicholasville (108) 1.55%.

**Munster (store 80):**

- It has the highest void rate in the chain: 2.28% before August, against 0.83% for the rest of the chain.
- That rate is consistent every month: Apr 2.0%, May 2.53%, Jun 1.68%, Jul 2.61%, Aug 2.39%.
- It also has a high share of fully comped checks (4.96%, 4th of 127 stores after Ireland Road 6.11%, Crestwood 5.95% and Morse Road 5.36%), 37 walked-out receipts, and 3 of the 8 highest-void employees with $10K+ in sales (161078, 161205, 159512).
- Its data gap (no receipts Aug 12–17) is NOT suspicious. Merrillville (77), Portage (82) and Valparaiso (86), all Northwest Indiana, have gaps in the same week (Aug 11–17), which points to a regional outage or weather.

**Relationships: the risk signals stack up on the same employees** (2,516 employees with $5K+ sales and 50+ card payments; every signal is a rate):

- **Top-10% overlap:** of the top 10% voiders, the share also in the top 10% for walkout rate is 27%, for discount rate 26%, for cash share 19%, for comp rate 13%, and for card tips over the bill 10%. If the signals were unrelated, each would be 10%.
- **Stacking:** 106 employees are in the top 10% on 3 or more of 5 signals (void, discount, walkout, comp, tips over the bill). Unrelated signals would give about 22, so this is 5× chance.
- **Where they work:** those employees cluster in Ireland Road (84) and Munster (80) with 8 each, Morse Road (174) with 7, Brice Road (155) with 6, and store 167 and Corpus Christi (39) with 4 each.
- **Rank correlations (Spearman):**

  | Pair | Correlation |
  |---|---|
  | Void rate – cash share | 0.32 |
  | Discount rate – walkout rate | 0.30 |
  | Void rate – discount rate | 0.25 |
  | Discount rate – comp rate | 0.68 (expected: a comp is a 100% discount) |

- **Tips:** card tips over the bill are unrelated to the other signals, so most are probably generous customers, not tip padding.
- **Caveat:** job roles are unknown (no lookup for job IDs), so some overlap, like cash and voids, may come from role (bartenders) rather than behavior.

**How the employees were compared** (the method behind charts 06, 08 and 11):

| Chart | Employees | Rule |
|---|---|---|
| 08 concentration curve | 3,183 | Everyone who rang a sale (employee_id 0 = system, excluded). It shows shares of totals, so small sellers can't distort it. |
| 06 who/where, not when | 2,522 | $5,000+ in sales over the 115 days. Below that, rates are noise (one $30 void on $300 of sales = a 10% void rate). The median employee sold $20.7K, so the cutoff mainly drops trainees, short stints and managers who rarely ring. |
| 11 signals stack up | 2,516 | $5,000+ in sales and 50+ card payments, so the tip signal means something |

- **Every signal is a rate:** void $ ÷ gross sales, discount $ ÷ gross sales, walked-out receipts per receipt, fully comped receipts per receipt, cash share of payments, card tips over the bill per card payment. Busy employees don't look worse just for being busy.
- **Attribution:** voids and discounts count against the employee who entered them, not the approving manager (a separate field, which is how self-approvals were found).
- **Top 10%:** rank all 2,516 on each rate separately and take the highest 252.
- **Expected by chance:** if the 5 signals (void, discount, walkout, comp, tips over the bill) were unrelated, the chance of being top 10% on 3 or more is 10·0.1³·0.9² + 5·0.1⁴·0.9 + 0.1⁵ ≈ 0.86%, and 0.86% × 2,516 ≈ 22. Observed: 106.

**HR flag:** 1,020 employees marked `Deleted` in the HR file still rang 14.6% of sales during the period. Most likely they left after August, which is worth comparing against their risk metrics.

## 11. Data quality issues and decisions

| Issue | Evidence | Decision |
|---|---|---|
| Nested single-line JSON | 63–168 MB per day | Flattened into Parquet (done) |
| Schema drift | Voids Quantity is decimal on 05-08, 05-23, 07-15, 08-05 and 08-12. ItemsSold Quantity is integer on 05-25 and 06-29. Check Id is 128-bit on 05-19, 07-03 and 07-20. | Fixed types on conversion (done) |
| check_id not unique | 2,100,502 distinct (date, check_id) pairs vs 2,142,846 rows | Composite key (done) |
| Odd receipt numbers | Normal numbers run 1 to ~2.4M. 9 fall outside, all at Topeka and Warsaw: 3 numbered −1 (card refunds with no items, see Refunds) and 6 above 1 billion (normal meals, likely a backup register) | Keep and flag (`flag_odd_check_id`) |
| Text timestamps | Minute precision, no seconds | Parse to datetime |
| Negative tip | Gratuity totals −$8.83M | Flip the sign into `tip` |
| Empty columns | Receipts: loyalty_id 100% empty, service_charge always $0. Employees: IsEmancipated 100% empty | Dropped all 3 (done) |
| Missing store-days | 20 store-days over 7 stores: Munster (80) Aug 12–17, Portage (82) Aug 11–15, Crestview Hills (113) Jul 2–4, Kearney (23) Apr 28–29, Valparaiso (86) Aug 11–12, Merrillville (77) Aug 11, Dayton (157) Aug 19 | Keep, normalize per open day |
| Time zone field | 108 Central, 18 Phoenix, 1 Eastern, even though Ohio stores should be Eastern | Ignore it; times are local |
| HR gaps | 9,184 missing birth dates, 5,351 missing hire dates, 3,134 with no job IDs, 37 job IDs with no names. employee_id 0 on 3,283 item lines. | Treat 0 as system; ask the organizers |
| HR file is historical | 148,650 of 156,975 records are `Deleted`; 9,126 are "Borrowed" | Use only the 3,194 IDs that appear in sales |
| Duplicate names | 24,558 names repeat (rehires and transfers) | Never join on name |
| Possible duplicates | 1,800 look-alike groups (not receipts) holding 3,774 receipts, identical on store, table, open/close minute, total, tax, payment | Resolved: 3,545 are split bills (food or payments differ). 229 are exact copies of another receipt, worth $73 in total, and were removed. |
| Split checks | 9,108 groups: same table and times, different amounts | Legitimate |
| Giant $0 checks | Store 42 (Ada): 5,120 lines on Aug 13, 1,424 lines on Jul 31 | Flag |
| Durations | 52,503 zero-minute (to-go and delivery), 10,387 over 6 h (open tabs), 18,253 opened after midnight | Keep, flag |
| Quantities and prices | 166,881 zero-quantity lines (59,004 priced), 766 negative SoldPrice, 116 SoldPrice > GrossPrice | Flag |
| Payments | 3,779 negative: 3,764 are gift-card sales, 15 are real refunds. 75,579 zero, max $2,500. | Flag refunds; label gift-card sales |
| Guest counts | 867,407 fractional (split checks share guests), 190,375 zero (delivery and to-go), max 284 | Use for dine-in only |
| Empty checks | 11,508 with no items, 3,856 with no payment | Flag |
| Duplicate labels | SERV ERR/SERVER ERR, NOT RECVD/NOT RECEVD, Postmates/POSTMATES, Pride/PRIDE, 1.5 OZ RANCH/1.5OZ RANCH | Normalize |
| Item names | 66 item names differ between items.json and the sales files; 5,329 of 16,697 menu items are used | Use the names from the sales files |
| Generic tax names | "Tax Category 1/2" | Leave as is |
| Privacy | Full names, birth dates and payroll IDs in employees.json | Dropped from `clean/employees.parquet`; show IDs only (done) |

## 12. Cleaning results (step 1, done Oct 7)

`phase1_eda/scripts/clean.py` builds the clean layer in about 20 seconds. Nothing weird is deleted; only exact copies are removed.

| Step | Receipts |
|---|---|
| Raw receipts | 2,142,846 |
| Exact copies removed | 229 ($73 of sales) |
| Clean receipts | 2,142,617 |
| … with at least one data-quality flag (kept) | 42,291 (2.0%) |
| … clean and unflagged | 2,100,326 (98.0%) |

**Data-quality flags** (`flag_*` columns on `clean/checks.parquet`):

| Flag | Receipts |
|---|---|
| no_items | 11,301 |
| long_open (over 6 h) | 10,387 |
| zero_qty_priced (a line with quantity 0 and a price) | 17,981 |
| no_payment | 3,643 |
| negative_price | 647 |
| giant (over 200 lines) | 142 |
| unbalanced | 78 |
| odd_check_id | 9 |

**Behavior flags** (risk levers, not errors):

| Flag | Receipts |
|---|---|
| has_discount | 268,579 |
| is_fully_comped | 58,081 |
| has_void | 55,114 |
| has_tip_over_bill | 12,886 |
| has_gift_card_sale | 2,494 |
| has_walkout | 2,345 |
| has_self_approved_discount | 367 |
| has_refund | 15 |

**Context flags** (normal behavior):

| Flag | Receipts |
|---|---|
| is_split_guests | 867,406 |
| is_zero_guests | 190,151 |
| is_instant | 52,494 |
| is_after_midnight | 18,253 |
| is_lookalike_split | 3,545 |

**What changed in the clean tables:**

- **Tip:** `tip` is a positive number. The original `gratuity` is kept next to it, and `tip_pct` = tip ÷ (amount − tip). The median card tip is 15.7%.
- **Line types:** every item line has a `line_type`: modifier 14.94M, menu item 7.75M, free line 4.13M, combo part / add-on 1.74M.
- **Merged labels**, listed in `reports/label_merges.csv`:
  - void reasons SERVER ERR → SERV ERR and NOT RECEVD → NOT RECVD
  - 9 discount spellings (EMP 50% → EMP 50, Free APP / Free App → FREEAPP, Birthday → BIRTHDAY, Pride → PRIDE…)
  - payment names in upper case
- **Void reasons** get a readable description, e.g. CUST CHANG → "Customer changed order".
- **Discounts:** item-level and check-level discounts are in one table, with `level`, `is_walkout`, `is_self_approved` and `no_manager`.
- **Payments:**
  - `method_group`: Card $71.2M, Cash $14.5M, Delivery app / partner $10.7M, Gift card $2.8M, Online card $0.2M, House charge, Gift card sold.
  - `is_refund` and `is_tip_over_bill` flags.
- **Channels:** `channel_group` is one of Dine-in 1.65M, Delivery app 254K, Online order 142K, To go 95K, Catering 644, Other 317.
- **Columns:** the checks table now has 53 columns. Times are parsed, and it includes open hour, weekday, duration, store name, channel, money totals and all the flags.
- **Employees:** `clean/employees.parquet` has no names, birth dates, payroll IDs or `IsEmancipated`.
- **Dropped columns** (also listed in `reports/cleaning_summary.json`): receipts' `loyalty_id` and `service_charge`, employees' `IsEmancipated` (all always empty), plus employee names, birth dates and payroll IDs (privacy).
- **Reports:** `reports/missing_values.csv` (null and zero % for every column), `reports/cleaning_summary.json` (the funnel and flag counts) and `reports/label_merges.csv`.
- **Check:** the balance check still holds on the clean data: 2,142,539 of 2,142,617 receipts, with the same 78 exceptions.

## 13. Charts and the presentation (done Oct 7–8)

12 charts in `phase1_eda/charts/` (2400 × 1350 px), in the order they appear in the 11-slide deck. The full storyboard, appendix and cut order are in `EDA_PLAN.md`, and the slide-by-slide deck plan is in `docs/DECK_GUIDE.md` (it embeds the charts).

| Slide | Chart (`phase1_eda/charts/`) | What it shows |
|---|---|---|
| 1 | — (KPI strip) | 127 stores · 115 days · 2.1M receipts · $99.3M collected; where can money leak at the register? |
| 2 | `00_data_model.png` | Every detail table links to one receipt (date + store + receipt #); 4 lookup tables turn IDs into names |
| 3 | `03_check_waterfall.png` | $87.32M menu prices → $99.29M collected; 99.996% of receipts balance |
| 4 | `02_cleaning_funnel.png` | 229 receipts removed, 2% flagged and kept, and why |
| 5 | `01_missing_values.png` | Only 3 fields were always empty (loyalty_id, service_charge, IsEmancipated) and were dropped; ClosedDate is empty only for open stores |
| 6 | `04_daily_trend.png` | Weekly rhythm, Mother's/Father's Day peaks, −18% per store-day by August |
| 7 | `06_who_where_not_when.png` | Void/discount rates flat by hour and weekday, wide by store and employee (the core insight) |
| 8 | `08_concentration_curve.png` | 5% of employees → 39% of walked-out receipts, 20% of void $, 21% of discount $ |
| 9 | `11_signals_stack_up.png` | Top-10% voiders are 2.7× as likely to be top-10% for walkouts, 2.6× for discounts; 106 employees are top 10% on 3+ of 5 signals (~22 by chance) |
| 10 | `09_store_scatter.png` | Munster voids 2.9× the chain median |
| 11 | — (takeaway) | Risk is about who and where, not when → Phase 2 risk score |
| A1 | `05_weekday_hour_heatmap.png` | Friday 6 PM is the busiest hour; dinner peaks every day |
| A2 | `07_discounts_and_voids.png` | Manager comps top discounts ($3.02M); order changes top voids ($0.73M) |
| A3 | `10_munster_by_month.png` | Munster is high every month, about 2.8× the other stores |

Rebuild all charts with `python phase1_eda/scripts/charts.py` (about 5 seconds), or one chart with e.g. `python phase1_eda/scripts/charts.py 06`.

The charts use one style: gray data, one blue accent on what the title is about, green and red only for money added or taken off, and the finding in the title. In the clean data there are 84 discount names with amounts above $0.

## 14. Technical reference

- **Location:** `phase1_eda/` in the repo (`databricks-challenge`). Use `clean/` for analysis; `parquet/` is the raw flattened copy. Data folders are gitignored; see `README.md` to get them.
  - `parquet/<table>/<date>.parquet`: the 7 tables, plus `parquet/check_summary/check_summary.parquet`.
  - `scripts/build_all.py`: rebuilds everything in one command (convert → check summary → clean), about 4–6 minutes from scratch. Tested: a rebuild reproduces identical rows and reports.
  - `scripts/check_setup.py`: checks Python, libraries, raw data and built tables, and says what to fix.
  - `scripts/convert.py`: JSON → Parquet for all days (about 1–3 s per day).
  - `scripts/build_check_summary.py`: one row per receipt with its totals.
  - `scripts/clean.py`: builds `clean/` and `reports/`.
  - `scripts/charts.py`: builds the 12 PNGs in `charts/`.
  - `scripts/dup_check.py`: the duplicate analysis.
  - `scripts/q.py`: registers the raw tables for DuckDB SQL (used by `p1`–`p12`, `e1`–`e3`).
  - Setup for teammates: `README.md` at the repo root.
  - `scripts/p1.py`…`p12.py`: the profiling queries behind every number here.
- **Open in pandas:** `pd.read_parquet("phase1_eda/clean/checks.parquet")`. For `items` (28.6M rows), load only the columns you need, or use DuckDB.
- **DuckDB:** an SQL engine that runs inside Python and queries Parquet files directly without loading them into memory: `duckdb.sql("SELECT ... FROM 'phase1_eda/clean/items.parquet'")`.
- **Column names in Parquet:** snake_case, e.g. `check_id`, `location_id`, `sold_price`, `gratuity`, `void_cat_name`, `discount_name`, `pay_cat_name`. Every table has `dt` (business date).

## 15. Open questions for the organizers

- What do the job IDs in employees.json mean (which ID is server, manager, cook)?
- What does `Deleted` mean, and when was the HR file extracted?
- What do the tax categories mean?
- What happened in Northwest Indiana on Aug 11–17?
- Why do some lines have quantity 0 but a price?
