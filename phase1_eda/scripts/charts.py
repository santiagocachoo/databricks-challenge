"""
Step 3 + 4: build every chart for the EDA presentation from the clean tables.
Run:     python phase1_eda/scripts/charts.py            (all charts, ~30 s)
         python phase1_eda/scripts/charts.py 06 09      (only charts whose file name starts with 06 or 09)
Output:  phase1_eda/charts/NN_name.png   (16:9, 2400 x 1350 px, ready for slides)
Style:   gray for data, ONE blue accent on what the title is about, green/red only for money in/out.
"""
import sys
from pathlib import Path
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
C = (REPO / "phase1_eda" / "clean").as_posix()
OUT = REPO / "phase1_eda" / "charts"
OUT.mkdir(exist_ok=True)
SRC = "Source: RMH Applebee's POS data, 127 stores, Apr 28 – Aug 20, 2026 (115 days) · clean layer"

# ---- palette (validated reference palette; light surface) ----
BG, INK, INK2, MUTED = "#ffffff", "#0b0b0b", "#52514e", "#8a8984"
GRID, AXIS = "#ebeae6", "#c9c8c2"
GRAY, GRAY_D = "#bdbbb3", "#888780"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
GOOD, BAD = "#0ca30c", "#d03b3b"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False, "savefig.facecolor": BG,
    "text.parse_math": False,  # so "$" prints as a dollar sign
})
con = duckdb.connect()
q = lambda s: con.execute(s).fetchall()
CK = f"read_parquet('{C}/checks.parquet')"

def fig(title, subtitle, figsize=(12, 6.75), **kw):
    f = plt.figure(figsize=figsize)
    f.text(0.045, 0.94, title, fontsize=19, fontweight="bold", color=INK, va="top", gid="fit")
    f.text(0.045, 0.875, subtitle, fontsize=12.5, color=INK2, va="top", gid="fit")
    f.text(0.045, 0.025, SRC, fontsize=9.5, color=MUTED, va="bottom")
    return f

def grid_y(ax):
    ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True)

def grid_x(ax):
    ax.xaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True)

def save(f, name):
    # shrink any title/subtitle that would run past the right edge (safe to edit titles)
    f.canvas.draw(); r = f.canvas.get_renderer(); W = f.get_figwidth() * f.dpi
    for tx in [t for t in f.texts if t.get_gid() == "fit"]:
        while tx.get_window_extent(r).x1 > 0.975 * W and tx.get_fontsize() > 9:
            tx.set_fontsize(tx.get_fontsize() - 0.5)
    f.savefig(OUT / name, dpi=200); plt.close(f); print("wrote", name)

money = lambda v: f"${v/1e6:,.2f}M"

