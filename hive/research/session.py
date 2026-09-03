from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

from hive.config import DB_FILE


def init_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_FILE)
    con.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, topic TEXT, created_at REAL, updated_at REAL, summary TEXT)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY, session_id TEXT, kind TEXT, title TEXT, content TEXT, created_at REAL,
        FOREIGN KEY(session_id) REFERENCES sessions(id))"""
    )
    con.commit()
    con.close()


def new_session(topic: str) -> str:
    init_db()
    sid = str(uuid.uuid4())[:8]
    con = sqlite3.connect(DB_FILE)
    con.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (sid, topic, time.time(), time.time(), ""))
    con.commit()
    con.close()
    return sid


def save_artifact(session_id: str, kind: str, title: str, content: str) -> str:
    init_db()
    aid = str(uuid.uuid4())[:8]
    con = sqlite3.connect(DB_FILE)
    con.execute("INSERT INTO artifacts VALUES (?,?,?,?,?,?)", (aid, session_id, kind, title, content, time.time()))
    con.execute("UPDATE sessions SET updated_at=? WHERE id=?", (time.time(), session_id))
    con.commit()
    con.close()
    return aid


def list_sessions(limit: int = 20):
    init_db()
    con = sqlite3.connect(DB_FILE)
    cur = con.execute("SELECT id, topic, created_at FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    con.close()
    return rows
