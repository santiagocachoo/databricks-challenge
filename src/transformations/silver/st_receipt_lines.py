"""
SILVER - receipt lines: the nested arrays of each raw receipt, flattened into one STREAMING TABLE each.

  silver.st_items      one row per item line (menu items, combo parts, $0 modifiers)
  silver.st_discounts  item-level and receipt-level discounts in one table (level = 'item' | 'check')
  silver.st_payments   one row per payment (tips made positive, refunds and tip-over-bill marked)
  silver.st_voids      one row per voided item
  silver.st_taxes      one row per tax line

Why streaming: these are row-by-row transformations of an append-only source (bronze). Each update
only explodes the receipts that arrived since the last update.

Same rules as Phase 1 (phase1_eda/scripts/convert.py + clean.py), ported to Spark:
  - employee / manager id 0 means "system" -> NULL
  - times arrive as text ("2026-05-04T11:03") -> timestamp
  - spelling variants of void reasons are merged; discount names compared ignoring case, spaces and %
  - nothing is deleted here: exact-copy receipts are removed in silver.mv_checks, and every
    table downstream joins to mv_checks, so their lines drop out there.
"""
from pyspark.sql import functions as F

try:
    from pyspark import pipelines as dp
except ImportError:  # older Databricks runtimes expose the same API as `dlt`
    import dlt as dp

KEY = [F.col("dt"), F.col("LocationId").alias("location_id"), F.col("Id").alias("check_id")]
TIME_FMT = "yyyy-MM-dd HH:mm"


def to_ts(col_name):
    return F.expr(f"try_to_timestamp(replace({col_name}, 'T', ' '), '{TIME_FMT}')")


def no_system(col):
    """POS id 0 = system / nobody -> NULL."""
    return F.when(col != 0, col)


def build_items(raw):
    x = raw.select(*KEY, F.posexplode("ItemsSold").alias("pos", "x"))
    gross, parent = F.col("x.GrossPrice"), F.col("x.ParentSequence")
    return x.select(
        "dt", "location_id", "check_id",
        (F.col("pos") + 1).alias("line_no"),
        F.col("x.Sequence").alias("seq"), parent.alias("parent_seq"), F.col("x.Seat").alias("seat"),
        F.col("x.ItemId").alias("item_id"), F.col("x.ItemName").alias("item_name"), F.col("x.ItemPLU").alias("item_plu"),
        F.col("x.ItemMajorCatName").alias("category"), F.col("x.ItemSubCatName").alias("subcategory"),
        F.when((parent == 0) & (gross != 0), "menu item")
        .when((parent == 0) & (gross == 0), "free line")
        .when((parent > 0) & (gross != 0), "combo part / add-on")
        .otherwise("modifier").alias("line_type"),
        ((parent > 0) & (gross == 0)).alias("is_modifier"),
        F.col("x.Quantity").alias("quantity"), gross.alias("gross_price"), F.col("x.SoldPrice").alias("sold_price"),
        F.round(gross - F.col("x.SoldPrice"), 2).alias("item_discount"),
        no_system(F.col("x.EmployeeId")).alias("employee_id"),
        (F.col("x.EmployeeId") == 0).alias("is_system_line"),
        to_ts("x.OrderTime").alias("order_time"),
        F.col("x.RevenueCenterId").alias("revenue_center_id"), F.col("x.PosSourceId").alias("pos_source_id"),
    )


def _discount_cols(d, level, line_no):
    key = F.upper(F.regexp_replace(F.col(f"{d}.DiscountName"), r"[\s%]", ""))
    emp, mgr = no_system(F.col(f"{d}.EmployeeId")), no_system(F.col(f"{d}.ManagerId"))
    return [
        "dt", "location_id", "check_id", F.lit(level).alias("level"), line_no.alias("line_no"),
        F.col(f"{d}.DiscountId").alias("discount_id"),
        F.col(f"{d}.DiscountName").alias("discount_name"),
        key.alias("discount_key"),
        F.col(f"{d}.Amount").alias("amount"),
        emp.alias("employee_id"), mgr.alias("manager_id"),
        (mgr == emp).alias("is_self_approved"),
        mgr.isNull().alias("no_manager"),
        (key == "WALKOUT").alias("is_walkout"),
        (F.col(f"{d}.Amount") == 0).alias("is_zero_amount"),
    ]


def build_discounts(raw):
    item_level = (
        raw.select(*KEY, F.posexplode("ItemsSold").alias("pos", "x"))
        .select("dt", "location_id", "check_id", (F.col("pos") + 1).alias("line_no"), F.explode("x.Discounts").alias("d"))
        .select(*_discount_cols("d", "item", F.col("line_no")))
    )
    check_level = (
        raw.select(*KEY, F.explode("Discounts").alias("d"))
        .select(*_discount_cols("d", "check", F.lit(None).cast("int")))
    )
    return item_level.unionByName(check_level)