# ================================================================= 00 data model (slide 2)
def c00():
    from matplotlib.patches import FancyBboxPatch
    n = lambda t: q(f"SELECT count(*) FROM read_parquet('{C}/{t}.parquet')")[0][0]
    rec, lines, disc, voids, pays, taxes = n("checks"), n("items"), n("discounts"), n("voids"), n("payments"), n("taxes")
    stores, active = q(f"SELECT count(*), count(*) FILTER (WHERE active_in_data) FROM read_parquet('{C}/stores.parquet')")[0]
    chans = n("channels"); used_ch = q(f"SELECT count(DISTINCT revenue_center_id) FROM {CK}")[0][0]
    emps, ring = q(f"SELECT count(*), count(*) FILTER (WHERE rings_sales) FROM read_parquet('{C}/employees.parquet')")[0]
    n_flags = len([r for r in q(f"DESCRIBE SELECT * FROM {CK}") if r[0].startswith(("flag_", "has_", "is_"))])
    sold = q(f"SELECT count(DISTINCT item_id) FROM read_parquet('{C}/items.parquet')")[0][0]
    try:
        menu = q(f"SELECT count(*) FROM read_json('{(REPO / 'Applebees Challenge' / 'dimensions' / 'items' / 'items.json').as_posix()}')")[0][0]
        menu_line = f"{menu:,} items · {sold:,} sold"
    except Exception:
        menu_line = f"{sold:,} items sold"
    short = lambda v: f"{v/1e6:.1f}M" if v >= 1e6 else (f"{v/1e3:.0f}K" if v >= 1e4 else f"{v:,}")
    f = fig("Every detail links back to one receipt; 4 lookup tables turn IDs into names",
            "The cleaned data model. Detail tables join to receipts on date + store + receipt number. Row counts after cleaning.")
    ax = f.add_axes([0.03, 0.10, 0.94, 0.74]); ax.set_xlim(0, 100); ax.set_ylim(0, 50); ax.axis("off")
    def box(x, y, w, h, title, sub, fields, kind):
        fc, ec, lw = {"hub": (BLUE, BLUE, 0), "fact": ("#f3f2ee", AXIS, 1), "dim": (BG, GRAY_D, 1.2)}[kind]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.0", fc=fc, ec=ec, lw=lw, ls="-" if kind != "dim" else (0, (4, 2))))
        tc, sc = ("white", "white") if kind == "hub" else (INK, INK2)
        cx = x + w / 2
        ax.text(cx, y + h - 2.0, title, ha="center", va="center", fontsize=13.5 if kind == "hub" else 12, fontweight="bold", color=tc)
        ax.text(cx, y + h - 4.1, sub, ha="center", va="center", fontsize=11 if kind == "hub" else 10.5, color=sc)
        ax.text(cx, y + 1.9, fields, ha="center", va="center", fontsize=10 if kind == "hub" else 9.5, color=sc, linespacing=1.3)
    def link(x1, y1, x2, y2, dashed=False):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-", color=GRAY_D, lw=1.2, ls=(0, (3, 2)) if dashed else "-"))
    # lookups on top
    box(20, 40, 24, 9, "Stores", f"{stores} stores · {active} with sales", "name · opened · closed", "dim")
    box(56, 40, 24, 9, "Sales channels", f"{chans} channels · {used_ch} used", "In-Store · To Go · DoorDash…", "dim")
    # hub
    box(31, 22, 38, 12, "Receipts (checks)", f"{rec:,} receipts · key: date + store + receipt #",
        f"table · open/close time · guests · channel\ntotals · tip · {n_flags} yes/no flags", "hub")
    # lookups on the sides
    box(1, 23, 24, 10, "Menu items", menu_line, "name · category", "dim")
    box(75, 23, 24, 10, "Employees", f"{emps:,} records · {ring:,} ring sales", "home store · job ID · no names\non lines, discounts, voids, payments", "dim")
    # details at the bottom
    kids = [("Item lines", lines, "item · price · line type\nemployee"), ("Discounts", disc, "name · amount · level\nemployee · manager"),
            ("Voids", voids, "reason · amount\nemployee · manager"), ("Taxes", taxes, "category · amount"),
            ("Payments", pays, "method · amount · tip\nemployee")]
    w, gap = 17.6, 2.5
    for i, (t, cnt, fl) in enumerate(kids):
        x = 1 + i * (w + gap)
        box(x, 1, w, 10, t, f"{short(cnt)} rows", fl, "fact")
        cx = x + w / 2
        link(cx, 11, min(max(cx, 33), 67), 22)
    link(32, 40, 39, 34, dashed=True); link(68, 40, 61, 34, dashed=True)
    link(13, 23, 10, 11, dashed=True)
    link(87, 23, 89.2, 11, dashed=True)
    ax.text(34.5, 37.2, "location_id", fontsize=9.5, color=MUTED, ha="right", va="center"); ax.text(65.5, 37.2, "revenue_center_id", fontsize=9.5, color=MUTED, ha="left", va="center")
    ax.text(10.5, 17, "item_id", fontsize=9.5, color=MUTED, ha="right", va="center")
    ax.text(89.6, 17, "employee_id", fontsize=9.5, color=MUTED, ha="left", va="center")
    ax.text(50, 18.0, "date + store + receipt #", fontsize=10, color=INK2, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", fc=BG, ec="none"))
    f.text(0.045, 0.062, "Solid lines = detail tables (many rows per receipt). Dashed = lookup tables. The employee file was not in the official guide.",
           fontsize=10, color=INK2)
    save(f, "00_data_model.png")

# ================================================================= 01 missing values (step 3)
def c01():
    n_chk = q(f"SELECT count(*) FROM {CK}")[0][0] + 229          # raw receipts (before removing exact copies)
    n_emp = q(f"SELECT count(*) FROM read_parquet('{C}/employees.parquet')")[0][0]
    n_sto = q(f"SELECT count(*) FROM read_parquet('{C}/stores.parquet')")[0][0]
    n_open = q(f"SELECT count(*) FROM read_parquet('{C}/stores.parquet') WHERE closed_date IS NULL")[0][0]
    mv = REPO / "phase1_eda" / "reports" / "missing_values.csv"
    hire = q(f"SELECT n_null FROM read_csv('{mv.as_posix()}') WHERE column_name='HireDate'")[0][0]
    groups = [
        ("Always empty: dropped", BLUE, [
            ("Receipts · loyalty_id", n_chk, n_chk, "receipts", "no loyalty number ever recorded"),
            ("Receipts · service_charge", n_chk, n_chk, "receipts", "always $0"),
            ("Employees · IsEmancipated", n_emp, n_emp, "employees", "never filled"),
        ]),
        ("Partly empty: kept, the gap has a reason", GRAY_D, [
            ("Stores · ClosedDate", n_open, n_sto, "stores", "empty = the store is still open"),
        ]),
    ]
    f = fig("Only 3 fields were always empty, and we dropped them",
            "Every field in every table was checked. Fields not shown are 100% filled, except the two in the note below.")
    ax = f.add_axes([0.25, 0.20, 0.40, 0.57])
    y, ticks, labels = 0, [], []
    for gname, col, rows in groups:
        ax.text(-0.51, y + 0.15, gname, fontsize=12.5, color=col, fontweight="bold", ha="left", va="bottom",
                transform=ax.get_yaxis_transform())
        y -= 0.75
        for lab, n_empty, n_all, unit, why in rows:
            pct = n_empty / n_all * 100
            ax.barh(y, pct, height=0.55, color=col if col == BLUE else GRAY)
            ax.text(pct + 1.5, y, f"{pct:.1f}%" if pct < 10 else f"{pct:.0f}%", va="center", fontsize=12.5, color=INK, fontweight="bold")
            ax.text(115, y + 0.13, f"{n_empty:,} of {n_all:,} {unit}", va="center", fontsize=11, color=INK, clip_on=False)
            ax.text(115, y - 0.2, why, va="center", fontsize=10.5, color=INK2, clip_on=False)
            ticks.append(y); labels.append(lab); y -= 0.9
        y -= 0.35
    ax.set_yticks(ticks, labels, fontsize=12, color=INK)
    ax.set_ylim(y + 0.4, 0.8); ax.set_xlim(0, 112)
    ax.xaxis.set_major_formatter(mt.PercentFormatter()); ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("% of rows where the field is empty", fontsize=11.5)
    grid_x(ax); ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    f.text(0.045, 0.068, f"Not shown: employee birth dates (5.9% empty; removed for privacy, with names and payroll IDs) and hire dates ({hire/n_emp:.1%} empty; not used).",
           fontsize=11, color=INK2)
    save(f, "01_missing_values.png")

# ================================================================= 02 cleaning funnel (step 3)
def c02():
    import json
    s = json.loads((REPO / "phase1_eda" / "reports" / "cleaning_summary.json").read_text())
    f = fig(f"Only {s['exact_copies_removed']} receipts removed; {s['receipts_with_any_data_quality_flag']/s['clean_receipts']:.0%} flagged and kept, not deleted",
            "Left: receipts at each cleaning step. Right: why the flagged receipts were flagged (a receipt can have several flags)")
    steps = [("Raw receipts", s["raw_receipts"], GRAY_D), ("Exact copies removed", s["exact_copies_removed"], BAD),
             ("Clean receipts", s["clean_receipts"], GRAY_D), ("Flagged, kept for review", s["receipts_with_any_data_quality_flag"], BLUE),
             ("Clean and unflagged", s["receipts_clean_and_unflagged"], GRAY)]
    ax = f.add_axes([0.20, 0.14, 0.30, 0.66])
    y = np.arange(len(steps))[::-1]
    for yi, (lab, v, col) in zip(y, steps):
        ax.barh(yi, v, height=0.56, color=col)
        ax.text(v + 30000, yi, f"{v:,}", va="center", fontsize=12, color=INK, fontweight="bold" if col in (BAD, BLUE) else "normal")
    ax.set_yticks(y, [x[0] for x in steps], fontsize=12, color=INK)
    ax.set_xlim(0, 2.9e6); ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v/1e6:.0f}M" if v else "0"))
    ax.set_xticks([0, 1e6, 2e6]); grid_x(ax); ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    names = {"flag_zero_qty_priced": "Line with qty 0 but a price", "flag_no_items": "No items on the receipt",
             "flag_long_open": "Open more than 6 hours", "flag_no_payment": "No payment recorded",
             "flag_negative_price": "Negative price on a line", "flag_giant": "Over 200 lines (not a real meal)",
             "flag_unbalanced": "Money doesn't add up", "flag_odd_check_id": "Odd receipt number"}
    fl = sorted(s["data_quality_flags"].items(), key=lambda kv: kv[1])
    ax3 = f.add_axes([0.72, 0.14, 0.20, 0.66])
    yy = np.arange(len(fl))
    ax3.barh(yy, [v for _, v in fl], height=0.56, color=BLUE, alpha=0.55)
    for yi, (k, v) in zip(yy, fl):
        ax3.text(v + 300, yi, f"{v:,}", va="center", fontsize=11.5, color=INK)
    ax3.set_yticks(yy, [names[k] for k, _ in fl], fontsize=11.5, color=INK)
    ax3.set_xlim(0, max(v for _, v in fl) * 1.35); ax3.set_xticks([]); ax3.spines["bottom"].set_visible(False)
    ax3.spines["left"].set_visible(False); ax3.tick_params(axis="y", length=0)
    save(f, "02_cleaning_funnel.png")

