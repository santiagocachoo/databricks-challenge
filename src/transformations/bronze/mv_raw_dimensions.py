"""
BRONZE - lookup files (stores, sales channels, employees) as MATERIALIZED VIEWS.

Source : /Volumes/<catalog>/bronze/landing/dimensions/*.json.gz (full snapshots, not daily files)
Why MV : a lookup file is replaced as a whole when it changes, so it is re-read in full on each
         refresh. A streaming table would append the same rows again every time a new copy lands.

PRIVACY: the HR file contains names, birth dates and payroll / location employee IDs.
         The employee schema below simply does not declare those fields, so Spark never parses
         them and they never reach any table (not even bronze). Only the anonymous employee Id is kept.
"""
from pyspark.sql import functions as F

try:
    from pyspark import pipelines as dp
except ImportError:  # older Databricks runtimes expose the same API as `dlt`
    import dlt as dp

materialized_view = getattr(dp, "materialized_view", dp.table)

LOCATION_SCHEMA = "Id BIGINT, Name STRING, OpenDate STRING, ClosedDate STRING, TimeZoneName STRING"
REVENUE_CENTER_SCHEMA = "Id BIGINT, Name STRING"
# No Name, DateOfBirth, LocationEmployeeId, PayrollEmployeeId, AlternateEmployeeId (privacy) and
# no IsEmancipated (100% empty in Phase 1).
EMPLOYEE_SCHEMA = (
    "Id BIGINT, LocationId BIGINT, Deleted BOOLEAN, Borrowed BOOLEAN, HomeLocationId BIGINT, "
    "PrimaryJobID BIGINT, HireDate STRING, IsMinor BOOLEAN, JobID ARRAY<BIGINT>"
)


def read_lookup(file_name, schema):
    landing = spark.conf.get("landing_path")  # noqa: F821 - `spark` is provided by the pipeline runtime
    return (
        spark.read.format("json")  # noqa: F821
        .option("multiLine", "true")
        .schema(schema)
        .load(f"{landing}/dimensions/{file_name}")
        .withColumn("source_file", F.col("_metadata.file_path"))
    )


@materialized_view(name="bronze.mv_raw_locations", comment="Store list as received (127 restaurants).",
                   table_properties={"quality": "bronze"})
@dp.expect_or_drop("store_id_present", "Id IS NOT NULL")
def mv_raw_locations():
    return read_lookup("locations.json.gz", LOCATION_SCHEMA)


@materialized_view(name="bronze.mv_raw_revenue_centers", comment="Sales channels (revenue centers) as received.",
                   table_properties={"quality": "bronze"})
@dp.expect_or_drop("channel_id_present", "Id IS NOT NULL")
def mv_raw_revenue_centers():
    return read_lookup("revenue_centers.json.gz", REVENUE_CENTER_SCHEMA)


@materialized_view(name="bronze.mv_raw_employees",
                   comment="HR employee records WITHOUT personal data (no names, birth dates or payroll IDs).",
                   table_properties={"quality": "bronze", "contains_pii": "false"})
@dp.expect_or_drop("employee_id_present", "Id IS NOT NULL")
def mv_raw_employees():
    return read_lookup("employees.json.gz", EMPLOYEE_SCHEMA)
