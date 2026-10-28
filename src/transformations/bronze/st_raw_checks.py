"""
BRONZE - st_raw_checks: every POS receipt exactly as it arrived, one row per receipt.

Source : /Volumes/<catalog>/bronze/landing/checks/checks_YYYY-MM-DD.json.gz
         (one file per business day; each file is a JSON array of receipts with nested
          item lines, discounts, payments, taxes and voids)
How    : Auto Loader (cloudFiles) as a STREAMING TABLE. Each pipeline update reads only the
         day files that landed since the last update (Auto Loader keeps a checkpoint), so
         adding a new day costs one day of compute, not 115.
Adds   : dt (business day, from the file name), source_file, ingested_at, content_hash
         (fingerprint of the whole receipt except its number, used by silver to find exact copies).
Schema : declared explicitly (schema-on-read contract). Anything that does not fit the
         contract is kept in _rescued_data instead of being lost or breaking the load.
Quality: the three expectation levels, on purpose:
           FAIL  dt cannot be read from the file name   -> the feed contract is broken, stop
           DROP  receipt without Id or LocationId        -> unusable, cannot be identified
           WARN  business date differs from file date, or data had to be rescued -> keep, count
"""
from pyspark.sql import functions as F

try:
    from pyspark import pipelines as dp
except ImportError:  # older Databricks runtimes expose the same API as `dlt`
    import dlt as dp

# Field order matters: content_hash is computed over these fields (everything except Id).
CHECK_FIELDS = [
    "LocationId BIGINT",
    "BusinessDate STRING",
    "TableName STRING",
    "OpenTime STRING",
    "CloseTime STRING",
    "TrafficCount DOUBLE",
    "ServiceCharge DOUBLE",
    "LoyaltyId STRING",
    "RevenueCenterId BIGINT",
    "Tax ARRAY<STRUCT<TaxCategoryId: BIGINT, Amount: DOUBLE, TaxCategoryName: STRING>>",
    "Discounts ARRAY<STRUCT<DiscountId: BIGINT, Amount: DOUBLE, EmployeeId: BIGINT, ManagerId: BIGINT, DiscountName: STRING>>",
    "Payments ARRAY<STRUCT<PaymentCategoryId: BIGINT, Amount: DOUBLE, Gratuity: DOUBLE, EmployeeId: BIGINT, "
    "PosSourceId: BIGINT, PayCatNo: BIGINT, PayCatName: STRING, IsCreditCard: BOOLEAN, IsGiftCard: BOOLEAN, "
    "IsGiftCert: BOOLEAN, IsPettyCash: BOOLEAN, IsNonPOS: BOOLEAN, IsCashDebit: BOOLEAN>>",
    "ItemsSold ARRAY<STRUCT<ItemId: BIGINT, Quantity: DOUBLE, GrossPrice: DOUBLE, SoldPrice: DOUBLE, EmployeeId: BIGINT, "
    "RevenueCenterId: BIGINT, OrderTime: STRING, Seat: BIGINT, `Sequence`: BIGINT, ParentSequence: BIGINT, "
    "PosSourceId: BIGINT, ItemName: STRING, ItemPLU: BIGINT, ItemMajorCatId: BIGINT, ItemMajorCatName: STRING, "
    "ItemSubCatId: BIGINT, ItemSubCatName: STRING, "
    "Discounts: ARRAY<STRUCT<DiscountId: BIGINT, Amount: DOUBLE, EmployeeId: BIGINT, ManagerId: BIGINT, DiscountName: STRING>>>>",
    "Voids ARRAY<STRUCT<ItemId: BIGINT, Quantity: DOUBLE, Amount: DOUBLE, EmployeeId: BIGINT, ManagerId: BIGINT, "
    "VoidCategoryId: BIGINT, VoidCategoryName: STRING, ItemName: STRING, ItemPLU: BIGINT>>",
]
CHECK_SCHEMA = ", ".join(["Id BIGINT"] + CHECK_FIELDS)
PAYLOAD_COLUMNS = [f.split(" ", 1)[0] for f in CHECK_FIELDS]


def build_raw_checks(raw):
    """Add ingestion metadata and the content fingerprint. `raw` = receipts read with CHECK_SCHEMA."""
    if "_rescued_data" not in raw.columns:  # Auto Loader adds it; plain readers (local tests) do not
        raw = raw.withColumn("_rescued_data", F.lit(None).cast("string"))
    file_day = F.regexp_extract(F.col("_metadata.file_path"), r"checks_(\d{4}-\d{2}-\d{2})", 1)
    return raw.select(
        F.when(file_day != "", F.to_date(file_day)).alias("dt"),
        "Id",
        *PAYLOAD_COLUMNS,
        "_rescued_data",
        F.sha2(F.to_json(F.struct(*PAYLOAD_COLUMNS)), 256).alias("content_hash"),
        F.col("_metadata.file_path").alias("source_file"),
        F.current_timestamp().alias("ingested_at"),
    )


@dp.table(
    name="bronze.st_raw_checks",
    comment="Raw POS receipts as received, one row per receipt (nested lines kept). Incremental load with Auto Loader.",
    cluster_by=["dt", "LocationId"],
    table_properties={"quality": "bronze"},
)
@dp.expect_or_fail("day_readable_from_file_name", "dt IS NOT NULL")
@dp.expect_or_drop("receipt_key_present", "Id IS NOT NULL AND LocationId IS NOT NULL")
@dp.expect("business_date_matches_file_day", "BusinessDate = CAST(dt AS STRING)")
@dp.expect("fits_schema_contract", "_rescued_data IS NULL")
def st_raw_checks():
    landing = spark.conf.get("landing_path")  # noqa: F821 - `spark` is provided by the pipeline runtime
    raw = (
        spark.readStream.format("cloudFiles")  # noqa: F821
        .option("cloudFiles.format", "json")
        .option("multiLine", "true")  # each file is one JSON array, not JSON lines
        .option("rescuedDataColumn", "_rescued_data")
        .option("pathGlobFilter", "checks_*.json*")
        .schema(CHECK_SCHEMA)
        .load(f"{landing}/checks/")
    )
    return build_raw_checks(raw)