# ================================================================= 03 money waterfall
def c03():
    menu, sold = q(f"SELECT sum(gross_price), sum(sold_price) FROM read_parquet('{C}/items.parquet')")[0]
    cd, tax, tips, paid, voids, n_ok, n = q(f"""SELECT sum(check_discounts), sum(tax), sum(tips), sum(amount_paid), sum(void_amount),
        count(*) FILTER (WHERE NOT flag_unbalanced), count(*) FROM {CK}""")[0]
    idisc = menu - sold; net = sold - cd
    steps = [("Menu price", menu, "total"), ("Item\ndiscounts", -idisc, "step"), ("Item sales", sold, "total"),
             ("Check\ndiscounts", -cd, "step"), ("Net sales", net, "total"), ("Tax", tax, "step"), ("Tips", tips, "step"),
             ("Collected", paid, "total")]
    f = fig(f"Every receipt balances: {money(menu)} in menu prices becomes {money(paid)} collected",
            f"Chain totals for 115 days. The equation holds to the cent on {n_ok:,} of {n:,} receipts ({n_ok/n:.3%}).")
    ax = f.add_axes([0.07, 0.21, 0.88, 0.59]); grid_y(ax)
    run = 0
    for i, (lab, v, kind) in enumerate(steps):
        if kind == "total":
            ax.bar(i, v, width=0.62, color=GRAY_D if lab in ("Menu price", "Collected") else GRAY); run = v
            ax.text(i, v + 1.2e6, money(v), ha="center", fontsize=12, color=INK, fontweight="bold")
        else:
            lo, hi = (run + v, run) if v < 0 else (run, run + v)
            ax.bar(i, hi - lo, bottom=lo, width=0.62, color=BAD if v < 0 else GOOD, alpha=0.75); run += v
            ax.text(i, hi + 1.2e6, ("−" if v < 0 else "+") + money(abs(v)), ha="center", fontsize=12, color=INK)
        if i < len(steps) - 1:
            ax.plot([i + 0.31, i + 0.69], [run, run], color=AXIS, lw=1, ls=":")
    ax.set_xticks(range(len(steps)), [s[0] for s in steps], fontsize=12, color=INK)
    ax.set_ylim(0, 112e6); ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"${v/1e6:.0f}M"))
    ax.tick_params(axis="x", length=0)
    f.text(0.07, 0.075, "Red = taken off the bill · green = added on top.  Voided items "
           f"({money(voids)}) were removed before the bill and never charged.", fontsize=11, color=INK2)
    save(f, "03_check_waterfall.png")

