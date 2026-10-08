show("qty>1 lines: is sold_price extended?", """SELECT quantity, gross_price, sold_price, n_item_discounts, item_name FROM items WHERE dt='2026-08-18' AND quantity>1 AND gross_price>0 USING SAMPLE 12 ROWS""")
show("qty ratio test", """SELECT count(*) n, count(*) FILTER (WHERE n_item_discounts=0 AND abs(sold_price-gross_price)<0.01) AS sold_eq_gross, count(*) FILTER (WHERE n_item_discounts=0 AND abs(sold_price-gross_price*quantity)<0.01) AS sold_eq_gross_x_q FROM items WHERE quantity>1 AND gross_price>0""")
show("neg/zero qty samples", """SELECT quantity, gross_price, sold_price, n_item_discounts, item_name, major_cat_name FROM items WHERE dt='2026-08-18' AND quantity<=0 USING SAMPLE 10 ROWS""")
show("gross-sold vs item discounts (lines w/ discount)", """WITH d AS (SELECT dt,location_id,check_id,line_no,sum(amount) amt FROM item_discounts GROUP BY ALL)
 SELECT count(*) n, count(*) FILTER (WHERE abs((i.gross_price - i.sold_price) - d.amt)<0.01) AS eq_unit, count(*) FILTER (WHERE abs((i.gross_price*i.quantity - i.sold_price) - d.amt)<0.01) AS eq_ext FROM items i JOIN d USING (dt,location_id,check_id,line_no)""")
con.execute("""CREATE TABLE ck AS
WITH it AS (SELECT dt,location_id,check_id, sum(sold_price) sold, sum(gross_price*quantity) gross_ext, sum(gross_price) gross FROM items GROUP BY ALL),
cd AS (SELECT dt,location_id,check_id, sum(amount) cdisc FROM check_discounts GROUP BY ALL),
idc AS (SELECT dt,location_id,check_id, sum(amount) idisc FROM item_discounts GROUP BY ALL),
tx AS (SELECT dt,location_id,check_id, sum(amount) tax FROM taxes GROUP BY ALL),
py AS (SELECT dt,location_id,check_id, sum(amount) pay, sum(gratuity) grat FROM payments GROUP BY ALL),
vd AS (SELECT dt,location_id,check_id, sum(amount) void_amt FROM voids GROUP BY ALL)
SELECT c.*, coalesce(sold,0) sold, coalesce(gross,0) gross, coalesce(gross_ext,0) gross_ext, coalesce(cdisc,0) cdisc, coalesce(idisc,0) idisc, coalesce(tax,0) tax, coalesce(pay,0) pay, coalesce(grat,0) grat, coalesce(void_amt,0) void_amt
FROM checks c LEFT JOIN it USING (dt,location_id,check_id) LEFT JOIN cd USING (dt,location_id,check_id) LEFT JOIN idc USING (dt,location_id,check_id)
LEFT JOIN tx USING (dt,location_id,check_id) LEFT JOIN py USING (dt,location_id,check_id) LEFT JOIN vd USING (dt,location_id,check_id)""")
show("reconciliation hypotheses (share of checks within 1 cent)", """SELECT count(*) n,
 avg((abs(pay - (sold + tax))<0.015)::INT) AS h1_sold_tax,
 avg((abs(pay - (sold - cdisc + tax))<0.015)::INT) AS h2_sold_minus_cdisc_tax,
 avg((abs(pay - (sold - cdisc + tax + grat))<0.015)::INT) AS h3_plus_grat,
 avg((abs(pay - grat - (sold - cdisc + tax))<0.015)::INT) AS h4_pay_minus_grat,
 avg((abs(pay - (sold + tax + grat))<0.015)::INT) AS h5 FROM ck""")
show("money totals ($)", "SELECT round(sum(gross_ext)) gross_ext, round(sum(sold)) sold, round(sum(idisc)) item_disc, round(sum(cdisc)) check_disc, round(sum(tax)) tax, round(sum(pay)) pay, round(sum(grat)) grat, round(sum(void_amt)) voids FROM ck")
con.execute(f"COPY ck TO '{CK}' (FORMAT parquet)")
