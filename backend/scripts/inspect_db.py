import sqlite3

con = sqlite3.connect("data/sentinel.db")
for name, sql in con.execute("select name, sql from sqlite_master where type='table'"):
    print(name)
    print(sql)
    print("---")
