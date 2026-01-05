from flask import Flask, render_template, request, redirect, session
import sqlite3
import pandas as pd

app = Flask(__name__)
app.secret_key = "exam_secret"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

def db():
    return sqlite3.connect("database.db")

# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["admin"] = True
            return redirect("/admin/dashboard")
    return render_template("admin_login.html")

@app.route("/admin/dashboard", methods=["GET", "POST"])
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    con = db()
    cur = con.cursor()

    if request.method == "POST":
        cur.execute("INSERT OR IGNORE INTO course(name) VALUES (?)",
                    (request.form["course"],))
        con.commit()

    courses = cur.execute("SELECT name FROM course").fetchall()
    return render_template("admin_dashboard.html", courses=courses)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/admin")

# ---------------- UPLOAD RESULTS ----------------
@app.route("/", methods=["GET", "POST"])
def upload_results():
    con = db()
    cur = con.cursor()
    courses = [c[0] for c in cur.execute("SELECT name FROM course").fetchall()]

    if request.method == "POST":
        try:
            course = request.form["course"]
            year = int(request.form["year"])
            semester = int(request.form["semester"])
            file = request.files["file"]

            # Read file safely
            if file.filename.endswith(".xlsx"):
                df = pd.read_excel(file, engine="openpyxl")
            elif file.filename.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                return "Invalid file format"

            # Required columns check
            required = ["HTNO", "SUBJECT_NAME", "TOTALMARKS", "CREDITS"]
            for col in required:
                if col not in df.columns:
                    return f"Missing column: {col}"

            course_id = cur.execute(
                "SELECT id FROM course WHERE name=?", (course,)
            ).fetchone()[0]

            cur.execute("""
                INSERT INTO semester(course_id, year, semester)
                VALUES (?, ?, ?)
            """, (course_id, year, semester))
            sem_id = cur.lastrowid

            for _, row in df.iterrows():
                if pd.isna(row["TOTALMARKS"]):
                    continue

                htno = str(row["HTNO"]).strip()
                subject = row["SUBJECT_NAME"]
                marks = int(row["TOTALMARKS"])
                credits = float(row["CREDITS"])
                grade_points = float(row["GRADE_POINTS"]) if "GRADE_POINTS" in df.columns and not pd.isna(row["GRADE_POINTS"]) else 0

                # Student
                cur.execute("""
                    INSERT OR IGNORE INTO student(roll_no, name, course_id)
                    VALUES (?, ?, ?)
                """, (htno, htno, course_id))

                student_id = cur.execute(
                    "SELECT id FROM student WHERE roll_no=?", (htno,)
                ).fetchone()[0]

                # Subject
                cur.execute("""
                    INSERT OR IGNORE INTO subject(semester_id, subject_name, credits, subject_type)
                    VALUES (?, ?, ?, ?)
                """, (
                    sem_id,
                    subject,
                    credits,
                    "LAB" if "LAB" in subject.upper() else "THEORY"
                ))

                subject_id = cur.execute("""
                    SELECT id FROM subject
                    WHERE semester_id=? AND subject_name=?
                """, (sem_id, subject)).fetchone()[0]

                # Marks
                cur.execute("""
                    INSERT INTO marks(student_id, subject_id, marks, grade_points)
                    VALUES (?, ?, ?, ?)
                """, (student_id, subject_id, marks, grade_points))

            con.commit()
            return "✅ Results uploaded successfully"

        except Exception as e:
            con.rollback()
            return f"❌ Error: {str(e)}"

    return render_template("upload.html", courses=courses)

# ---------------- RESULT OVERVIEW ----------------
@app.route("/overview", methods=["GET", "POST"])
def overview():
    con = db()
    cur = con.cursor()

    courses = [c[0] for c in cur.execute("SELECT name FROM course").fetchall()]
    data = []
    stats = None

    if request.method == "POST":
        course = request.form["course"].strip()
        year = int(request.form["year"])
        semester = int(request.form["semester"])

        rows = cur.execute("""
            SELECT s.roll_no,
                   sub.subject_name,
                   m.marks,
                   sub.credits,
                   m.grade_points
            FROM marks m
            JOIN student s ON m.student_id = s.id
            JOIN subject sub ON m.subject_id = sub.id
            JOIN semester sem ON sub.semester_id = sem.id
            JOIN course c ON sem.course_id = c.id
            WHERE TRIM(c.name)=?
              AND sem.year=?
              AND sem.semester=?
        """, (course, year, semester)).fetchall()

        data = rows

        students = set(r[0] for r in rows)
        passed = set(r[0] for r in rows if r[2] >= 40)

        stats = {
            "total": len(students),
            "passed": len(passed),
            "failed": len(students) - len(passed),
            "pass_percent": round((len(passed) / len(students)) * 100, 2)
            if students else 0
        }

    return render_template(
        "overview.html",
        courses=courses,
        data=data,
        stats=stats
    )

if __name__ == "__main__":
    app.run(debug=True)
