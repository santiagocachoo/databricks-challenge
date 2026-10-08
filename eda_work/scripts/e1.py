# candidate example checks: in-store, 2 guests, 6-12 lines, has void + item/check discount + card payment with tip
show("candidates", """SELECT c.dt, c.location_id, c.check_id, c.n_items, c.n_voids, c.n_check_discounts, c.n_payments FROM checks c
 WHERE c.dt='2026-08-14' AND c.revenue_center_id=1 AND c.traffic_count=2 AND c.n_items BETWEEN 7 AND 11 AND c.n_voids=1 AND c.n_payments=1
 AND EXISTS (SELECT 1 FROM item_discounts d WHERE d.dt=c.dt AND d.location_id=c.location_id AND d.check_id=c.check_id AND d.amount>0)
 AND EXISTS (SELECT 1 FROM payments p WHERE p.dt=c.dt AND p.location_id=c.location_id AND p.check_id=c.check_id AND p.gratuity<0 AND p.is_credit_card)
 LIMIT 5""")
show("open date vs business date", "SELECT CASE WHEN strptime(open_time_raw,'%Y-%m-%dT%H:%M')::DATE > dt THEN 'after midnight' ELSE 'day before' END AS kind, count(*) n FROM checks WHERE strptime(open_time_raw,'%Y-%m-%dT%H:%M')::DATE <> dt GROUP BY 1")
show("top free top-level lines", "SELECT item_name, count(*) n FROM items WHERE parent_seq=0 AND gross_price=0 GROUP BY 1 ORDER BY n DESC LIMIT 10")
show("top free modifiers", "SELECT item_name, count(*) n FROM items WHERE parent_seq>0 AND gross_price=0 GROUP BY 1 ORDER BY n DESC LIMIT 10")
show("card tip % (tip / bill)", """WITH t AS (SELECT -gratuity AS tip, amount+gratuity AS bill FROM payments WHERE is_credit_card AND amount+gratuity>0)
 SELECT count(*) n, round(median(tip/bill)*100,1) med_pct, count(*) FILTER (WHERE tip=0) zero_tip, count(*) FILTER (WHERE tip/bill>0.5) gt50, count(*) FILTER (WHERE tip/bill>1) gt100, round(max(tip),2) max_tip FROM t""")
show("cash tips", "SELECT count(*) n, count(*) FILTER (WHERE gratuity<>0) with_tip FROM payments WHERE pay_cat_name='CASH'")
