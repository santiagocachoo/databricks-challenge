show("emp dim profile", """SELECT count(*) n, count(DISTINCT Id) u_id, count(*) FILTER (WHERE Deleted) deleted, count(*) FILTER (WHERE Borrowed) borrowed, count(*) FILTER (WHERE IsMinor) minor,
 count(*) FILTER (WHERE DateOfBirth IS NULL) dob_null, count(*) FILTER (WHERE HireDate IS NULL) hire_null, count(*) FILTER (WHERE len(JobID)=0) no_jobs, count(DISTINCT LocationId) n_loc,
 count(*) FILTER (WHERE LocationId NOT IN (SELECT Id FROM loc)) loc_orphan, count(DISTINCT PrimaryJobID) n_primary_jobs FROM emp""")
show("emp names dup", "SELECT count(*) FROM (SELECT lower(Name) nm, count(*) c FROM emp GROUP BY 1 HAVING c>1)")
show("primary jobs", "SELECT PrimaryJobID, count(*) n FROM emp GROUP BY 1 ORDER BY n DESC LIMIT 25", 25)
con.execute("CREATE TABLE fe AS SELECT DISTINCT employee_id FROM items UNION SELECT DISTINCT employee_id FROM payments UNION SELECT DISTINCT employee_id FROM voids UNION SELECT DISTINCT employee_id FROM item_discounts UNION SELECT DISTINCT employee_id FROM check_discounts")
con.execute("CREATE TABLE fm AS SELECT DISTINCT manager_id FROM voids UNION SELECT DISTINCT manager_id FROM item_discounts UNION SELECT DISTINCT manager_id FROM check_discounts")
show("fact employees vs dim", """SELECT (SELECT count(*) FROM fe) n_fact_emp, (SELECT count(*) FROM fe WHERE employee_id NOT IN (SELECT Id FROM emp)) not_in_dim,
 (SELECT count(*) FROM fe JOIN emp ON emp.Id=fe.employee_id WHERE emp.Deleted) deleted_but_active,
 (SELECT count(*) FROM fm) n_mgr, (SELECT count(*) FROM fm WHERE manager_id NOT IN (SELECT Id FROM emp)) mgr_not_in_dim""")
show("orphan emp ids sample", "SELECT employee_id FROM fe WHERE employee_id NOT IN (SELECT Id FROM emp) LIMIT 10")
show("employee location mismatch (items emp at other store)", """WITH x AS (SELECT DISTINCT i.employee_id, i.location_id FROM items i) SELECT count(*) pairs, count(*) FILTER (WHERE e.LocationId<>x.location_id) other_store, count(*) FILTER (WHERE e.Borrowed) borrowed FROM x JOIN emp e ON e.Id=x.employee_id""")
