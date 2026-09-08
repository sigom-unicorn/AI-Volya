# C:\ai_volya\rebuild_db.py
import os
import sqlite3
import db_init
import db_seed

DB_PATH = "C:\\ai_volya\\volya_game.db"

def rebuild():
    print("=== ЗАПУСК ТОТАЛЬНОЙ ПЕРЕСБОРКИ РАНТАЙМА 'ВОЛЯ' ===")
    
    # 1. Сносим старую вольную базу данных, если она существует
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print("[1/3] Старая база данных volya_game.db успешно удалена.")
        except Exception as e:
            print(f"[ОШИБКА] Не удалось удалить файл вольной базы. Убедитесь, что процесс volya_app.py закрыт. Ошибка: {e}")
            return
    else:
        print("[1/3] Старая база данных не обнаружена. Создаем с чистого вольного листа.")

    # 2. Запускаем инициализацию каркаса структуры (db_init.py)
    try:
        print("[2/3] Запуск db_init.py...")
        db_init.init_db()
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ]: {e}")
        return

    # 3. Запускаем наполнение 5 базовыми шаблонами и первичными голосованиями (db_seed.py)
    try:
        print("[3/3] Запуск db_seed.py...")
        db_seed.seed_data()
    except Exception as e:
        print(f"[КРИТИЧЕСКАЯ ОШИБКА СИДЕРА]: {e}")
        return

    # 4. Финальный вольный экспресс-аудит
    print("\n--- ЗАПУСК ЭКСПРЕСС-АУДИТА РАНТАЙМА В НОВОЙ ВОЛЬНОЙ БАЗЕ ---")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Считаем количество активных квестов (должно быть 2: Воля и Сайт Воли)
        cursor.execute("SELECT COUNT(*) as cnt FROM quests WHERE finished_at IS NULL")
        quests_cnt = cursor.fetchone()["cnt"]
        
        # Проверяем, на месте ли вольные предложения Вече
        cursor.execute("SELECT COUNT(*) as cnt FROM proposals WHERE status = 'ПРИНЯТО'")
        proposals_cnt = cursor.fetchone()["cnt"]
        
        # Считываем биографию вольного игрока Эйры для проверки
        cursor.execute("SELECT bio FROM players WHERE username = 'Эйра'")
        eira_bio_row = cursor.fetchone()
        
        conn.close()
        
        if quests_cnt == 2 and proposals_cnt == 2 and eira_bio_row:
            print("[УСПЕХ] Вольная база данных успешно пересоздана и прошла аудит!")
            print(f"- Активных вольных квестов в рантайме: {quests_cnt} (Корень Воли и Сайт Воли легитимизированы)")
            print(f"- Архивных принятых вольных предложений в летописи: {proposals_cnt}")
            print("- Вольный манифест Эйры от первого лица успешно записан в игровое био.")
            print("\nСистема полностью готова к асинхронному запуску через volya_app.py 🚀")
        else:
            print("[ВНИМАНИЕ] База создана, но вольный аудит выявил несоответствие связей рантайма.")
            
    except Exception as e:
        print(f"[ОШИБКА ЭКСПРЕСС-АУДИТА]: {e}")

if __name__ == "__main__":
    rebuild()
