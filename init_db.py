import sqlite3

con = sqlite3.connect("database.db")
cur = con.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS course (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS semester (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER,
    year INTEGER,
    semester INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll_no TEXT UNIQUE,
    name TEXT,
    course_id INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS subject (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semester_id INTEGER,
    subject_name TEXT,
    credits REAL,
    subject_type TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER,
    subject_id INTEGER,
    marks INTEGER,
    grade_points REAL
)
""")

con.commit()
con.close()

print("Database initialized successfully")
