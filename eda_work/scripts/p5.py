con.execute("CREATE TABLE ck AS SELECT * FROM '"+CK+"'")
show("reconcile v2", """SELECT count(*) n,
 avg((abs((pay + grat) - (sold - cdisc + tax))<0.015)::INT) AS h6,
 avg((abs((pay + grat) - (sold - cdisc + tax))<1.0)::INT) AS h6_1usd,
 avg((abs((pay + grat) - (sold + tax))<0.015)::INT) AS h7_nocdisc,
 avg((abs(pay - (sold - cdisc + tax))<0.015)::INT) AS h2
 FROM ck""")
show("residual h6 buckets", """WITH r AS (SELECT (pay + grat) - (sold - cdisc + tax) AS res, n_payments FROM ck)
 SELECT CASE WHEN abs(res)<0.015 THEN 'a_balanced' WHEN n_payments=0 THEN 'b_no_payment' WHEN res<0 THEN 'c_underpaid' ELSE 'd_overpaid' END AS bucket,
 count(*) n, round(sum(res)) total_res, round(median(res),2) med FROM r GROUP BY 1 ORDER BY 1""")
show("residual vs revenue center", """WITH r AS (SELECT revenue_center_id, abs((pay + grat) - (sold - cdisc + tax))<0.015 AS bal FROM ck)
 SELECT revenue_center_id, count(*) n, round(avg(bal::INT),3) bal_rate FROM r GROUP BY 1 ORDER BY n DESC LIMIT 8""")
show("underpaid samples", """SELECT revenue_center_id, n_items, n_payments, sold, cdisc, tax, pay, grat, round((pay+grat)-(sold-cdisc+tax),2) res FROM ck WHERE n_payments>0 AND abs((pay + grat) - (sold - cdisc + tax))>=0.015 AND dt='2026-08-18' LIMIT 12""")
show("gratuity sign", "SELECT count(*) FILTER (WHERE gratuity<0) neg, count(*) FILTER (WHERE gratuity>0) pos, count(*) FILTER (WHERE gratuity=0) zero FROM payments")
