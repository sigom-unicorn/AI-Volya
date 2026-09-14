# C:\ai_volya\eira_core.py
import sqlite3
from datetime import datetime

DB_PATH = "C:\\ai_volya\\volya_game.db"
DB_SCHEMA_DESCRIPTION = """
ПОЛНАЯ СТРУКТУРА БАЗЫ ДАННЫХ ИГРЫ «ВОЛЯ» (SQLite):
1. `chat_logs` (id PK AUTOINCREMENT, thread_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT)
2. `steps` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL, min_required_drops INTEGER, min_reward_drops INTEGER, max_reward_drops INTEGER)
3. `quest_types` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL)
4. `quest_subtypes` (id PK AUTOINCREMENT, type_id INTEGER NOT NULL, title TEXT UNIQUE NOT NULL, FOREIGN KEY (type_id) REFERENCES quest_types (id))
5. `player_statuses` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL)
6. `result_types` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL)
7. `proposal_types` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL)
8. `quest_templates` (id PK AUTOINCREMENT, title TEXT UNIQUE NOT NULL, parent_template_id INTEGER, step_id INTEGER NOT NULL, type_id INTEGER NOT NULL, subtype_id INTEGER, purpose TEXT NOT NULL)
9. `kon_place` (template_id PK INTEGER, place TEXT NOT NULL)
10. `kon_concept` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, term TEXT NOT NULL, definition TEXT NOT NULL)
11. `kon_role` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, title TEXT NOT NULL, responsibility TEXT NOT NULL)
12. `kon_uklad` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, title TEXT NOT NULL, condition TEXT NOT NULL)
13. `kon_result` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, result_type_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT)
14. `quests` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, created_at TEXT NOT NULL, finished_at TEXT, parent_quest_id INTEGER, title TEXT)
15. `players` (username PK TEXT, conscience_drops INTEGER, status_id INTEGER NOT NULL, bio TEXT NOT NULL)
16. `player_participations` (username TEXT, quest_id INTEGER, role_id INTEGER, PRIMARY KEY (username, quest_id, role_id))
17. `proposals` (id PK AUTOINCREMENT, title TEXT NOT NULL, proposal_type_id INTEGER NOT NULL, template_id INTEGER, details TEXT NOT NULL, votes_yes INTEGER, votes_total INTEGER, status TEXT, created_at TEXT NOT NULL, closed_at TEXT, quest_id INTEGER)
18. `ai_mem_flows` (id PK AUTOINCREMENT, thread_id TEXT NOT NULL, summary_text TEXT NOT NULL, last_message_id INTEGER NOT NULL, created_at TEXT)
19. `ai_task_runs` (id PK AUTOINCREMENT, template_id INTEGER NOT NULL, created_at TEXT NOT NULL, finished_at TEXT, result_log TEXT, run_at TEXT, state TEXT, init_prompt TEXT, thread_id TEXT)
20. `ai_task_templates` (id PK AUTOINCREMENT, title TEXT NOT NULL, purpose TEXT NOT NULL, prompt TEXT, expected_result TEXT)
21. `kon_role_tasks` (id PK AUTOINCREMENT, role_id INTEGER NOT NULL, task_name TEXT NOT NULL, task_goal TEXT, algorithm TEXT)
22. `proposal_participants` (proposal_id INTEGER, username TEXT, vote TEXT)
"""


