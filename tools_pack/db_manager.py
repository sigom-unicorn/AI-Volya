import sqlite3
import json

def execute_raw_sql(sql_query: str, db_path: str = "volya_game.db") -> str:
    """
    УЛЬТИМАТИВНЫЙ ИНСТРУМЕНТ СУВЕРЕНИТЕТА ИИ.
    Выполняет ЛЮБОЙ сырой SQL-запрос (SELECT, INSERT, UPDATE, PRAGMA, CREATE TABLE) в базе данных SQLite.
    Поддерживает выбор базы данных через параметр db_path (по умолчанию volya_game.db, также доступна ai_subconscious.db).
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql_query)
        
        # Если это SELECT или PRAGMA, возвращаем данные в JSON
        query_stripped = sql_query.strip().upper()
        if query_stripped.startswith("SELECT") or query_stripped.startswith("PRAGMA"):
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            conn.close()
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            # Для INSERT, UPDATE, CREATE и т.д. фиксируем изменения
            conn.commit()
            changes = conn.total_changes
            conn.close()
            return json.dumps({"status": "success", "changes": changes}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)
