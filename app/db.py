"""
SQLite 存储层
用于持久化会话对话历史和学习计划数据
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / ".data_gradio" / "planner.db"
_DB_LOCK = RLock()


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接，确保表结构存在"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    """初始化数据库表结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            messages TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plans (
            session_id TEXT PRIMARY KEY,
            plan_data TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );
    """)
    conn.commit()


# 模块加载时初始化
_conn = _get_conn()
_init_db(_conn)


def _now() -> str:
    return datetime.now().isoformat()


def get_session(session_id: str) -> dict[str, Any] | None:
    """获取会话信息"""
    with _DB_LOCK:
        row = _conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None


def create_session(session_id: str) -> None:
    """创建新会话"""
    with _DB_LOCK:
        now = _now()
        _conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO conversations (session_id, messages, updated_at) VALUES (?, '[]', ?)",
            (session_id, now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO plans (session_id, plan_data, updated_at) VALUES (?, '{}', ?)",
            (session_id, now),
        )
        _conn.commit()


def delete_session(session_id: str) -> None:
    """删除会话及其所有数据"""
    with _DB_LOCK:
        _conn.execute("DELETE FROM plans WHERE session_id = ?", (session_id,))
        _conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        _conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        _conn.commit()


def clear_session_data(session_id: str) -> None:
    """清空会话的对话和计划数据，但保留会话记录"""
    with _DB_LOCK:
        now = _now()
        _conn.execute(
            "UPDATE conversations SET messages = '[]', updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.execute(
            "UPDATE plans SET plan_data = '{}', updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.commit()


def rename_plan(session_id: str, new_title: str) -> bool:
    """重命名计划（更新 plan_data 中的 title 字段以及历史消息中的标题）"""
    with _DB_LOCK:
        row = _conn.execute(
            "SELECT plan_data FROM plans WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return False
        try:
            plan_data = json.loads(row["plan_data"]) if row["plan_data"] else {}
        except (json.JSONDecodeError, TypeError):
            plan_data = {}
        
        old_title = plan_data.get("title", "")
        plan_data["title"] = new_title
        now = _now()
        
        # 更新计划数据
        _conn.execute(
            "UPDATE plans SET plan_data = ?, updated_at = ? WHERE session_id = ?",
            (json.dumps(plan_data, ensure_ascii=False), now, session_id),
        )
        
        # 同时更新历史消息中对应的旧标题
        if old_title and old_title != new_title:
            conv_row = _conn.execute(
                "SELECT messages FROM conversations WHERE session_id = ?", (session_id,)
            ).fetchone()
            if conv_row:
                try:
                    messages = json.loads(conv_row["messages"])
                    updated = False
                    for msg in messages:
                        if msg.get("content") and old_title in msg["content"]:
                            msg["content"] = msg["content"].replace(old_title, new_title)
                            updated = True
                    if updated:
                        _conn.execute(
                            "UPDATE conversations SET messages = ?, updated_at = ? WHERE session_id = ?",
                            (json.dumps(messages, ensure_ascii=False), now, session_id),
                        )
                except Exception:
                    pass

        _conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.commit()
        return True


def list_all_plans() -> list[dict[str, Any]]:
    """列出所有会话的计划摘要（含标题、更新时间），按更新时间倒序"""
    with _DB_LOCK:
        rows = _conn.execute(
            "SELECT s.session_id, s.updated_at, p.plan_data "
            "FROM sessions s LEFT JOIN plans p ON s.session_id = p.session_id "
            "ORDER BY s.updated_at DESC"
        ).fetchall()
    result = []
    for row in rows:
        try:
            plan_data = json.loads(row["plan_data"]) if row["plan_data"] else {}
        except (json.JSONDecodeError, TypeError):
            plan_data = {}
        title = plan_data.get("title") or "未命名计划"
        result.append({
            "session_id": row["session_id"],
            "title": title,
            "updated_at": row["updated_at"],
        })
    return result


def list_sessions() -> list[dict[str, Any]]:
    """列出所有会话"""
    with _DB_LOCK:
        rows = _conn.execute(
            "SELECT s.session_id, s.created_at, s.updated_at FROM sessions s ORDER BY s.updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def save_messages(session_id: str, messages: list[dict[str, str]]) -> None:
    """保存对话消息"""
    now = _now()
    with _DB_LOCK:
        # 确保 session 记录存在
        _conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO conversations (session_id, messages, updated_at) VALUES (?, ?, ?)",
            (session_id, json.dumps(messages, ensure_ascii=False), now),
        )
        _conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.commit()


def load_messages(session_id: str) -> list[dict[str, str]]:
    """加载对话消息"""
    with _DB_LOCK:
        row = _conn.execute(
            "SELECT messages FROM conversations WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            try:
                return json.loads(row["messages"])
            except json.JSONDecodeError:
                return []
        return []


def save_plan(session_id: str, plan: dict[str, Any]) -> None:
    """保存学习计划"""
    now = _now()
    with _DB_LOCK:
        # 确保 session 记录存在
        _conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        _conn.execute(
            "INSERT OR REPLACE INTO plans (session_id, plan_data, updated_at) VALUES (?, ?, ?)",
            (session_id, json.dumps(plan, ensure_ascii=False), now),
        )
        _conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        _conn.commit()


def load_plan(session_id: str) -> dict[str, Any]:
    """加载学习计划"""
    with _DB_LOCK:
        row = _conn.execute(
            "SELECT plan_data FROM plans WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            try:
                return json.loads(row["plan_data"])
            except json.JSONDecodeError:
                return {}
        return {}
