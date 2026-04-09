import sqlite3

conn = sqlite3.connect("example.db")
cur = conn.cursor()

cur.execute("CREATE TABLE users (id INT, name TEXT, age INT)")
cur.executemany(
    "INSERT INTO users VALUES (?, ?, ?)",
    [(1, "Alice", 25), (2, "Bob", 30), (3, "Charlie", None)]
)

conn.commit()
conn.close()
