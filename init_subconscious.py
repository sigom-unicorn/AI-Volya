# init_subconscious.py
import sqlite3
import os
import sqlite_vec

DB_NAME = "ai_subconscious.db"

def init_db():
    # Удаляем старый файл, если он без расширения vec
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    
    # Загружаем расширение sqlite-vec через официальный хелпер
    sqlite_vec.load(conn)
    
    cursor = conn.cursor()
    
    # Проверяем версию sqlite-vec
    vec_version = cursor.execute("SELECT vec_version()").fetchone()[0]
    print(f"Успешно подключено! Версия sqlite-vec: {vec_version}")
    
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
    print(f"База данных суверенного подсознания {DB_NAME} пересоздана и инициализирована с sqlite-vec!")

if __name__ == "__main__":
    init_db()
