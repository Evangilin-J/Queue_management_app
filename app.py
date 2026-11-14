import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = "rugas_queue_manager_secret_key"
DB_NAME = "queue_system.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS managers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER NOT NULL,
            token_number TEXT NOT NULL,
            person_name TEXT NOT NULL,
            position INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            created_at TEXT NOT NULL,
            served_at TEXT,
            FOREIGN KEY (queue_id) REFERENCES queues (id) ON DELETE CASCADE
        )
    """)
    # Default manager account
    cur.execute("SELECT * FROM managers WHERE username = ?", ("admin",))
    if not cur.fetchone():
        cur.execute("INSERT INTO managers (username, password) VALUES (?, ?)", ("admin", "admin123"))

    # Seed sample queue & data if empty so analytics look great right away
    cur.execute("SELECT COUNT(*) as cnt FROM queues")
    if cur.fetchone()["cnt"] == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO queues (name, created_at) VALUES (?, ?)", ("General Support Desk", now))
        qid = cur.lastrowid
        sample_tokens = [
            (qid, "T-101", "Arun Kumar", 1, "served", "2026-11-14 09:00:00", "2026-11-14 09:08:00"),
            (qid, "T-102", "Priya S", 2, "served", "2026-11-14 09:05:00", "2026-11-14 09:17:00"),
            (qid, "T-103", "Karthik R", 3, "served", "2026-11-14 09:15:00", "2026-11-14 09:24:00"),
            (qid, "T-104", "Divya M", 1, "waiting", "2026-11-14 09:30:00", None),
            (qid, "T-105", "Santhosh V", 2, "waiting", "2026-11-14 09:35:00", None),
        ]
        cur.executemany("""
            INSERT INTO tokens (queue_id, token_number, person_name, position, status, created_at, served_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_tokens)
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "manager_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db()
        user = conn.execute("SELECT * FROM managers WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()
        if user:
            session["manager_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        error = "Invalid username or password. Try admin / admin123"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username"))

# --- REST API ENDPOINTS ---

@app.route("/api/queues", methods=["GET"])
@login_required
def get_queues():
    conn = get_db()
    queues = conn.execute("SELECT * FROM queues ORDER BY id ASC").fetchall()
    result = []
    for q in queues:
        waiting_count = conn.execute(
            "SELECT COUNT(*) as c FROM tokens WHERE queue_id = ? AND status = 'waiting'", (q["id"],)
        ).fetchone()["c"]
        result.append({
            "id": q["id"],
            "name": q["name"],
            "created_at": q["created_at"],
            "waiting_count": waiting_count
        })
    conn.close()
    return jsonify(result)

@app.route("/api/queues", methods=["POST"])
@login_required
def create_queue():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Queue name is required"}), 400
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("INSERT INTO queues (name, created_at) VALUES (?, ?)", (name, now))
    conn.commit()
    qid = cur.lastrowid
    conn.close()
    return jsonify({"id": qid, "name": name, "created_at": now, "waiting_count": 0}), 201

@app.route("/api/queues/<int:queue_id>/tokens", methods=["GET"])
@login_required
def get_tokens(queue_id):
    conn = get_db()
    tokens = conn.execute(
        "SELECT * FROM tokens WHERE queue_id = ? AND status = 'waiting' ORDER BY position ASC",
        (queue_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tokens])

@app.route("/api/queues/<int:queue_id>/tokens", methods=["POST"])
@login_required
def add_token(queue_id):
    data = request.get_json()
    person_name = (data.get("person_name") or "").strip()
    if not person_name:
        return jsonify({"error": "Person name is required"}), 400
    conn = get_db()
    total_tokens = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE queue_id = ?", (queue_id,)).fetchone()["c"]
    token_number = f"T-{101 + total_tokens}"
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), 0) as mp FROM tokens WHERE queue_id = ? AND status = 'waiting'",
        (queue_id,)
    ).fetchone()["mp"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO tokens (queue_id, token_number, person_name, position, status, created_at) VALUES (?, ?, ?, ?, 'waiting', ?)",
        (queue_id, token_number, person_name, max_pos + 1, now)
    )
    conn.commit()
    tid = cur.lastrowid
    conn.close()
    return jsonify({"id": tid, "token_number": token_number, "person_name": person_name}), 201

