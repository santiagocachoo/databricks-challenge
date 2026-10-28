show("locations summary", "SELECT count(DISTINCT location_id) AS n_loc FROM checks")
show("store-days missing", """WITH ld AS (SELECT location_id, count(DISTINCT dt) AS d FROM checks GROUP BY 1) SELECT location_id, d, 115-d AS missing FROM ld WHERE d<115 ORDER BY d""")
show("missing day list for gaps", """WITH ls AS (SELECT location_id FROM checks GROUP BY 1 HAVING count(DISTINCT dt)<115), days AS (SELECT DISTINCT dt FROM checks)
 SELECT ls.location_id, list(days.dt ORDER BY days.dt) AS missing FROM ls CROSS JOIN days WHERE NOT EXISTS (SELECT 1 FROM checks c WHERE c.location_id=ls.location_id AND c.dt=days.dt) GROUP BY 1""")
show("time raw formats", """SELECT length(open_time_raw) AS lo, length(close_time_raw) AS lc, count(*) AS n FROM checks GROUP BY ALL ORDER BY n DESC""")
show("time sanity", """WITH t AS (SELECT try_strptime(open_time_raw,'%Y-%m-%dT%H:%M') o, try_strptime(close_time_raw,'%Y-%m-%dT%H:%M') c, dt FROM checks)
 SELECT count(*) FILTER (WHERE o IS NULL) AS o_null, count(*) FILTER (WHERE c IS NULL) AS c_null, count(*) FILTER (WHERE c<o) AS close_before_open,
 count(*) FILTER (WHERE date_diff('minute',o,c)=0) AS zero_min, count(*) FILTER (WHERE date_diff('minute',o,c)>360) AS gt6h,
 count(*) FILTER (WHERE o::DATE<>dt) AS open_not_dt, approx_quantile(date_diff('minute',o,c),[0.05,0.5,0.95,0.999]) AS dur_q FROM t""")
show("checks numeric", """SELECT min(traffic_count) mn_tc, max(traffic_count) mx_tc, count(*) FILTER (WHERE traffic_count=0) tc0, count(*) FILTER (WHERE traffic_count<0) tcneg, count(*) FILTER (WHERE traffic_count<>floor(traffic_count)) tc_frac,
 count(*) FILTER (WHERE service_charge<>0) sc_nz, count(*) FILTER (WHERE loyalty_id IS NOT NULL) loyalty_nn, count(*) FILTER (WHERE n_items=0) no_items, count(*) FILTER (WHERE n_payments=0) no_pay,
 count(*) FILTER (WHERE n_voids>0) w_voids, count(*) FILTER (WHERE n_check_discounts>0) w_cdisc, count(*) FILTER (WHERE table_name IS NULL OR table_name='') tbl_empty FROM checks""")
show("items numeric", """SELECT count(*) FILTER (WHERE quantity<=0) q_le0, count(*) FILTER (WHERE quantity<>floor(quantity)) q_frac, max(quantity) q_max,
 count(*) FILTER (WHERE gross_price<0) gp_neg, count(*) FILTER (WHERE gross_price=0) gp0, max(gross_price) gp_max, count(*) FILTER (WHERE sold_price<0) sp_neg,
 count(*) FILTER (WHERE sold_price>gross_price+0.005) sp_gt_gp, count(*) FILTER (WHERE sold_price<gross_price-0.005) sp_lt_gp, count(*) FILTER (WHERE sold_price<gross_price-0.005 AND n_item_discounts=0) sp_lt_gp_no_disc,
 count(*) FILTER (WHERE employee_id IS NULL OR employee_id=0) emp_missing, count(*) FILTER (WHERE item_id NOT IN (SELECT Id FROM itm)) item_not_in_dim FROM items""")
show("item names top-level cats", "SELECT major_cat_name, count(*) n, round(sum(sold_price),0) sold FROM items GROUP BY 1 ORDER BY n DESC")