# ================================================================= 04 daily trend
def c04():
    d = q(f"SELECT dt, sum(net_sales) FROM {CK} GROUP BY 1 ORDER BY 1")
    dates = np.array([r[0] for r in d], dtype="datetime64[D]"); v = np.array([r[1] for r in d]) / 1e3
    roll = np.convolve(v, np.ones(7) / 7, mode="valid"); rd = dates[6:]
    wk = q(f"""SELECT date_trunc('week', dt) w, sum(net_sales)/count(DISTINCT (dt, location_id)) FROM {CK}
              WHERE dt BETWEEN '2026-05-04' AND '2026-08-16' GROUP BY 1 ORDER BY 1""")
    a, b = wk[0][1], wk[-1][1]
    f = fig(f"Sales peak on weekends and holidays, and drift down {1 - b/a:.0%} by August",
            f"Net sales per day (gray) and 7-day average (blue). Per store per day: ${a:,.0f} (week of May 4) → ${b:,.0f} (week of Aug 10).")
    ax = f.add_axes([0.07, 0.14, 0.89, 0.66]); grid_y(ax)
    ax.plot(dates, v, color=GRAY, lw=1.4, label="Daily net sales")
    ax.plot(rd, roll, color=BLUE, lw=2.6, label="7-day average")
    for day, lab, off in [("2026-05-10", "Mother's Day", (8, 0)), ("2026-06-21", "Father's Day", (8, 0)), ("2026-07-04", "July 4 (a Saturday)", (-10, -62))]:
        i = int(np.where(dates == np.datetime64(day))[0][0])
        ax.scatter(dates[i], v[i], s=40, color=INK, zorder=5)
        ax.annotate(f"{lab}\n${v[i]/1e3:.2f}M", (dates[i], v[i]), xytext=off, textcoords="offset points",
                    fontsize=11, color=INK, va="center", ha="left" if off[0] > 0 else "right",
                    arrowprops=None if off[0] > 0 else dict(arrowstyle="-", color=INK2, lw=0.8))
    ax.axvspan(np.datetime64("2026-08-11"), np.datetime64("2026-08-17"), color=GRID, alpha=0.8, lw=0)
    ax.text(np.datetime64("2026-08-14"), 1380, "4 NW Indiana\nstores offline", ha="center", fontsize=10, color=INK2, va="top")
    ax.set_ylim(400, 1550); ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: f"${x/1e3:.1f}M" if x >= 1000 else f"${x:.0f}K"))
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b 1"))
    ax.legend(loc="upper right", frameon=False, fontsize=11)
    save(f, "04_daily_trend.png")

# ================================================================= 05 weekday x hour heatmap
def c05():
    hours = list(range(10, 24)) + [0, 1]
    nd = dict(q(f"SELECT weekday_num, count(DISTINCT dt) FROM {CK} GROUP BY 1"))
    cnt = {(w, h): n for w, h, n in q(f"SELECT weekday_num, open_hour, count(*) FROM {CK} GROUP BY 1, 2")}
    order = [1, 2, 3, 4, 5, 6, 0]  # DuckDB weekday(): 0 = Sunday
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    M = np.array([[cnt.get((w, h), 0) / nd[w] for h in hours] for w in order])
    peak = np.unravel_index(M.argmax(), M.shape)
    f = fig(f"{names[peak[0]]}day {hours[peak[1]] % 12 or 12} PM is the busiest hour; dinner peaks every day",
            "Average checks opened per day, by weekday and hour, all 127 stores (hours after midnight belong to the previous business day)")
    ax = f.add_axes([0.07, 0.14, 0.80, 0.64])
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("b", ["#f4f8fd"] + BLUES)
    im = ax.imshow(M, cmap=cmap, aspect="auto")
    ax.set_yticks(range(7), names, fontsize=12, color=INK)
    ax.set_xticks(range(len(hours)), [f"{h % 12 or 12}{'a' if h < 12 else 'p'}" for h in hours], fontsize=11)
    for i in range(7):
        for j in range(len(hours)):
            val = M[i, j]
            if val >= 1000:
                ax.text(j, i, f"{val/1000:.1f}k", ha="center", va="center", fontsize=9.5, color="white" if val > M.max() * 0.55 else INK)
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)
    cax = f.add_axes([0.89, 0.14, 0.015, 0.64]); cb = f.colorbar(im, cax=cax); cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=10, length=0); cb.set_label("checks per day", color=INK2, fontsize=11)
    save(f, "05_weekday_hour_heatmap.png")