@app.route("/api/tokens/<int:token_id>/move", methods=["POST"])
@login_required
def move_token(token_id):
    data = request.get_json()
    direction = data.get("direction") # 'up' or 'down'
    conn = get_db()
    token = conn.execute("SELECT * FROM tokens WHERE id = ? AND status = 'waiting'", (token_id,)).fetchone()
    if not token:
        conn.close()
        return jsonify({"error": "Token not found"}), 404

    queue_id = token["queue_id"]
    pos = token["position"]

    if direction == "up":
        neighbor = conn.execute(
            "SELECT * FROM tokens WHERE queue_id = ? AND status = 'waiting' AND position < ? ORDER BY position DESC LIMIT 1",
            (queue_id, pos)
        ).fetchone()
    elif direction == "down":
        neighbor = conn.execute(
            "SELECT * FROM tokens WHERE queue_id = ? AND status = 'waiting' AND position > ? ORDER BY position ASC LIMIT 1",
            (queue_id, pos)
        ).fetchone()
    else:
        conn.close()
        return jsonify({"error": "Invalid direction"}), 400

    if neighbor:
        conn.execute("UPDATE tokens SET position = ? WHERE id = ?", (neighbor["position"], token["id"]))
        conn.execute("UPDATE tokens SET position = ? WHERE id = ?", (pos, neighbor["id"]))
        conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/queues/<int:queue_id>/assign-top", methods=["POST"])
@login_required
def assign_top_token(queue_id):
    conn = get_db()
    top_token = conn.execute(
        "SELECT * FROM tokens WHERE queue_id = ? AND status = 'waiting' ORDER BY position ASC LIMIT 1",
        (queue_id,)
    ).fetchone()
    if not top_token:
        conn.close()
        return jsonify({"error": "No waiting tokens in this queue"}), 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE tokens SET status = 'served', served_at = ? WHERE id = ?", (now, top_token["id"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "assigned", "token": dict(top_token)})

@app.route("/api/tokens/<int:token_id>/cancel", methods=["POST"])
@login_required
def cancel_token(token_id):
    conn = get_db()
    token = conn.execute("SELECT * FROM tokens WHERE id = ? AND status = 'waiting'", (token_id,)).fetchone()
    if not token:
        conn.close()
        return jsonify({"error": "Token not found"}), 404
    conn.execute("UPDATE tokens SET status = 'cancelled' WHERE id = ?", (token_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "cancelled"})

@app.route("/api/analytics", methods=["GET"])
@login_required
def analytics():
    conn = get_db()
    queues = conn.execute("SELECT * FROM queues").fetchall()
    served = conn.execute("SELECT * FROM tokens WHERE status = 'served' AND served_at IS NOT NULL").fetchall()
    waiting_total = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE status = 'waiting'").fetchone()["c"]
    cancelled_total = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE status = 'cancelled'").fetchone()["c"]

    wait_minutes = []
    for t in served:
        try:
            c_dt = datetime.strptime(t["created_at"], "%Y-%m-%d %H:%M:%S")
            s_dt = datetime.strptime(t["served_at"], "%Y-%m-%d %H:%M:%S")
            diff = max(1.0, round((s_dt - c_dt).total_seconds() / 60.0, 1))
            wait_minutes.append(diff)
        except Exception:
            pass

    avg_wait = round(sum(wait_minutes) / len(wait_minutes), 1) if wait_minutes else 0.0

    queue_breakdown = []
    for q in queues:
        w = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE queue_id = ? AND status = 'waiting'", (q["id"],)).fetchone()["c"]
        s = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE queue_id = ? AND status = 'served'", (q["id"],)).fetchone()["c"]
        c = conn.execute("SELECT COUNT(*) as c FROM tokens WHERE queue_id = ? AND status = 'cancelled'", (q["id"],)).fetchone()["c"]
        queue_breakdown.append({
            "queue_name": q["name"],
            "waiting": w,
            "served": s,
            "cancelled": c
        })

    recent_served = [
        {"token": t["token_number"], "name": t["person_name"], "wait_mins": wait_minutes[i]}
        for i, t in enumerate(served[-8:])
    ] if len(served) == len(wait_minutes) else []

    conn.close()
    return jsonify({
        "total_queues": len(queues),
        "waiting_total": waiting_total,
        "served_total": len(served),
        "cancelled_total": cancelled_total,
        "avg_wait_mins": avg_wait,
        "queue_breakdown": queue_breakdown,
        "recent_served": recent_served
    })

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
