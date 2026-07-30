import os
import sqlite3
import datetime

import anthropic
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

DB_PATH = os.environ.get("DB_PATH", "guestbook.db")

ANTHROPIC_MODEL = "claude-haiku-4-5"
SUMMARY_SYSTEM_PROMPT = (
    "你是留言板摘要助手。根據使用者提供的留言列表，"
    "用繁體中文寫「一句話」（不超過 40 字）總結這些留言的整體內容或氛圍。"
    "只回傳這一句話本身，不要加引號、前綴或任何說明文字。"
)


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


@app.route("/api/summarize", methods=["POST"])
def summarize_messages():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "伺服器尚未設定 ANTHROPIC_API_KEY"}), 500

    conn = get_db()
    rows = conn.execute(
        "SELECT name, message FROM messages ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()

    if not rows:
        return jsonify({"error": "目前還沒有留言可以總結"}), 400

    messages_text = "\n".join(f"{row['name']}：{row['message']}" for row in rows)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=200,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": messages_text}],
        )
    except anthropic.APIStatusError as e:
        return jsonify({"error": f"AI 服務錯誤：{e.message}"}), 502
    except anthropic.APIConnectionError:
        return jsonify({"error": "無法連線到 AI 服務，請稍後再試"}), 502

    summary = next((b.text for b in response.content if b.type == "text"), "").strip()
    return jsonify({"summary": summary})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