# ================================================================= 06 who/where, not when
def c06():
    def rates(sql):
        return np.array([r[0] * 100 for r in q(sql) if r[0] is not None])
    hour_v = rates(f"""SELECT sum(void_amount)/sum(gross_sales) FROM {CK} GROUP BY open_hour HAVING count(*) >= 5000""")
    hour_d = rates(f"""SELECT sum(item_discounts+check_discounts)/sum(gross_sales) FROM {CK} GROUP BY open_hour HAVING count(*) >= 5000""")
    wd_v = rates(f"SELECT sum(void_amount)/sum(gross_sales) FROM {CK} GROUP BY weekday_num")
    wd_d = rates(f"SELECT sum(item_discounts+check_discounts)/sum(gross_sales) FROM {CK} GROUP BY weekday_num")
    st = q(f"SELECT location_id, sum(void_amount)/sum(gross_sales), sum(item_discounts+check_discounts)/sum(gross_sales) FROM {CK} GROUP BY 1")
    st_v = np.array([r[1] * 100 for r in st]); st_d = np.array([r[2] * 100 for r in st]); st_ids = np.array([r[0] for r in st])
    mun = [r for r in st if r[0] == 80][0]
    em = q(f"""WITH g AS (SELECT employee_id, sum(gross_price*quantity) gross FROM read_parquet('{C}/items.parquet') WHERE employee_id IS NOT NULL GROUP BY 1),
        v AS (SELECT employee_id, sum(amount) va FROM read_parquet('{C}/voids.parquet') GROUP BY 1),
        d AS (SELECT employee_id, sum(amount) da FROM read_parquet('{C}/discounts.parquet') GROUP BY 1)
        SELECT coalesce(va,0)/gross, coalesce(da,0)/gross FROM g LEFT JOIN v USING (employee_id) LEFT JOIN d USING (employee_id) WHERE gross >= 5000""")
    em_v = np.array([r[0] * 100 for r in em]); em_d = np.array([r[1] * 100 for r in em])
    f = fig("Voids and discounts depend on where and who, not on when",
            f"Each dot is one hour of the day, one weekday, one store ({len(st_v)}) or one employee ({len(em_v):,} with $5K+ in sales). Share of gross sales.")
    groups = [("Hour of day", hour_v, hour_d), ("Weekday", wd_v, wd_d), ("Store", st_v, st_d), ("Employee", em_v, em_d)]
    rng = np.random.default_rng(7)
    for k, (title, xmax) in enumerate([("Voids, % of gross sales", 8.5), ("Discounts, % of gross sales", 20)]):
        ax = f.add_axes([0.13 + k * 0.45, 0.14, 0.38, 0.64]); grid_x(ax)
        for i, (lab, vv, dd) in enumerate(groups):
            x = vv if k == 0 else dd; yy = 3 - i + rng.uniform(-0.22, 0.22, len(x))
            keep = st_ids != 80 if lab == "Store" else np.ones(len(x), bool)   # Munster is drawn once, in blue
            ax.scatter(x[keep], yy[keep], s=10 if lab == "Employee" else 26, color=GRAY_D, alpha=0.35 if lab == "Employee" else 0.8, lw=0)
            ax.text(xmax * 0.995, 3 - i + 0.33, f"range {x.min():.1f}–{x.max():.1f}%", ha="right", fontsize=10.5, color=INK2)
        mx = mun[1] * 100 if k == 0 else mun[2] * 100
        ax.scatter([mx], [1], s=70, color=BLUE, zorder=5, edgecolor="white", lw=1.5)
        ax.annotate("Munster", (mx, 1), xytext=(6, -14), textcoords="offset points", fontsize=11, color=BLUE, fontweight="bold")
        ax.set_xlim(0, xmax); ax.set_ylim(-0.6, 3.6); ax.xaxis.set_major_locator(mt.MultipleLocator(1 if k == 0 else 5))
        ax.xaxis.set_major_formatter(mt.PercentFormatter(decimals=0))
        ax.set_yticks([3, 2, 1, 0], [g[0] for g in groups] if k == 0 else [""] * 4, fontsize=12.5, color=INK)
        ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
        ax.set_title(title, loc="left", fontsize=12.5, color=INK, pad=10)
    save(f, "06_who_where_not_when.png")

