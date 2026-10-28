con.execute("""CREATE TABLE cand AS SELECT c.dt, c.location_id, c.check_id, c.n_items, c.n_voids, c.n_check_discounts FROM checks c
 WHERE c.dt='2026-08-14' AND c.revenue_center_id=1 AND c.traffic_count=2 AND c.n_items BETWEEN 6 AND 12 AND c.n_voids>=1 AND c.n_payments=1
 AND (c.n_check_discounts>=1 OR EXISTS (SELECT 1 FROM item_discounts d WHERE d.dt=c.dt AND d.location_id=c.location_id AND d.check_id=c.check_id AND d.amount>0))
 AND EXISTS (SELECT 1 FROM payments p WHERE p.dt=c.dt AND p.location_id=c.location_id AND p.check_id=c.check_id AND p.gratuity<0 AND p.is_credit_card)
 AND EXISTS (SELECT 1 FROM items i WHERE i.dt=c.dt AND i.location_id=c.location_id AND i.check_id=c.check_id AND i.parent_seq>0)""")
show("n cand", "SELECT count(*) FROM cand")
k = con.execute("SELECT location_id, check_id FROM cand ORDER BY n_items, check_id LIMIT 1 OFFSET 3").fetchone()
L, C = k
W = f"dt='2026-08-14' AND location_id={L} AND check_id={C}"
show("header", f"SELECT c.location_id, l.Name AS store, c.check_id, table_name, open_time_raw, close_time_raw, traffic_count, revenue_center_id FROM checks c JOIN loc l ON l.Id=c.location_id WHERE {W}")
show("items", f"SELECT line_no, seq, parent_seq, item_name, quantity, gross_price, sold_price, employee_id, major_cat_name FROM items WHERE {W} ORDER BY line_no")
show("item discounts", f"SELECT line_no, discount_name, amount, employee_id, manager_id FROM item_discounts WHERE {W}")
show("check discounts", f"SELECT discount_name, amount, employee_id, manager_id FROM check_discounts WHERE {W}")
show("voids", f"SELECT item_name, quantity, amount, void_cat_name, employee_id, manager_id FROM voids WHERE {W}")
show("taxes", f"SELECT tax_cat_name, amount FROM taxes WHERE {W}")
show("payments", f"SELECT pay_cat_name, amount, gratuity, employee_id FROM payments WHERE {W}")
