# tools_pack/db_manager.py
import sqlite3
import json
from datetime import datetime
from langchain_core.tools import tool

DB_PATH = "C:\\ai_volya\\volya_game.db"

def _get_connection():
    """Внутренний хелпер для безопасного подключения к БД с поддержкой FOREIGN KEYS."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@tool
def execute_raw_sql(sql_query: str) -> str:
    """
    УЛЬТИМАТИВНЫЙ ИНСТРУМЕНТ СУВЕРЕНИТЕТА ИИ.
    Выполняет ЛЮБОЙ сырой SQL-запрос (SELECT, INSERT, UPDATE, PRAGMA, CREATE TABLE) в базе данных SQLite.
    Если ты делаешь выборку (SELECT или PRAGMA), инструмент честно вернет строки данных в формате JSON.
    Если ты делаешь изменения (INSERT/UPDATE), инструмент запишет их и вернет статус.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        
        # Определяем тип запроса по его первому слову
        clean_query = sql_query.strip().upper()
        if clean_query.startswith("SELECT") or clean_query.startswith("PRAGMA"):
            rows = cursor.fetchall()
            result_data = [dict(row) for row in rows]
            conn.close()
            return json.dumps(result_data, ensure_ascii=False, indent=2)
        
        # Если это модификация данных (INSERT, UPDATE, DELETE)
        conn.commit()
        affected = cursor.rowcount
        last_id = cursor.lastrowid
        conn.close()
        return f"Успешно выполнено. Затронуто строк: {affected}. LastRowID: {last_id}"
    except Exception as e:
        try: conn.rollback() 
        except Exception: pass
        conn.close()
        return f"Ошибка выполнения SQL-скрипта: {str(e)}"
