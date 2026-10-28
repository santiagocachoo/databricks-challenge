-- SILVER - clean lookup tables (materialized views over the bronze lookup files).

-- Stores: renamed columns, typed dates, and how many days each store appears in the loaded data.
CREATE OR REFRESH MATERIALIZED VIEW silver.mv_stores
COMMENT 'One row per restaurant. days_in_data = business days with at least one receipt in the loaded data.'
TBLPROPERTIES ('quality' = 'silver')
AS
SELECT
  l.Id                          AS location_id,
  l.Name                        AS store_name,
  try_cast(l.OpenDate AS DATE)  AS open_date,
  try_cast(l.ClosedDate AS DATE) AS closed_date,
  l.TimeZoneName                AS time_zone,
  coalesce(d.days_in_data, 0)   AS days_in_data,
  coalesce(d.days_in_data, 0) > 0 AS active_in_data
FROM bronze.mv_raw_locations l
LEFT JOIN (
  SELECT LocationId, count(DISTINCT dt) AS days_in_data
  FROM bronze.st_raw_checks
  GROUP BY LocationId
) d ON d.LocationId = l.Id;

-- Sales channels: the same grouping we used in Phase 1.
CREATE OR REFRESH MATERIALIZED VIEW silver.mv_channels
COMMENT 'Revenue centers grouped into channels (Dine-in, To go, Online order, Delivery app, Catering, Other).'
TBLPROPERTIES ('quality' = 'silver')
AS
SELECT
  Id   AS revenue_center_id,
  Name AS channel,
  CASE
    WHEN Id = 1 THEN 'Dine-in'
    WHEN Id = 2 THEN 'To go'
    WHEN Id IN (3, 4, 24, 25, 26, 27) THEN 'Online order'
    WHEN Id = 7 THEN 'Catering'
    WHEN Id IN (6, 11, 12, 13, 14, 15, 17, 18, 20, 21, 23) THEN 'Delivery app'
    ELSE 'Other'
  END AS channel_group
FROM bronze.mv_raw_revenue_centers;

-- Employees: anonymous HR attributes only (personal data was never parsed in bronze).
CREATE OR REFRESH MATERIALIZED VIEW silver.mv_employees
COMMENT 'One row per HR employee record, no personal data. rings_sales = appears on at least one item line in the loaded data.'
TBLPROPERTIES ('quality' = 'silver', 'contains_pii' = 'false')
AS
SELECT
  e.Id                        AS employee_id,
  e.LocationId                AS home_store_id,
  e.PrimaryJobID              AS primary_job_id,
  e.JobID                     AS job_ids,
  e.Deleted                   AS is_deleted_in_hr,
  e.Borrowed                  AS is_borrowed,
  try_cast(e.HireDate AS DATE) AS hire_date,
  e.IsMinor                   AS is_minor,
  s.employee_id IS NOT NULL   AS rings_sales
FROM bronze.mv_raw_employees e
LEFT JOIN (SELECT DISTINCT employee_id FROM silver.st_items WHERE employee_id IS NOT NULL) s
  ON s.employee_id = e.Id;