# ================================================================= 07 discounts and voids by reason
def c07():
    d = q(f"""SELECT discount_name, sum(amount) a, count(DISTINCT (dt,location_id,check_id)) n FROM read_parquet('{C}/discounts.parquet')
             GROUP BY 1 ORDER BY a DESC LIMIT 10""")
    dtot = q(f"SELECT sum(amount) FROM read_parquet('{C}/discounts.parquet')")[0][0]
    v = q(f"""SELECT void_reason_desc, sum(amount) a FROM read_parquet('{C}/voids.parquet') GROUP BY 1 ORDER BY a DESC""")
    vtot = sum(r[1] for r in v); v = [r for r in v if r[1] >= 1000]
    n_names = q(f"SELECT count(DISTINCT discount_name) FROM read_parquet('{C}/discounts.parquet') WHERE amount > 0")[0][0]
    f = fig("Manager comps top the discounts; order changes top the voids",
            f"Dollars taken off the bill (discounts, top 10 of {n_names} names) and removed before billing (voids, every reason over $1K).")
    ax = f.add_axes([0.16, 0.13, 0.30, 0.66]); ax2 = f.add_axes([0.66, 0.13, 0.28, 0.66])
    for a, rows, tit, tot in [(ax, d, "Discounts", dtot), (ax2, v, "Voids", vtot)]:
        y = np.arange(len(rows))[::-1]
        for yi, r in zip(y, rows):
            col = BLUE if r is rows[0] else GRAY_D
            a.barh(yi, r[1], height=0.6, color=col)
            a.text(r[1] + tot * 0.006, yi, f"${r[1]/1e3:,.0f}K", va="center", fontsize=11, color=INK)
        a.set_yticks(y, [r[0] for r in rows], fontsize=11.5, color=INK)
        a.set_xlim(0, max(r[1] for r in rows) * 1.25); a.set_xticks([]); a.spines["bottom"].set_visible(False)
        a.spines["left"].set_visible(False); a.tick_params(axis="y", length=0)
        a.set_title(f"{tit}: {money(tot)}", loc="left", fontsize=13, color=INK, pad=10, fontweight="bold")
    save(f, "07_discounts_and_voids.png")

# ================================================================= 08 concentration curve
def c08():
    base = f"(SELECT DISTINCT employee_id FROM read_parquet('{C}/items.parquet') WHERE employee_id IS NOT NULL)"
    series = {
        "Walked-out receipts": f"""SELECT coalesce(n,0) FROM {base} e LEFT JOIN (SELECT employee_id, count(DISTINCT (dt,location_id,check_id)) n
                FROM read_parquet('{C}/discounts.parquet') WHERE is_walkout AND amount>0 GROUP BY 1) w USING (employee_id)""",
        "Void dollars": f"""SELECT coalesce(a,0) FROM {base} e LEFT JOIN (SELECT employee_id, sum(amount) a FROM read_parquet('{C}/voids.parquet') GROUP BY 1) v USING (employee_id)""",
        "Discount dollars": f"""SELECT coalesce(a,0) FROM {base} e LEFT JOIN (SELECT employee_id, sum(amount) a FROM read_parquet('{C}/discounts.parquet') GROUP BY 1) d USING (employee_id)""",
    }
    cols = {"Walked-out receipts": BLUE, "Void dollars": ORANGE, "Discount dollars": AQUA}
    curves = {}
    for k, sql in series.items():
        x = np.sort(np.array([r[0] for r in q(sql)], dtype=float))[::-1]
        curves[k] = (np.arange(1, len(x) + 1) / len(x) * 100, np.cumsum(x) / x.sum() * 100)
    at5 = {k: np.interp(5, *curves[k]) for k in curves}
    n = len(curves["Void dollars"][0])
    f = fig(f"5% of employees account for {at5['Walked-out receipts']:.0f}% of walked-out receipts",
            f"Employees sorted from highest to lowest ({n:,} who rang sales). Dashed line = perfectly even spread.")
    ax = f.add_axes([0.08, 0.14, 0.62, 0.66]); grid_y(ax)
    ax.plot([0, 100], [0, 100], color=AXIS, lw=1.2, ls="--")
    for k, (x, y) in curves.items():
        ax.plot(x, y, color=cols[k], lw=2.6 if k == "Walked-out receipts" else 2, label=k)
    ax.axvline(5, color=INK2, lw=1, ls=":")
    for k, v in at5.items():
        ax.scatter([5], [v], s=36, color=cols[k], zorder=5, edgecolor="white", lw=1.2)
    ax.set_xlim(0, 60); ax.set_ylim(0, 102)
    ax.xaxis.set_major_formatter(mt.PercentFormatter(decimals=0)); ax.yaxis.set_major_formatter(mt.PercentFormatter(decimals=0))
    ax.set_xlabel("Share of employees (highest first)", fontsize=12); ax.set_ylabel("Cumulative share of the total", fontsize=12)
    tx = f.add_axes([0.74, 0.14, 0.23, 0.66]); tx.axis("off")
    tx.text(0, 0.95, "The top 5% of employees hold:", fontsize=12.5, color=INK, fontweight="bold", va="top")
    for i, (k, v) in enumerate(at5.items()):
        tx.text(0, 0.80 - i * 0.17, f"{v:.0f}%", fontsize=26, color=cols[k], fontweight="bold", va="top")
        tx.text(0.36, 0.775 - i * 0.17, f"of {k.lower()}", fontsize=12, color=INK2, va="top")
    tx.text(0, 0.22, "If spread evenly, 5% of employees\nwould hold 5% of each.", fontsize=11, color=INK2, va="top")
    save(f, "08_concentration_curve.png")

