import os
import sqlite3
import datetime

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

DB_PATH = os.environ.get("DB_PATH", "guestbook.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/messages", methods=["GET"])
def list_messages():
    conn = get_db()
    rows = conn.execute(
        "SELECT name, message, created_at FROM messages ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/messages", methods=["POST"])
def add_message():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:50]
    message = (data.get("message") or "").strip()[:280]

    if not name or not message:
        return jsonify({"error": "name and message are required"}), 400

    created_at = datetime.datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute(
        "INSERT INTO messages (name, message, created_at) VALUES (?, ?, ?)",
        (name, message, created_at),
    )
    conn.commit()
    conn.close()

    return jsonify({"name": name, "message": message, "created_at": created_at}), 201


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
