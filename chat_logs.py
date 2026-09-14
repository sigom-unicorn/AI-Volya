# C:\ai_volya\chat_logs.py
import sqlite3
from datetime import datetime

DB_PATH = "C:\\ai_volya\\volya_game.db"

def _get_connection():
    """Внутренний хелпер для безопасного подключения к БД с поддержкой FOREIGN KEYS."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_visible_history_from_db(thread_id: str, limit: int = 15):
    """Вытаскивает из SQLite фиксированное окно последних сообщений сессии."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM (
            SELECT id, role, content FROM chat_logs 
            WHERE thread_id = ? ORDER BY id DESC LIMIT ?
        ) ORDER BY id ASC
    """, (thread_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows

def save_message_to_db(thread_id: str, role: str, content: str):
    """Сохраняет реплику диалога в SQLite с точным локальным временем и датой сервера (datetime.now())."""
    conn = _get_connection()
    cursor = conn.cursor()
    # Используем datetime.now() для записи точных даты и времени сервера
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO chat_logs (thread_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (thread_id, role, content, local_time)
    )
    conn.commit()
    conn.close()