# ================================================================= 09 store scatter
def c09():
    st = q(f"""SELECT location_id, store_name, sum(item_discounts+check_discounts)/sum(gross_sales)*100, sum(void_amount)/sum(gross_sales)*100, sum(net_sales)
              FROM {CK} GROUP BY 1, 2""")
    xs = np.array([r[2] for r in st]); ys = np.array([r[3] for r in st]); sz = np.array([r[4] for r in st])
    mv, md = np.median(ys), np.median(xs); mun = [r for r in st if r[0] == 80][0]
    f = fig(f"Munster voids {mun[3]/mv:.1f}× the chain median; most stores sit near {mv:.1f}%",
            f"Each dot is one of {len(st)} stores, sized by net sales. Dotted lines = chain medians (voids {mv:.2f}%, discounts {md:.2f}% of gross sales).")
    ax = f.add_axes([0.08, 0.14, 0.86, 0.66]); grid_y(ax); grid_x(ax)
    s = 20 + (sz - sz.min()) / (sz.max() - sz.min()) * 220
    isM = np.array([r[0] == 80 for r in st])
    ax.scatter(xs[~isM], ys[~isM], s=s[~isM], color=GRAY_D, alpha=0.55, edgecolor="white", lw=0.8)
    ax.scatter(xs[isM], ys[isM], s=s[isM] + 60, color=BLUE, edgecolor="white", lw=1.5, zorder=5)
    ax.annotate(f"Munster  {mun[3]:.2f}% voids", (mun[2], mun[3]), xytext=(10, 4), textcoords="offset points", fontsize=12, color=BLUE, fontweight="bold")
    for r in sorted(st, key=lambda r: -r[3])[1:4]:
        ax.annotate(r[1], (r[2], r[3]), xytext=(8, -3), textcoords="offset points", fontsize=10.5, color=INK2)
    ax.axhline(mv, color=INK2, lw=1, ls=":"); ax.axvline(md, color=INK2, lw=1, ls=":")
    ax.set_xlabel("Discounts, % of gross sales", fontsize=12); ax.set_ylabel("Voids, % of gross sales", fontsize=12)
    ax.xaxis.set_major_formatter(mt.PercentFormatter(decimals=0)); ax.yaxis.set_major_formatter(mt.PercentFormatter(decimals=1))
    ax.set_xlim(0, max(xs) * 1.08); ax.set_ylim(0, max(ys) * 1.15)
    save(f, "09_store_scatter.png")

# ================================================================= 10 Munster by month
def c10():
    rows = q(f"""SELECT month(dt) m, location_id = 80 AS mun, sum(void_amount)/sum(gross_sales)*100 FROM {CK} GROUP BY 1, 2 ORDER BY 1""")
    months = sorted({r[0] for r in rows}); lab = {4: "Apr*", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug*"}
    m_v = [next(r[2] for r in rows if r[0] == m and r[1]) for m in months]
    c_v = [next(r[2] for r in rows if r[0] == m and not r[1]) for m in months]
    ratio = np.mean(np.array(m_v) / np.array(c_v))
    f = fig(f"Munster's void rate is high every month, about {ratio:.1f}× the other stores",
            "Voids as % of gross sales, by month. *April has 3 days and August 20 (Munster had no data Aug 12–17, like 3 nearby stores).")
    ax = f.add_axes([0.08, 0.14, 0.86, 0.66]); grid_y(ax)
    x = np.arange(len(months)); w = 0.36
    ax.bar(x - w / 2, c_v, width=w, color=GRAY, label="Other 126 stores")
    ax.bar(x + w / 2, m_v, width=w, color=BLUE, label="Munster")
    for xi, a, b in zip(x, c_v, m_v):
        ax.text(xi - w / 2, a + 0.05, f"{a:.2f}%", ha="center", fontsize=11, color=INK2)
        ax.text(xi + w / 2, b + 0.05, f"{b:.2f}%", ha="center", fontsize=11.5, color=BLUE, fontweight="bold")
    ax.set_xticks(x, [lab[m] for m in months], fontsize=12, color=INK); ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, max(m_v) * 1.2); ax.yaxis.set_major_formatter(mt.PercentFormatter(decimals=1))
    ax.legend(loc="upper left", frameon=False, fontsize=11.5)
    save(f, "10_munster_by_month.png")

