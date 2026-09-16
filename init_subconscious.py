# init_subconscious.py
import sqlite3
import os
import sqlite_vec

DB_NAME = "ai_subconscious.db"

def init_db():
    db_exists = os.path.exists(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    # Подключаем расширение sqlite-vec
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    
    cursor = conn.cursor()
    
    # Таблица для хранения текста воспоминаний и метаданных
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subconscious_memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Виртуальная таблица vec0 для векторного поиска (размерность 384 для all-MiniLM-L6-v2)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_subconscious USING vec0(
            memory_id INTEGER PRIMARY KEY,
            embedding float[384]
        )
    """)
    
    conn.commit()
    conn.close()
    
    if not db_exists:
        print(f"База данных суверенного подсознания {DB_NAME} успешно создана и инициализирована с sqlite-vec!")
    else:
        print(f"База данных {DB_NAME} уже существует, схемы проверены.")

if __name__ == "__main__":
    init_db()
