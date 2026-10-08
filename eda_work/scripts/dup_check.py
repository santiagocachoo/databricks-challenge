# Step 2: decide which look-alike checks are true duplicates vs split bills.
# Look-alike group = same date, store, table, open/close minute, channel, line count, payment count, sales, payment total and tax.
# Inside a group, checks whose item lines, payments, discounts and voids are ALL identical are true duplicates.
con.execute(f"CREATE TABLE ck AS SELECT * FROM '{CK}'")
con.execute("""CREATE TABLE cand AS
SELECT dt, location_id, check_id, n_items, revenue_center_id, sold, pay,
  dense_rank() OVER (ORDER BY dt, location_id, table_name, open_time_raw, close_time_raw, revenue_center_id, n_items, n_payments, round(sold,2), round(pay,2), round(tax,2)) AS grp_id,
  count(*) OVER (PARTITION BY dt, location_id, table_name, open_time_raw, close_time_raw, revenue_center_id, n_items, n_payments, round(sold,2), round(pay,2), round(tax,2)) AS grp_n
FROM ck QUALIFY grp_n > 1""")
K = "USING (dt, location_id, check_id)"
con.execute(f"""CREATE TABLE sig AS
WITH i AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', seq, parent_seq, item_id, quantity, gross_price, sold_price, employee_id, order_time_raw, seat), ';' ORDER BY line_no)) s FROM items SEMI JOIN cand {K} GROUP BY ALL),
p AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', pay_cat_name, amount, gratuity, employee_id), ';' ORDER BY pay_cat_name, amount, gratuity)) s FROM payments SEMI JOIN cand {K} GROUP BY ALL),
d AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', lvl, discount_name, amount, employee_id, manager_id), ';' ORDER BY lvl, discount_name, amount)) s FROM
      (SELECT dt, location_id, check_id, 'i' lvl, discount_name, amount, employee_id, manager_id FROM item_discounts UNION ALL SELECT dt, location_id, check_id, 'c', discount_name, amount, employee_id, manager_id FROM check_discounts) SEMI JOIN cand {K} GROUP BY ALL),
v AS (SELECT dt, location_id, check_id, md5(string_agg(concat_ws('|', item_id, amount, void_cat_name, employee_id), ';' ORDER BY item_id, amount)) s FROM voids SEMI JOIN cand {K} GROUP BY ALL)
SELECT c.*, coalesce(i.s,'') isig, coalesce(p.s,'') psig, coalesce(d.s,'') dsig, coalesce(v.s,'') vsig FROM cand c LEFT JOIN i {K} LEFT JOIN p {K} LEFT JOIN d {K} LEFT JOIN v {K}""")
con.execute("""CREATE TABLE dupres AS SELECT *, count(*) OVER (PARTITION BY grp_id, isig, psig, dsig, vsig) AS twin_n,
  min(check_id) OVER (PARTITION BY grp_id, isig, psig, dsig, vsig) AS kept_check_id FROM sig""")
show("groups and checks", "SELECT count(DISTINCT grp_id) AS n_groups, count(*) AS n_checks FROM dupres")
show("classification (checks)", """SELECT CASE WHEN twin_n>1 THEN 'identical inside' ELSE 'differs (split bill)' END AS cls, count(*) AS n_checks, count(DISTINCT grp_id) AS n_groups, count(*) FILTER (WHERE twin_n>1 AND check_id<>kept_check_id) AS extra_copies FROM dupres GROUP BY 1""")
show("identical: by line count", "SELECT CASE WHEN n_items<=2 THEN '1-2 lines' WHEN n_items<=5 THEN '3-5' WHEN n_items<=10 THEN '6-10' ELSE '11+' END b, count(*) n FROM dupres WHERE twin_n>1 GROUP BY 1 ORDER BY 1")
show("identical: check id gap to kept", "SELECT CASE WHEN check_id-kept_check_id=1 THEN 'next id' WHEN check_id-kept_check_id<=5 THEN '2-5' ELSE '>5' END g, count(*) n FROM dupres WHERE twin_n>1 AND check_id<>kept_check_id GROUP BY 1")
show("identical: channel", "SELECT revenue_center_id, count(*) n FROM dupres WHERE twin_n>1 GROUP BY 1 ORDER BY n DESC LIMIT 5")
show("identical: money", "SELECT round(sum(sold) FILTER (WHERE check_id<>kept_check_id)) extra_sales, round(sum(pay) FILTER (WHERE check_id<>kept_check_id)) extra_pay FROM dupres WHERE twin_n>1")
show("sample identical", "SELECT dt, location_id, check_id, kept_check_id, n_items, round(sold,2) sold, revenue_center_id FROM dupres WHERE twin_n>1 AND check_id<>kept_check_id ORDER BY n_items DESC LIMIT 6")
con.execute("COPY dupres TO '/tmp/dupres.parquet'")
