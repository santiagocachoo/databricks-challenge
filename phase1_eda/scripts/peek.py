import tempfile
DUCK_TMP = (__import__("pathlib").Path(tempfile.gettempdir()) / "duckdb_spill").as_posix()  # works on macOS, Linux and Windows
import duckdb, time, sys
f = sys.argv[1]
con = duckdb.connect()
con.execute(f"SET memory_limit='2GB'; SET threads=4; SET temp_directory='{DUCK_TMP}'")
t=time.time()
con.execute(f"CREATE TABLE c AS SELECT * FROM read_json('{f}', format='array', maximum_object_size=100000000, sample_size=-1)")
print("load s", round(time.time()-t,1))
print(con.execute("SELECT count(*) FROM c").fetchall())
for r in con.execute("DESCRIBE c").fetchall(): print(r[0], '|', r[1][:400])
