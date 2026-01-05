from flask import Flask, render_template, request, send_file, session
import pandas as pd
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.secret_key = "result_analytics_secret"


# =========================
# DATA CLEANING FUNCTION
# =========================
def clean_dataframe(df):
    df["SUBJECT_NAME"] = df["SUBJECT_NAME"].astype(str).str.strip()

    df = df[
        (df["SUBJECT_NAME"] != "") &
        (df["SUBJECT_NAME"].str.lower() != "nan")
    ]

    for col in ["INTERNALMARKS", "EXTERNALMARKS", "TOTALMARKS", "GRADE_POINTS", "CREDITS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["INTERNALMARKS", "EXTERNALMARKS", "TOTALMARKS"],
        how="all"
    )

    return df


# =========================
# HOME
# =========================
@app.route("/")
def upload_page():
    return render_template("upload.html")


# =========================
# UPLOAD
# =========================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")

    if not file or file.filename.strip() == "":
        return "No file selected"

    # Save file
    filename = file.filename
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # Store filename in session (IMPORTANT)
    session["file_name"] = filename

    # Read & clean Excel
    try:
        df = pd.read_excel(path)
    except Exception as e:
        return f"Invalid Excel file: {str(e)}"

    df = clean_dataframe(df)

    # Extract valid subjects
    subjects = list(
        enumerate(
            sorted(df["SUBJECT_NAME"].unique()),
            start=1
        )
    )

    if not subjects:
        return "No valid subjects found in the file."

    return render_template(
        "select_subjects.html",
        subjects=subjects
    )


# =========================
# PROCESS RESULTS
# =========================
@app.route("/process", methods=["POST"])
def process():
    file_name = session.get("file_name")
    if not file_name:
        return "Session expired. Please upload the file again."
    optional_subjects = request.form.getlist("optional_subjects")

    df = clean_dataframe(pd.read_excel(os.path.join(app.config["UPLOAD_FOLDER"], file_name)))

    # =========================
    # PASS / FAIL LOGIC (UNCHANGED)
    # =========================
    def marks_result(row):
        i = row["INTERNALMARKS"]
        e = row["EXTERNALMARKS"]
        t = row["TOTALMARKS"]
        subject = row["SUBJECT_NAME"]

        if e == 0:
            return "PASS" if t >= 40 else "FAIL"

        if subject in optional_subjects:
            return "PASS" if t >= 40 else "FAIL"

        return "PASS" if (i >= 14 and e >= 21 and t >= 35) else "FAIL"

    df["RESULT"] = df.apply(marks_result, axis=1)

    # =========================
    # STUDENT METRICS + SGPA
    # =========================
    student_metrics = []
    rank_list = []
    failure_map = {}
    failed_subjects_by_student = []

    for htno, g in df.groupby("HTNO"):
        total = len(g)
        passed = (g["RESULT"] == "PASS").sum()
        failed = total - passed
        failure_map[htno] = failed

        # SGPA calculation
        passed_g = g[g["RESULT"] == "PASS"]
        total_credits = passed_g["CREDITS"].sum()
        sgpa = (
            (passed_g["GRADE_POINTS"] * passed_g["CREDITS"]).sum() / total_credits
            if total_credits > 0 else 0
        )

        status = "DETAINED" if failed >= 3 else "PROMOTED"

        student_metrics.append({
            "HTNO": htno,
            "Total": total,
            "Passed": passed,
            "Failed": failed,
            "Pass %": round((passed / total) * 100, 2),
            "SGPA": round(sgpa, 2),
            "CGPA": round(sgpa, 2),
            "Status": status
        })

        rank_list.append({
            "HTNO": htno,
            "SGPA": round(sgpa, 2)
        })

        failed_subjects = g[g["RESULT"] == "FAIL"]["SUBJECT_NAME"].tolist()
        if failed_subjects:
            failed_subjects_by_student.append({
                "HTNO": htno,
                "Failed_Count": len(failed_subjects),
                "Failed_Subjects": ", ".join(failed_subjects)
            })

    # =========================
    # FAILURE DISTRIBUTION
    # =========================
    max_fail = max(failure_map.values()) if failure_map else 0
    failure_distribution = []

    for i in range(max_fail + 1):
        failure_distribution.append({
            "Category": "All Subjects Passed" if i == 0 else f"{i} Subject(s) Failed",
            "Students": sum(1 for v in failure_map.values() if v == i)
        })

    # =========================
    # SUBJECT METRICS
    # =========================
    subject_wise_top5 = {}

    for subject, g in df.groupby("SUBJECT_NAME"):
        ranked = (
            g.sort_values("TOTALMARKS", ascending=False)
            .head(5)
            .reset_index(drop=True)
        )

        ranked_list = []
        for i, row in ranked.iterrows():
            ranked_list.append({
                "Rank": i + 1,
                "HTNO": row["HTNO"],
                "TOTALMARKS": row["TOTALMARKS"]
            })

        subject_wise_top5[subject] = ranked_list

    # =========================
    # RANK LIST (SGPA BASED)
    # =========================
    rank_list.sort(key=lambda x: x["SGPA"], reverse=True)

    top5_rank_list = []
    for i, r in enumerate(rank_list[:5], start=1):
        r["Rank"] = i
        top5_rank_list.append(r)


    # =========================
    # SUBJECT-WISE PASS PERCENTAGE
    # =========================
    subject_metrics = []

    for idx, (subject, g) in enumerate(df.groupby("SUBJECT_NAME"), start=1):
        appeared = len(g)
        passed = (g["RESULT"] == "PASS").sum()
        failed = appeared - passed

        subject_metrics.append({
            "SNo": idx,
            "Subject": subject,
            "Appeared": appeared,
            "Passed": passed,
            "Failed": failed,
            "Pass %": round((passed / appeared) * 100, 2) if appeared > 0 else 0
        })

    # =========================
    # EXPORT EXCEL
    # =========================
    export_path = os.path.join(UPLOAD_FOLDER, "Result_Analytics.xlsx")
    with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
        pd.DataFrame(top5_rank_list).to_excel(writer, "Top 5 Overall Ranks", index=False)

        # Subject-wise ranks (each subject in separate sheet)
        for subject, data in subject_wise_top5.items():
            sheet_name = subject[:30]  # Excel sheet name limit
            pd.DataFrame(data).to_excel(writer, sheet_name, index=False)

    return render_template(
        "results.html",
        student_metrics=student_metrics,
        rank_list=top5_rank_list,
        subject_wise_top5=subject_wise_top5,
        failure_distribution=failure_distribution,
        failed_subjects_by_student=failed_subjects_by_student,
        subject_metrics=subject_metrics,
        file_name=file_name
    )


# =========================
# STUDENT SEARCH
# =========================
@app.route("/search", methods=["GET", "POST"])
def search():
    file_name = session.get("file_name")
    if not file_name:
        return "Session expired. Please upload the file again."

    if request.method == "POST":
        htno = request.form["htno"]

        df = clean_dataframe(
            pd.read_excel(os.path.join(app.config["UPLOAD_FOLDER"], file_name))
        )

        student_data = df[df["HTNO"] == htno]

        return render_template(
            "search.html",
            data=student_data.to_dict("records"),
            htno=htno
        )

    return render_template("search.html")


# =========================
# DOWNLOAD EXCEL
# =========================
@app.route("/download")
def download():
    return send_file(
        os.path.join(UPLOAD_FOLDER, "Result_Analytics.xlsx"),
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=True)
