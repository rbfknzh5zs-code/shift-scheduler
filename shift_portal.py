#!/usr/bin/env python3
"""スタッフの月次シフト希望入力ポータル (LINE/LIFF対応向け最小構成)"""

from __future__ import annotations

import calendar
import csv
import io
import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, flash, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = (
    Path("/tmp/shift_portal.db")
    if os.environ.get("VERCEL")
    else BASE_DIR / "data" / "shift_portal.db"
)
DB_PATH = Path(os.environ.get("SHIFT_PORTAL_DB_PATH", str(DEFAULT_DB_PATH)))
STAFF_CSV_PATH = BASE_DIR / "sample_data" / "staff.csv"

DAY_NAMES = "月火水木金土日"
STATUS_CHOICES = [
    ("available", "出勤可"),
    ("requested_off", "申請休"),
    ("contract_off", "契約休"),
    ("paid_leave", "有給"),
]
STATUS_LABELS = dict(STATUS_CHOICES)
REQUEST_PRIORITY = {
    "requested_off": "希望",
    "contract_off": "必須",
    "paid_leave": "必須",
}


app = Flask(__name__)
app.secret_key = "shift-portal-local-secret"


def next_month(today: date | None = None) -> tuple[int, int]:
    t = today or date.today()
    if t.month == 12:
        return t.year + 1, 1
    return t.year, t.month + 1


def parse_ym(args) -> tuple[int, int]:
    ny, nm = next_month()
    year = int(args.get("year", ny))
    month = int(args.get("month", nm))
    if month < 1 or month > 12:
        raise ValueError("month must be 1-12")
    return year, month


def month_dates(year: int, month: int) -> list[date]:
    _, last = calendar.monthrange(year, month)
    return [date(year, month, d) for d in range(1, last + 1)]


def day_name(d: date) -> str:
    return DAY_NAMES[d.weekday()]


