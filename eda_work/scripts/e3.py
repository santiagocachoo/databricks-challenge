show("gap stores", "SELECT Id, Name, TimeZoneName FROM loc WHERE Id IN (23,77,80,82,86,113,157) ORDER BY Id")
con.execute("CREATE TABLE ck AS SELECT * FROM '"+CK+"'")
show("munster void rate before gap vs chain", """SELECT location_id=80 AS munster, round(sum(void_amt)/sum(gross_ext)*100,2) void_pct, round(sum(cdisc+idisc)/sum(gross_ext)*100,2) disc_pct FROM ck WHERE dt < '2026-08-01' GROUP BY 1""")
show("munster monthly void %", "SELECT month(dt) m, round(sum(void_amt)/sum(gross_ext)*100,2) void_pct, count(*) n FROM ck WHERE location_id=80 GROUP BY 1 ORDER BY 1")
