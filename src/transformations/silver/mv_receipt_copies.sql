-- SILVER - exact-copy receipts (audit table).
--
-- In Phase 1 we found 229 receipts that are exact copies of another receipt: same day, same store and
-- identical content (items, payments, discounts, voids, times, totals) - only the receipt number differs.
-- They look like the POS saving the same check twice. We keep the lowest check_id of each group and
-- remove the others from silver.mv_checks. This table lists every removed copy, so nothing disappears
-- without a trace ("flag, don't delete" - this is the one documented exception).
--
-- content_hash is computed in bronze over every field except the receipt number (Id).
-- Copies always share the same day and store, so this is a per-day check: adding a new day never
-- changes the result for earlier days.
CREATE OR REFRESH MATERIALIZED VIEW silver.mv_receipt_copies
COMMENT 'Receipts removed from silver as exact copies of another receipt (same day, store and content). kept_check_id = the receipt we kept.'
TBLPROPERTIES ('quality' = 'silver')
AS
WITH groups AS (
  SELECT
    dt,
    LocationId AS location_id,
    Id         AS check_id,
    min(Id)  OVER (PARTITION BY dt, LocationId, content_hash) AS kept_check_id,
    count(*) OVER (PARTITION BY dt, LocationId, content_hash) AS n_identical
  FROM bronze.st_raw_checks
)
SELECT dt, location_id, check_id, kept_check_id, n_identical
FROM groups
WHERE check_id <> kept_check_id;