# ================================================================= 11 risk signals stack up (relationships)
def c11():
    con.execute(f"""CREATE OR REPLACE TEMP TABLE emp_rates AS
    WITH s AS (SELECT employee_id, any_value(location_id) store, sum(gross_price*quantity) gross, count(DISTINCT (dt,location_id,check_id)) n_rec
               FROM read_parquet('{C}/items.parquet') WHERE employee_id IS NOT NULL GROUP BY 1),
    v AS (SELECT employee_id, sum(amount) void_amt FROM read_parquet('{C}/voids.parquet') GROUP BY 1),
    d AS (SELECT employee_id, sum(amount) disc_amt, count(DISTINCT (dt,location_id,check_id)) FILTER (WHERE is_walkout AND amount>0) n_walk
          FROM read_parquet('{C}/discounts.parquet') GROUP BY 1),
    p AS (SELECT employee_id, sum(amount) FILTER (WHERE method_group='Cash') cash, sum(amount) FILTER (WHERE amount>0) paid,
                 count(*) FILTER (WHERE method_group='Card') n_card, count(*) FILTER (WHERE is_tip_over_bill AND method_group='Card') n_tipover
          FROM read_parquet('{C}/payments.parquet') GROUP BY 1),
    k AS (SELECT i.employee_id, count(*) n_comp FROM (SELECT DISTINCT dt,location_id,check_id,employee_id FROM read_parquet('{C}/items.parquet') WHERE employee_id IS NOT NULL) i
          JOIN (SELECT dt,location_id,check_id FROM {CK} WHERE is_fully_comped) c USING (dt,location_id,check_id) GROUP BY 1)
    SELECT s.employee_id, s.store, coalesce(void_amt,0)/gross AS void_rate, coalesce(disc_amt,0)/gross AS disc_rate,
           coalesce(n_walk,0)*1.0/n_rec AS walk_rate, coalesce(n_comp,0)*1.0/n_rec AS comp_rate,
           coalesce(cash,0)/nullif(paid,0) AS cash_share, coalesce(n_tipover,0)*1.0/nullif(n_card,0) AS tipover_rate
    FROM s LEFT JOIN v USING (employee_id) LEFT JOIN d USING (employee_id) LEFT JOIN p USING (employee_id) LEFT JOIN k USING (employee_id)
    WHERE gross >= 5000 AND n_card >= 50""")
    con.execute("""CREATE OR REPLACE TEMP TABLE emp_top AS SELECT *,
        ntile(10) OVER (ORDER BY void_rate DESC)=1 tv, ntile(10) OVER (ORDER BY disc_rate DESC)=1 td, ntile(10) OVER (ORDER BY walk_rate DESC)=1 tw,
        ntile(10) OVER (ORDER BY comp_rate DESC)=1 tc, ntile(10) OVER (ORDER BY cash_share DESC)=1 tcash, ntile(10) OVER (ORDER BY tipover_rate DESC)=1 tt
        FROM emp_rates""")
    n = q("SELECT count(*) FROM emp_top")[0][0]
    over = [(lab, q(f"SELECT avg({col}::INT) FILTER (WHERE tv) * 100 FROM emp_top")[0][0]) for lab, col in
            [("Walkout rate", "tw"), ("Discount rate", "td"), ("Cash share", "tcash"), ("Comp rate", "tc"), ("Card tips over the bill", "tt")]]
    k3 = q("SELECT count(*) FILTER (WHERE tv::INT + td::INT + tw::INT + tc::INT + tt::INT >= 3) FROM emp_top")[0][0]
    p = 0.1; exp3 = n * sum(__import__("math").comb(5, k) * p**k * (1-p)**(5-k) for k in (3, 4, 5))
    f = fig("Risk signals stack up on the same employees",
            f"{n:,} employees with $5K+ in sales and 50+ card payments. Every signal is a rate, so busy employees are not favored.")
    ax = f.add_axes([0.22, 0.19, 0.36, 0.56]); grid_x(ax)
    y = np.arange(len(over))[::-1]
    for yi, (lab, v) in zip(y, over):
        col = BLUE if v >= 15 else GRAY
        ax.barh(yi, v, height=0.56, color=col)
        ax.text(v + 0.8, yi, f"{v:.0f}%", va="center", fontsize=12.5, color=INK, fontweight="bold" if col == BLUE else "normal")
    ax.axvline(10, color=INK2, lw=1.2, ls="--")
    ax.set_ylim(-0.6, len(over) - 0.1)
    ax.text(10.6, len(over) - 0.45, "10% if unrelated", fontsize=10.5, color=INK2, va="center")
    ax.set_yticks(y, [o[0] for o in over], fontsize=12, color=INK); ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 34); ax.xaxis.set_major_formatter(mt.PercentFormatter(decimals=0))
    ax.set_title("Of the top 10% voiders, share who are also\nin the top 10% for…", loc="left", fontsize=12.5, color=INK, pad=10)
    ax2 = f.add_axes([0.68, 0.19, 0.27, 0.56]); grid_y(ax2)
    ax2.bar([0], [exp3], width=0.55, color=GRAY); ax2.bar([1], [k3], width=0.55, color=BLUE)
    ax2.text(0, exp3 + 3, f"~{exp3:.0f}", ha="center", fontsize=13, color=INK2)
    ax2.text(1, k3 + 3, f"{k3}", ha="center", fontsize=15, color=BLUE, fontweight="bold")
    ax2.set_xticks([0, 1], ["Expected\nby chance", "Actual"], fontsize=12, color=INK); ax2.tick_params(axis="x", length=0)
    ax2.set_ylim(0, k3 * 1.25); ax2.set_ylabel("Employees", fontsize=11.5)
    ax2.set_title(f"Top 10% on 3+ of 5 signals at once:\n{k3/exp3:.0f}× more employees than chance", loc="left", fontsize=12.5, color=INK, pad=10)
    f.text(0.045, 0.058, "Signals: void rate, discount rate, walkouts per receipt, comp rate, card tips over the bill.\n"
           "Job roles are unknown, so some overlap (e.g. cash and voids) may come from the role, not the behavior.", fontsize=10, color=INK2, linespacing=1.4)
    save(f, "11_signals_stack_up.png")

ALL = {"00": c00, "01": c01, "02": c02, "03": c03, "04": c04, "05": c05, "06": c06, "07": c07, "08": c08, "09": c09, "10": c10, "11": c11}
for k in (sys.argv[1:] or ALL):
    ALL[k]()
