"""
utils/database.py
=================
SQLite storage for quiz results and citizen feedback.
"""

import os
import sqlite3
from typing import Optional

import streamlit as st


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "feedback.db")


def _get_connection() -> sqlite3.Connection:
    """Create a SQLite connection with dictionary-like row access."""
    os.makedirs(DATA_DIR, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def _sanitize(value: Optional[str], max_length: int) -> str:
    """Remove NULL characters and limit text length."""
    if value is None:
        return ""

    value = str(value).replace("\x00", "").strip()

    return value[:max_length]


def init_db() -> None:
    """Create the application tables if they do not already exist."""
    with _get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                helpful TEXT NOT NULL,
                topic_of_interest TEXT NOT NULL,
                comment TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL
            )
            """
        )

        connection.commit()


def save_feedback(
    helpful: str,
    topic_of_interest: str,
    comment: str = "",
) -> bool:
    """
    Save one citizen feedback submission.

    Returns True when the record is stored successfully.
    """
    helpful = _sanitize(helpful, 50)
    topic_of_interest = _sanitize(topic_of_interest, 100)
    comment = _sanitize(comment, 1000)

    try:
        init_db()

        with _get_connection() as connection:
            connection.execute(
                """
                INSERT INTO feedback (
                    helpful,
                    topic_of_interest,
                    comment
                )
                VALUES (?, ?, ?)
                """,
                (
                    helpful,
                    topic_of_interest,
                    comment,
                ),
            )

            connection.commit()

        return True

    except sqlite3.Error:
        return False


def save_quiz_result(score: int, total: int) -> bool:
    """
    Save one quiz result.

    Returns True when the result is stored successfully.
    """
    try:
        score = int(score)
        total = int(total)

        if score < 0 or total < 0 or score > total:
            return False

        init_db()

        with _get_connection() as connection:
            connection.execute(
                """
                INSERT INTO quiz_results (
                    score,
                    total
                )
                VALUES (?, ?)
                """,
                (
                    score,
                    total,
                ),
            )

            connection.commit()

        return True

    except (ValueError, TypeError, sqlite3.Error):
        return False


@st.cache_data(ttl=30)
def get_feedback_summary() -> dict:
    """
    Return a small aggregate summary of submitted feedback.

    The result is cached for 30 seconds to avoid unnecessary database reads.
    """
    try:
        init_db()

        with _get_connection() as connection:
            total_feedback = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM feedback
                """
            ).fetchone()["count"]

            helpful_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM feedback
                WHERE helpful = ?
                """,
                ("نعم",),
            ).fetchone()["count"]

            topic_rows = connection.execute(
                """
                SELECT topic_of_interest, COUNT(*) AS count
                FROM feedback
                GROUP BY topic_of_interest
                ORDER BY count DESC
                """
            ).fetchall()

        return {
            "total_feedback": total_feedback,
            "helpful_count": helpful_count,
            "topics": [
                {
                    "topic": row["topic_of_interest"],
                    "count": row["count"],
                }
                for row in topic_rows
            ],
        }

    except sqlite3.Error:
        return {
            "total_feedback": 0,
            "helpful_count": 0,
            "topics": [],
        }


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")