def build_payments(raw):
    p = raw.select(*KEY, F.explode("Payments").alias("p"))
    method = F.upper(F.col("p.PayCatName"))
    group = (
        F.when(method == "CASH", "Cash")
        .when(method.isin("VISA", "MASTERCARD", "DISCOVER", "AMEX"), "Card")
        .when(method.startswith("OLO"), "Online card")
        .when(method == "GIFT CARD", "Gift card")
        .when(method == "GC SOLD", "Gift card sold")
        .when(method == "HOUSE CHG", "House charge")
        .otherwise("Delivery app / partner")
    )
    amount, grat = F.col("p.Amount"), F.col("p.Gratuity")
    before_tip = amount + grat  # raw gratuity is negative: the card charge already includes the tip
    return p.select(
        "dt", "location_id", "check_id",
        F.col("p.PayCatName").alias("method_raw"), method.alias("method"), group.alias("method_group"),
        amount.alias("amount"), grat.alias("gratuity"), (F.lit(0) - grat).alias("tip"),
        F.round(before_tip, 2).alias("amount_before_tip"),
        F.when(before_tip > 0, F.round(-grat / before_tip, 4)).alias("tip_pct"),
        no_system(F.col("p.EmployeeId")).alias("employee_id"),
        F.col("p.IsCreditCard").alias("is_credit_card"), F.col("p.IsGiftCard").alias("is_gift_card"),
        (group == "Gift card sold").alias("is_gift_card_sale"),
        ((amount < 0) & (group != "Gift card sold")).alias("is_refund"),
        ((before_tip > 0) & (-grat > before_tip)).alias("is_tip_over_bill"),
    )


def build_voids(raw):
    v = raw.select(*KEY, F.explode("Voids").alias("v"))
    reason_raw = F.col("v.VoidCategoryName")
    reason = (F.when(reason_raw == "SERVER ERR", "SERV ERR")
              .when(reason_raw == "NOT RECEVD", "NOT RECVD")
              .otherwise(reason_raw))
    return v.select(
        "dt", "location_id", "check_id",
        F.col("v.ItemId").alias("item_id"), F.col("v.ItemName").alias("item_name"),
        F.col("v.Quantity").alias("quantity"), F.col("v.Amount").alias("amount"),
        reason_raw.alias("void_reason_raw"), reason.alias("void_reason"),
        no_system(F.col("v.EmployeeId")).alias("employee_id"), no_system(F.col("v.ManagerId")).alias("manager_id"),
        (F.col("v.ManagerId") == F.col("v.EmployeeId")).alias("is_self_approved"),
        (F.col("v.Amount") == 0).alias("is_zero_amount"),
    )


def build_taxes(raw):
    t = raw.select(*KEY, F.explode("Tax").alias("t"))
    return t.select(
        "dt", "location_id", "check_id",
        F.col("t.TaxCategoryId").alias("tax_cat_id"), F.col("t.TaxCategoryName").alias("tax_cat_name"),
        F.col("t.Amount").alias("amount"),
    )


def bronze_stream():
    return spark.readStream.table("bronze.st_raw_checks")  # noqa: F821 - `spark` is provided by the pipeline runtime


@dp.table(name="silver.st_items", comment="One row per item line. line_type separates menu items, combo parts, free lines and $0 modifiers.",
          cluster_by=["dt", "location_id"], table_properties={"quality": "silver"})
@dp.expect("non_negative_sold_price", "sold_price >= 0")
@dp.expect("priced_line_has_quantity", "NOT (quantity = 0 AND sold_price <> 0)")
@dp.expect("order_time_parsed", "order_time IS NOT NULL")
def st_items():
    return build_items(bronze_stream())


@dp.table(name="silver.st_discounts", comment="Item-level and receipt-level discounts (level column). is_walkout = WALKOUT discount.",
          cluster_by=["dt", "location_id"], table_properties={"quality": "silver"})
@dp.expect("discount_has_name", "discount_name IS NOT NULL")
def st_discounts():
    return build_discounts(bronze_stream())


@dp.table(name="silver.st_payments", comment="One row per payment. tip is positive; is_refund and is_tip_over_bill are risk markers.",
          cluster_by=["dt", "location_id"], table_properties={"quality": "silver"})
@dp.expect("payment_amount_present", "amount IS NOT NULL")
def st_payments():
    return build_payments(bronze_stream())


@dp.table(name="silver.st_voids", comment="One row per voided item, with the merged void reason.",
          cluster_by=["dt", "location_id"], table_properties={"quality": "silver"})
@dp.expect("void_amount_not_negative", "amount >= 0")
def st_voids():
    return build_voids(bronze_stream())


@dp.table(name="silver.st_taxes", comment="One row per tax line.",
          cluster_by=["dt", "location_id"], table_properties={"quality": "silver"})
def st_taxes():
    return build_taxes(bronze_stream())