def normalize_hhmm(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    if len(value) == 5 and value[2] == ":":
        hh = int(value[:2])
        mm = int(value[3:])
    else:
        hh, mm = map(int, value.split(":", 1))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("時刻は HH:MM 形式で入力してください")
    return f"{hh:02d}:{mm:02d}"


def hhmm_to_minutes(text: str) -> int:
    hh, mm = map(int, text.split(":"))
    return hh * 60 + mm


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                submitted_at TEXT NOT NULL,
                UNIQUE(name, year, month)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS day_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                submission_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                status TEXT NOT NULL,
                start_time TEXT,
                end_time TEXT,
                UNIQUE(submission_id, day),
                FOREIGN KEY(submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_year_month ON submissions(year, month)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_day_entries_day ON day_entries(day)")


def load_staff_names() -> list[str]:
    names = []
    if STAFF_CSV_PATH.exists():
        with open(STAFF_CSV_PATH, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                n = row.get("name", "").strip()
                if n:
                    names.append(n)
    return sorted(set(names))


def get_submission(name: str, year: int, month: int) -> tuple[dict, str]:
    entry_map = {}
    comment = ""
    with get_conn() as conn:
        sub = conn.execute(
            "SELECT id, comment FROM submissions WHERE name = ? AND year = ? AND month = ?",
            (name, year, month),
        ).fetchone()
        if not sub:
            return entry_map, comment
        comment = sub["comment"] or ""
        rows = conn.execute(
            "SELECT day, status, start_time, end_time FROM day_entries WHERE submission_id = ?",
            (sub["id"],),
        ).fetchall()
        for row in rows:
            entry_map[row["day"]] = {
                "status": row["status"],
                "start_time": row["start_time"] or "",
                "end_time": row["end_time"] or "",
            }
    return entry_map, comment


def build_form_rows(year: int, month: int, entry_map: dict) -> list[dict]:
    rows = []
    for d in month_dates(year, month):
        key = d.isoformat()
        existing = entry_map.get(key) or {}
        status = existing.get("status", "available")
        start_time = existing.get("start_time", "09:00")
        end_time = existing.get("end_time", "18:00")
        rows.append(
            {
                "date": d,
                "key": key,
                "day_name": day_name(d),
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
    return rows


def upsert_submission(name: str, year: int, month: int, comment: str, entries: list[dict]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO submissions(name, year, month, comment, submitted_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name, year, month)
            DO UPDATE SET comment = excluded.comment, submitted_at = excluded.submitted_at
            """,
            (name, year, month, comment, now),
        )
        sub = conn.execute(
            "SELECT id FROM submissions WHERE name = ? AND year = ? AND month = ?",
            (name, year, month),
        ).fetchone()
        submission_id = sub["id"]
        conn.execute("DELETE FROM day_entries WHERE submission_id = ?", (submission_id,))
        conn.executemany(
            """
            INSERT INTO day_entries(submission_id, day, status, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    submission_id,
                    row["day"],
                    row["status"],
                    row["start_time"],
                    row["end_time"],
                )
                for row in entries
            ],
        )


def validate_entries(year: int, month: int, form_data) -> tuple[list[dict], list[str]]:
    entries = []
    errors = []
    valid_statuses = {k for k, _ in STATUS_CHOICES}

    for d in month_dates(year, month):
        key = d.isoformat()
        status = form_data.get(f"status_{key}", "available")
        if status not in valid_statuses:
            status = "available"

        start_time = (form_data.get(f"start_{key}") or "").strip()
        end_time = (form_data.get(f"end_{key}") or "").strip()

        if status == "available":
            try:
                start_time = normalize_hhmm(start_time)
                end_time = normalize_hhmm(end_time)
                if hhmm_to_minutes(start_time) >= hhmm_to_minutes(end_time):
                    raise ValueError("開始時刻は終了時刻より前にしてください")
            except Exception:
                errors.append(f"{key} の勤務可能時間を正しく入力してください (例: 09:00-18:00)")
        else:
            start_time = ""
            end_time = ""

        entries.append(
            {
                "day": key,
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
    return entries, errors


def fetch_month_answers(year: int, month: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT s.name, s.comment, s.submitted_at, d.day, d.status, d.start_time, d.end_time
            FROM submissions s
            JOIN day_entries d ON d.submission_id = s.id
            WHERE s.year = ? AND s.month = ?
            ORDER BY d.day, s.name
            """,
            (year, month),
        ).fetchall()


def build_admin_view_data(year: int, month: int) -> dict:
    dates = month_dates(year, month)
    rows = fetch_month_answers(year, month)
    staff_names = set(load_staff_names())
    staff_names.update(row["name"] for row in rows)
    ordered_staff = sorted(staff_names)

    matrix = {name: {d.isoformat(): "未提出" for d in dates} for name in ordered_staff}
    comments = {name: "" for name in ordered_staff}
    submitted_at = {name: "" for name in ordered_staff}
    by_day = {d.isoformat(): [] for d in dates}
    counts = {
        d.isoformat(): {key: 0 for key, _ in STATUS_CHOICES}
        for d in dates
    }

    for row in rows:
        dkey = row["day"]
        name = row["name"]
        status = row["status"]
        start = row["start_time"] or ""
        end = row["end_time"] or ""

        if status == "available":
            label = f"{start}-{end}"
        else:
            label = STATUS_LABELS.get(status, status)

        matrix[name][dkey] = label
        comments[name] = row["comment"] or ""
        submitted_at[name] = row["submitted_at"]
        counts[dkey][status] = counts[dkey].get(status, 0) + 1
        by_day[dkey].append(
            {
                "name": name,
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "time_text": f"{start}-{end}" if status == "available" else "-",
            }
        )

    # 日曜始まりのカレンダー
    cal = calendar.Calendar(firstweekday=6)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        cells = []
        for d in week:
            if d.month != month:
                cells.append(None)
            else:
                cells.append(
                    {
                        "date": d,
                        "key": d.isoformat(),
                        "counts": counts[d.isoformat()],
                        "entries": by_day[d.isoformat()],
                    }
                )
        weeks.append(cells)

    return {
        "dates": dates,
        "staff_names": ordered_staff,
        "matrix": matrix,
        "comments": comments,
        "submitted_at": submitted_at,
        "weeks": weeks,
    }


def csv_response(filename: str, rows: list[list[str]]) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    for row in rows:
        writer.writerow(row)
    payload = out.getvalue().encode("utf-8-sig")
    return Response(
        payload,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/")
def index():
    year, month = parse_ym(request.args)
    return render_template("index.html", year=year, month=month)


@app.route("/form", methods=["GET", "POST"])
def shift_form():
    year, month = parse_ym(request.values)
    staff_names = load_staff_names()

    default_name = staff_names[0] if staff_names else ""
    selected_name = (request.values.get("name") or default_name).strip()

    entry_map = {}
    comment = ""
    errors = []

    if request.method == "POST":
        if not selected_name:
            errors.append("スタッフ名を選択してください")
        entries, validation_errors = validate_entries(year, month, request.form)
        errors.extend(validation_errors)
        comment = (request.form.get("comment") or "").strip()

        if not errors:
            upsert_submission(selected_name, year, month, comment, entries)
            flash("入力内容を保存しました", "success")
            return redirect(url_for("shift_form", name=selected_name, year=year, month=month))

        entry_map = {
            row["day"]: {
                "status": row["status"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
            }
            for row in entries
        }
    elif selected_name:
        entry_map, comment = get_submission(selected_name, year, month)

    day_rows = build_form_rows(year, month, entry_map)

    return render_template(
        "form.html",
        year=year,
        month=month,
        staff_names=staff_names,
        selected_name=selected_name,
        day_rows=day_rows,
        status_choices=STATUS_CHOICES,
        comment=comment,
        errors=errors,
    )


@app.route("/admin")
def admin():
    year, month = parse_ym(request.args)
    view_data = build_admin_view_data(year, month)
    return render_template(
        "admin.html",
        year=year,
        month=month,
        status_labels=STATUS_LABELS,
        **view_data,
    )


@app.route("/admin/export/requests.csv")
def export_requests_csv():
    year, month = parse_ym(request.args)
    rows = [["name", "date", "priority"]]
    for row in fetch_month_answers(year, month):
        priority = REQUEST_PRIORITY.get(row["status"])
        if not priority:
            continue
        rows.append([row["name"], row["day"], priority])
    filename = f"requests_{year}{month:02d}.csv"
    return csv_response(filename, rows)


@app.route("/admin/export/availability.csv")
def export_availability_csv():
    year, month = parse_ym(request.args)
    rows = [["name", "date", "time_start", "time_end"]]
    for row in fetch_month_answers(year, month):
        if row["status"] != "available":
            continue
        rows.append([
            row["name"],
            row["day"],
            row["start_time"] or "",
            row["end_time"] or "",
        ])
    filename = f"availability_{year}{month:02d}.csv"
    return csv_response(filename, rows)


@app.route("/admin/export/monthly_answers.csv")
def export_monthly_answers_csv():
    year, month = parse_ym(request.args)
    rows = [["name", "date", "status", "status_label", "time_start", "time_end", "comment", "submitted_at"]]
    for row in fetch_month_answers(year, month):
        rows.append([
            row["name"],
            row["day"],
            row["status"],
            STATUS_LABELS.get(row["status"], row["status"]),
            row["start_time"] or "",
            row["end_time"] or "",
            row["comment"] or "",
            row["submitted_at"],
        ])
    filename = f"monthly_answers_{year}{month:02d}.csv"
    return csv_response(filename, rows)


@app.route("/health")
def health():
    return {"ok": True, "db": str(DB_PATH)}


def create_app() -> Flask:
    init_db()
    return app


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5050, debug=True)
