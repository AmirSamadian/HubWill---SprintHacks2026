"""Local scheduling state. SQLite here stores job history, not business data."""

import sqlite3
from contextlib import closing
from pathlib import Path


class DeliveryHistory:
    def __init__(self, directory: Path):
        self.path = directory / "email-schedule.sqlite3"

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE IF NOT EXISTS deliveries ("
            "report_month TEXT PRIMARY KEY, status TEXT NOT NULL, detail TEXT NOT NULL)"
        )
        connection.commit()
        return connection

    def claim(self, month: str) -> bool:
        with closing(self.connect()) as connection, connection:
            # A unique month and a write transaction prevent competing schedulers
            # from both claiming the same month.
            connection.execute("BEGIN IMMEDIATE")
            inserted = connection.execute(
                "INSERT OR IGNORE INTO deliveries VALUES (?, 'in_progress', ?)",
                (month, "Scheduled capture started."),
            )
            if inserted.rowcount:
                return True
            retry = connection.execute(
                "UPDATE deliveries SET status='in_progress', detail=? "
                "WHERE report_month=? AND status='retryable'",
                ("Retrying after connection was refused.", month),
            )
            return bool(retry.rowcount)

    def finish(self, month: str, status: str, detail: str) -> None:
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "UPDATE deliveries SET status=?, detail=? WHERE report_month=?",
                (status, detail, month),
            )

    def entries(self) -> list[dict[str, str]]:
        with closing(self.connect()) as connection:
            return [dict(row) for row in connection.execute(
                "SELECT report_month, status, detail FROM deliveries ORDER BY report_month DESC"
            )]

    def get(self, month: str) -> dict[str, str] | None:
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT * FROM deliveries WHERE report_month=?", (month,)).fetchone()
            return dict(row) if row else None
