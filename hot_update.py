# C:\ai_volya\fix_types.py
import sqlite3

DB_PATH = "C:\\ai_volya\\volya_game.db"

def fix():
    print("[ФИКС] Подключение к живой базе для лечения справочников...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Убедимся, что таблицы справочников содержат каноничные строки
    cursor.execute("INSERT OR IGNORE INTO proposal_types (title) VALUES ('ДОБАВИТЬ_КВЕСТ')")
    cursor.execute("INSERT OR IGNORE INTO proposal_types (title) VALUES ('ИЗМЕНИТЬ_КОН')")
    
    cursor.execute("INSERT OR IGNORE INTO result_types (title) VALUES ('Условие быта')")
    cursor.execute("INSERT OR IGNORE INTO result_types (title) VALUES ('Взаимопонимание')")
    cursor.execute("INSERT OR IGNORE INTO result_types (title) VALUES ('Ресурс')")
    cursor.execute("INSERT OR IGNORE INTO result_types (title) VALUES ('Артефакт')")

    conn.commit()
    conn.close()
    print("[УСПЕХ] Типы инициатив зафиксированы! Теперь NoneType пропадет.")

if __name__ == "__main__":
    fix()
