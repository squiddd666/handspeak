"""HandSpeak Web application server (standard-library only)."""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "handspeak.db"
MAX_BODY = 1_000_000

GESTURES = [
    ("A", "A", "Closed fist, thumb rests beside the fingers"),
    ("B", "B", "Four fingers up together, thumb across palm"),
    ("I", "I", "Pinky raised, other fingers closed"),
    ("L", "L", "Index and thumb form an L shape"),
    ("V", "V", "Index and middle fingers spread"),
    ("W", "W", "Index, middle, and ring fingers raised"),
    ("Y", "Y", "Thumb and pinky extended"),
    ("5", "Five", "All five fingers extended and spread"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_database() -> None:
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS gestures (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                message TEXT NOT NULL,
                character_count INTEGER NOT NULL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                latency_ms REAL NOT NULL CHECK(latency_ms >= 0),
                correct INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                respondent_type TEXT NOT NULL,
                accuracy INTEGER NOT NULL CHECK(accuracy BETWEEN 1 AND 5),
                usability INTEGER NOT NULL CHECK(usability BETWEEN 1 AND 5),
                performance INTEGER NOT NULL CHECK(performance BETWEEN 1 AND 5),
                comments TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
        """)
        db.executemany(
            "INSERT OR IGNORE INTO gestures(symbol,name,description) VALUES(?,?,?)",
            GESTURES,
        )


class APIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class HandSpeakHandler(SimpleHTTPRequestHandler):
    server_version = "HandSpeak/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(self), microphone=()")
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        else:
            self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/health":
                return self.json_response({"status": "ok", "time": utc_now()})
            if parsed.path == "/api/gestures":
                with connect() as db:
                    rows = db.execute("SELECT symbol,name,description FROM gestures WHERE enabled=1 ORDER BY rowid").fetchall()
                return self.json_response({"gestures": [dict(r) for r in rows]})
            if parsed.path == "/api/sessions":
                limit = min(max(int(parse_qs(parsed.query).get("limit", [20])[0]), 1), 100)
                with connect() as db:
                    rows = db.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
                return self.json_response({"sessions": [dict(r) for r in rows]})
            if parsed.path == "/api/metrics":
                return self.json_response(self.metrics())
            if parsed.path == "/api/export/sessions.csv":
                return self.export_sessions()
            if parsed.path.startswith("/api/"):
                raise APIError(404, "API endpoint not found")
            return super().do_GET()
        except (APIError, ValueError) as error:
            status = error.status if isinstance(error, APIError) else 400
            message = error.message if isinstance(error, APIError) else "Invalid request"
            self.json_response({"error": message}, status)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            data = self.read_json()
            if parsed.path == "/api/sessions":
                return self.create_session(data)
            if parsed.path == "/api/evaluations":
                return self.create_evaluation(data)
            raise APIError(404, "API endpoint not found")
        except APIError as error:
            self.json_response({"error": error.message}, error.status)
        except sqlite3.Error:
            self.json_response({"error": "Database operation failed"}, 500)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise APIError(400, "Invalid content length") from exc
        if length <= 0 or length > MAX_BODY:
            raise APIError(413 if length > MAX_BODY else 400, "Invalid request body")
        try:
            value = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIError(400, "Request body must be valid JSON") from exc
        if not isinstance(value, dict):
            raise APIError(400, "JSON body must be an object")
        return value

    def create_session(self, data: dict) -> None:
        message = str(data.get("message", "")).strip()
        if not message or len(message) > 1000:
            raise APIError(422, "Message must contain 1 to 1000 characters")
        detections = data.get("detections", [])
        if not isinstance(detections, list) or len(detections) > 1000:
            raise APIError(422, "Detections must be a list with at most 1000 items")
        session_id = uuid.uuid4().hex
        created = utc_now()
        duration = max(0, min(int(data.get("durationMs", 0)), 86_400_000))
        clean = []
        allowed = {item[0] for item in GESTURES}
        for item in detections:
            try:
                symbol = str(item["symbol"])
                confidence = float(item["confidence"])
                latency = float(item.get("latencyMs", 0))
            except (KeyError, TypeError, ValueError) as exc:
                raise APIError(422, "Each detection requires a valid symbol and confidence") from exc
            if symbol not in allowed or not 0 <= confidence <= 1 or not 0 <= latency <= 60_000:
                raise APIError(422, "Detection contains values outside the accepted range")
            clean.append((session_id, symbol, confidence, latency, created))
        with connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (session_id, message, len(message), duration, created))
            db.executemany("INSERT INTO detections(session_id,symbol,confidence,latency_ms,created_at) VALUES(?,?,?,?,?)", clean)
        self.json_response({"id": session_id, "createdAt": created}, HTTPStatus.CREATED)

    def create_evaluation(self, data: dict) -> None:
        respondent = str(data.get("respondentType", "")).strip()
        if respondent not in {"Student", "Educator", "Deaf/Hard-of-Hearing", "Hearing", "Other"}:
            raise APIError(422, "Select a valid respondent type")
        try:
            ratings = [int(data[key]) for key in ("accuracy", "usability", "performance")]
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(422, "All three ratings are required") from exc
        if any(value < 1 or value > 5 for value in ratings):
            raise APIError(422, "Ratings must be from 1 to 5")
        comments = str(data.get("comments", "")).strip()[:2000]
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO evaluations(respondent_type,accuracy,usability,performance,comments,created_at) VALUES(?,?,?,?,?,?)",
                (respondent, *ratings, comments, utc_now()),
            )
        self.json_response({"id": cursor.lastrowid}, HTTPStatus.CREATED)

    def metrics(self) -> dict:
        with connect() as db:
            totals = db.execute("SELECT COUNT(*) sessions, COALESCE(SUM(character_count),0) characters FROM sessions").fetchone()
            detection = db.execute("SELECT COUNT(*) total, COALESCE(AVG(confidence),0) confidence, COALESCE(AVG(latency_ms),0) latency FROM detections").fetchone()
            evaluation = db.execute("SELECT COUNT(*) total, COALESCE(AVG(accuracy),0) accuracy, COALESCE(AVG(usability),0) usability, COALESCE(AVG(performance),0) performance FROM evaluations").fetchone()
        return {
            "sessions": totals["sessions"], "characters": totals["characters"],
            "detections": detection["total"], "averageConfidence": round(detection["confidence"], 3),
            "averageLatencyMs": round(detection["latency"], 1), "evaluations": evaluation["total"],
            "ratings": {key: round(evaluation[key], 2) for key in ("accuracy", "usability", "performance")},
        }

    def export_sessions(self) -> None:
        with connect() as db:
            rows = db.execute("SELECT id,message,character_count,duration_ms,created_at FROM sessions ORDER BY created_at DESC").fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["session_id", "message", "character_count", "duration_ms", "created_at"])
        writer.writerows(tuple(row) for row in rows)
        body = output.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=handspeak-sessions.csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    initialize_database()
    server = ThreadingHTTPServer((host, port), HandSpeakHandler)
    print(f"HandSpeak Web is running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
