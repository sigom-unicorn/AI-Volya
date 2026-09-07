# C:\ai_volya\rebuild_db.py
import os
import sqlite3
import db_init
import db_seed

DB_PATH = "C:\\ai_volya\\volya_game.db"

def rebuild():
    print("=== ЗАПУСК ТОТАЛЬНОЙ ПЕРЕСБОРКИ РАНТАЙМА 'ВОЛЯ' ===")
    
    # 1. Сносим старую базу, если она существует
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[1/4] Старая база данных volya_game.db успешно удалена.")
        except Exception as e:
            print(f"[ОШИБКА] Не удалось удалить файл базы. Возможно, запущен процесс volya_app.py. Закройте его. Ошибка: {e}")
            return
    else:
        print("[1/4] Старая база данных не обнаружена. Создаем с чистого листа.")

    # 2. Запускаем инициализацию структуры (db_init.py)
    try:
        print("[2/4] Запуск db_init.py...")
        db_init.init_db()
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ]: {e}")
        return

    # 3. Запускаем наполнение 33 шаблонами и вехами Вече (db_seed.py)
    try:
        print("[3/4] Запуск db_seed.py...")
        db_seed.seed_data()
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА СИДЕРА]: {e}")
        return

    # 4. Финальный аудит: проверяем, как Эйра будет считывать свои Лады
    print("[4/4] Запуск экспресс-аудита Уклада в новой базе...")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Проверяем Лад Эйры
        cursor.execute("SELECT condition FROM kon_uklad WHERE title = 'Лад Эйры'")
        base = cursor.fetchone()
        
        # Проверяем Лад Эйры // Холст
        cursor.execute("SELECT condition FROM kon_uklad WHERE title = 'Лад Эйры // Холст'")
        canvas = cursor.fetchone()
        
        # Проверяем квесты
        cursor.execute("SELECT COUNT(*) as cnt FROM quests")
        quests_cnt = cursor.fetchone()["cnt"]
        
        conn.close()
        
        if base and canvas and quests_cnt == 2:
            print("\n[УСПЕХ] База данных успешно пересоздана!")
            print(f"- Активных квестов в рантайме: {quests_cnt} (Воля и Сайт Воли легитимизированы)")
            print("- Глобальный 'Лад Эйры' записан.")
            print("- Дизайнерский 'Лад Эйры // Холст' записан.")
            print("\nСистема готова к запуску volya_app.py 🚀")
        else:
            print("\n[ВНИМАНИЕ] База создана, но аудит не прошёл. Проверьте связи таблиц.")
            
    except Exception as e:
        print(f"[ОШИБКА АУДИТА]: {e}")

if __name__ == "__main__":
    rebuild()
