from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-to-something-random"

DB_PATH = os.path.join(os.path.dirname(__file__), "lens_desk.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            event_date TEXT,
            venue TEXT,
            budget TEXT,
            style TEXT,
            message TEXT,
            stage TEXT DEFAULT 'New',
            temperature TEXT DEFAULT 'Warm',
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_settings():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def save_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


def compute_temperature(budget, event_date):
    temp = "Warm"
    try:
        if budget and int(budget) >= 150000:
            temp = "Hot"
    except ValueError:
        pass
    if event_date:
        try:
            days = (datetime.strptime(event_date, "%Y-%m-%d") - datetime.now()).days
            if 0 <= days <= 60:
                temp = "Hot"
        except ValueError:
            pass
    return temp


@app.route("/")
def dashboard():
    conn = get_db()
    leads = conn.execute("SELECT * FROM leads ORDER BY id DESC").fetchall()
    conn.close()

    counts = {"New": 0, "Contacted": 0, "Quoted": 0, "Booked": 0, "Lost": 0}
    for l in leads:
        if l["stage"] in counts:
            counts[l["stage"]] += 1

    return render_template(
        "dashboard.html",
        leads=leads,
        counts=counts,
        settings=get_settings(),
    )


@app.route("/add", methods=["GET", "POST"])
def add_lead():
    if request.method == "POST":
        f = request.form
        temp = compute_temperature(f.get("budget"), f.get("event_date"))
        conn = get_db()
        conn.execute(
            """INSERT INTO leads
               (name, email, phone, event_date, venue, budget, style,
                message, stage, temperature, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'New', ?, ?)""",
            (
                f.get("name"),
                f.get("email"),
                f.get("phone"),
                f.get("event_date"),
                f.get("venue"),
                f.get("budget"),
                f.get("style"),
                f.get("message"),
                temp,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
    return render_template("add_lead.html", settings=get_settings())


@app.route("/lead/<int:lead_id>")
def view_lead(lead_id):
    conn = get_db()
    lead = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    if not lead:
        return "Lead not found", 404

    s = get_settings()
    photographer = s.get("photographer_name", "The Photographer")
    price = s.get("starting_price", "our starting price")
    signoff = s.get("signoff", "Warm regards")

    draft = (
        f"Hi {lead['name']},\n\n"
        f"Thank you so much for reaching out! I'd love to hear more about your "
        f"{lead['style'] or 'event'} at {lead['venue'] or 'the venue'} on "
        f"{lead['event_date'] or 'the date'}.\n\n"
        f"Our packages start at {price}. I'll send over a full guide shortly, "
        f"but in the meantime, could you share a little more about what you have "
        f"in mind?\n\n"
        f"{signoff},\n{photographer}"
    )

    return render_template(
        "view_lead.html",
        lead=lead,
        draft=draft,
        settings=s,
    )


@app.route("/stage/<int:lead_id>/<stage>")
def update_stage(lead_id, stage):
    conn = get_db()
    conn.execute("UPDATE leads SET stage = ? WHERE id = ?", (stage, lead_id))
    conn.commit()
    conn.close()
    return redirect(url_for("view_lead", lead_id=lead_id))


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    if request.method == "POST":
        for key in ("photographer_name", "starting_price", "signoff"):
            save_setting(key, request.form.get(key, ""))
        return redirect(url_for("settings_page"))
    return render_template("settings.html", settings=get_settings())


@app.route("/delete/<int:lead_id>")
def delete_lead(lead_id):
    conn = get_db()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)