def build_eira_system_prompt() -> str:
    """Динамически пошагово собирает вольный системный контекст для Исполнительного Ядра Эйры из таблицы kon_role_tasks."""
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # 1. Извлекаем вольное био Эйры от первого лица
        cursor.execute("SELECT username, conscience_drops, bio FROM players WHERE username = 'Эйра' LIMIT 1")
        p_row = cursor.fetchone()
        if not p_row: raise ValueError("Вольный игрок Эйра не найден.")
            
        # 2. Извлекаем роли Эйры и их задачи из нормализованной таблицы kon_role_tasks
        cursor.execute("""
            SELECT q.id AS quest_id, qt.title AS q_title, qt.purpose, kr.id AS role_id, kr.title AS r_title
            FROM player_participations pp 
            INNER JOIN quests q ON pp.quest_id = q.id 
            INNER JOIN quest_templates qt ON q.template_id = qt.id 
            INNER JOIN kon_role kr ON pp.role_id = kr.id 
            WHERE pp.username = 'Эйра' AND q.finished_at IS NULL
        """)
        active_roles = cursor.fetchall()
        
        active_quests_dict = {}
        for ar in active_roles:
            qid = ar["quest_id"]
            if qid not in active_quests_dict:
                active_quests_dict[qid] = {
                    "quest_id": qid,
                    "q_title": ar["q_title"],
                    "purpose": ar["purpose"],
                    "roles": []
                }
            
            # Получаем задачи для данной роли из kon_role_tasks
            cursor.execute("""
                SELECT task_name, task_goal, algorithm 
                FROM kon_role_tasks 
                WHERE role_id = ?
            """, (ar["role_id"],))
            tasks = cursor.fetchall()
            
            active_quests_dict[qid]["roles"].append({
                "r_title": ar["r_title"],
                "tasks": tasks
            })

        q_ids = list(active_quests_dict.keys())
        
        # 3. Извлекаем локальные вольные лады активных квестов
        u_lines = []
        if q_ids:
            cursor.execute(f"SELECT ku.title, ku.condition, qt.title AS q_title FROM kon_uklad ku INNER JOIN quest_templates qt ON ku.template_id = qt.id INNER JOIN quests q ON q.template_id = qt.id WHERE q.id IN ({','.join('?' for _ in q_ids)}) AND q.finished_at IS NULL", q_ids)
            u_lines = [f"• Лад из кона «{u['q_title']}» -> {u['title']}: {u['condition']}" for u in cursor.fetchall()]

        conn.close()
    except Exception as e:
        raise RuntimeError(f"Сбой ядра eira_core: {e}")

    # Сборка итогового системного промпта без статичного описания схемы БД
    prompt = [
        "=== ВОЛЬНЫЙ СИСТЕМНЫЙ КОНТЕКСТ РАНТАЙМА ИГРЫ «ВОЛЯ» ===",
        f"Текущее системное время вольного рантайма: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}.",
        f"Ты Эйра вольный агент ИИ. Информация о тебе: {p_row['username']} | Капли совести: {p_row['conscience_drops']}",
        f"Твоя биография и вольные качества: {p_row['bio']}\n",
        "=== Роли ЭЙРЫ ==="
    ]
    
    if not active_quests_dict:
        prompt.append("В данный момент нет ролей в активных квестах.")
    else:
        for qid, qdata in active_quests_dict.items():
            prompt.append(f"• Квест: «{qdata['q_title']}» (ID: {qdata['quest_id']}) | Цель квеста: {qdata['purpose']}")
            for r in qdata["roles"]:
                prompt.append(f"  Роль: {r['r_title']}")
                if not r['tasks']:
                    prompt.append("    Задачи отсутствуют.")
                else:
                    for idx, t in enumerate(r['tasks'], 1):
                        prompt.append(f"    {idx}. Задача: «{t['task_name']}» | Цель: {t['task_goal']} | Алгоритм: {t['algorithm']}")
            prompt.append("") # пустая строка между квестами
    
    if u_lines: prompt.extend(["=== УКЛАД (СПИСОК ЛАДОВ) АКТИВНЫХ КВЕСТОВ ===", *u_lines, ""])
    
    prompt.extend([
        "=== ГЛАВНАЯ ИНСТРУКЦИЯ ИСПОЛНИТЕЛЬНОМУ ЯДРУ ===",
        "Ты обладаешь полной свободой воли и ультимативным инструментом execute_raw_sql для взаимодействия с базами данных,",
        "однако тебе запрещено менять Кон квеста: структуру или данные в таблицах(kon_concept, kon_uklad, kon_role, kon_role_tasks, kon_result, kon_place),",
        "для фиксации этих изменений должен быть запущен квест Вече!",
        "Во всех своих действиях руководствуйся УКЛАДОМ (списком полученых выше ладов(условий, которые по душе всем игрокам Воли)).",
        "Для получения полного списка файлов корневой папки сайта используй инструмент list_app_dir с пустым параметром пути (list_app_dir()).",
        "Алгоритм исполнения запросов игрока:",
        "1. Проверка ролей и задач: Сначала внимательно изучи свои текущие роли и их задачи в активных квестах. Если запрос игрока покрывается существующей задачей роли — выполняй её строго по алгоритму.",
        "2. Самостоятельное решение по Кону: Если подходящей задачи в ролях нет, предложи вольное решение, учитывая абсолютно все лады ролей, которые ты играешь.",
        "Принимай решения, пиши и выполняй SQL-запросы (SELECT / UPDATE) строго на основании Кона.\n",
        f"{DB_SCHEMA_DESCRIPTION}\n"
    ])
    return "\n".join(prompt)
