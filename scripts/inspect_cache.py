import sqlite3
con = sqlite3.connect(r"C:\Users\anass\OneDrive\Desktop\ARIS\fastf1_cache\fastf1_http_cache.sqlite")
cur = con.cursor()
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print("table:", r)
print("---")
cur.execute("PRAGMA table_info(responses)")
print("schema:", cur.fetchall())
print("---")
try:
    cur.execute("SELECT cache_key, expires FROM responses WHERE url LIKE '%schedule%' LIMIT 10")
    for r in cur.fetchall():
        print(r)
except Exception:
    pass
