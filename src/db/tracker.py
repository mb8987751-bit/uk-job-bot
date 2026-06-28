import sqlite3
import csv
import os
from datetime import datetime, date
from typing import Optional

from src.utils.logger import logger

DB_PATH = "data/applications.db"


class ApplicationTracker:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                company TEXT,
                platform TEXT,
                location TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'applied',
                notes TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_counts (
                date TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        try:
            conn.execute("ALTER TABLE applications ADD COLUMN notes TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()
        logger.info("Database initialized")

    def is_applied(self, url: str) -> bool:
        conn = self._get_conn()
        row = conn.execute("SELECT 1 FROM applications WHERE url = ?", (url,)).fetchone()
        conn.close()
        return row is not None

    def update_status(self, url: str, new_status: str):
        conn = self._get_conn()
        conn.execute("UPDATE applications SET status = ? WHERE url = ?", (new_status, url))
        conn.commit()
        conn.close()

    def update_notes(self, url: str, notes: str):
        conn = self._get_conn()
        conn.execute("UPDATE applications SET notes = ? WHERE url = ?", (notes, url))
        conn.commit()
        conn.close()

    def get_status(self, url: str) -> str | None:
        conn = self._get_conn()
        row = conn.execute("SELECT status FROM applications WHERE url = ?", (url,)).fetchone()
        conn.close()
        return row["status"] if row else None

    def record_application(self, url: str, title: str, company: str, platform: str, location: str, status: str = "tracked"):
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO applications (url, title, company, platform, location, status) VALUES (?, ?, ?, ?, ?, ?)",
                (url, title, company, platform, location, status),
            )
            today = date.today().isoformat()
            conn.execute(
                "INSERT INTO daily_counts (date, count) VALUES (?, 1) "
                "ON CONFLICT(date) DO UPDATE SET count = count + 1",
                (today,),
            )
            conn.commit()
            logger.info(f"Recorded: {title} at {company}")
        except Exception as e:
            logger.error(f"Failed to record application: {e}")
        finally:
            conn.close()

    def get_today_count(self) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT count FROM daily_counts WHERE date = ?", (date.today().isoformat(),)
        ).fetchone()
        conn.close()
        return row["count"] if row else 0

    def export_csv(self, path: Optional[str] = None):
        if path is None:
            path = f"data/exports/applications_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM applications ORDER BY applied_at DESC").fetchall()
        conn.close()
        if rows:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(rows[0].keys())
                for row in rows:
                    writer.writerow(row)
            logger.info(f"Exported {len(rows)} records to {path}")
        return path
