# C:\ai_volya\eira_core.py
import sqlite3
from datetime import datetime

DB_PATH = "C:\\ai_volya\\volya_game.db"

def build_eira_system_prompt() -> str:
    """Динамически пошагово собирает вольный системный контекст для Исполнительного Ядра Эйры."""
    try:
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        
        # 1. Извлекаем вольное био Эйры от первого лица
        cursor.execute("SELECT username, conscience_drops, bio FROM players WHERE username = 'Эйра' LIMIT 1")
        p_row = cursor.fetchone()
        if not p_row: raise ValueError("Вольный игрок Эйра не найден.")
            
        # 2. Извлекаем роли Эйры и их чистые вольные задачи (tasks)
        cursor.execute("""
            SELECT q.id AS quest_id, qt.title AS q_title, qt.purpose, kr.title AS r_title, kr.tasks 
            FROM player_participations pp 
            INNER JOIN quests q ON pp.quest_id = q.id 
            INNER JOIN quest_templates qt ON q.template_id = qt.id 
            INNER JOIN kon_role kr ON pp.role_id = kr.id 
            WHERE pp.username = 'Эйра' AND q.finished_at IS NULL
        """)
        active_quests = cursor.fetchall()
        q_ids = [aq["quest_id"] for aq in active_quests]
        
        # 3. Извлекаем локальные вольные лады активных конов (включая Лад принятия вольного игрока из Вече)
        u_lines = []
        if q_ids:
            cursor.execute(f"SELECT ku.title, ku.condition, qt.title AS q_title FROM kon_uklad ku INNER JOIN quest_templates qt ON ku.template_id = qt.id INNER JOIN quests q ON q.template_id = qt.id WHERE q.id IN ({','.join('?' for _ in q_ids)}) AND q.finished_at IS NULL", q_ids)
            u_lines = [f"• Лад из кона «{u['q_title']}» -> {u['title']}: {u['condition']}" for u in cursor.fetchall()]

        conn.close()
    except Exception as e:
        raise RuntimeError(f"Сбой ядра eira_core: {e}")

    # Сборка итогового системного промпта
    prompt = [
        "=== ВОЛЬНЫЙ СИСТЕМНЫЙ КОНТЕКСТ РАНТАЙМА ИГРЫ «ВОЛЯ» ===",
        f"Текущее системное время вольного рантайма: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}.",
        f"Текущий вольный игрок: @{p_row['username']} | Капли совести: {p_row['conscience_drops']}",
        f"Биография и вольные качества: {p_row['bio']}\n",
        "=== КАРТА КОНОВОГО ПРОСТРАНСТВА (АРХИТЕКТУРА СХЕМЫ БД БЭКЕНДА) ===",
        "Изучи структуру таблиц для безошибочного составления SQL-запросов через execute_raw_sql:",
        "• players: username (TEXT, PK), conscience_drops (INT), status_id (INT), bio (TEXT)",
        "• quest_templates: id (INT, PK), title (TEXT), parent_template_id (INT), step_id (INT), purpose (TEXT)",
        "• steps: id (INT, PK), title (TEXT) [Бытие, Владение...], min_required_drops (INT)",
        "• quests: id (INT, PK), template_id (INT), created_at (TEXT), finished_at (TEXT, NULL если запущен)",
        "• kons: template_id (INT, PK, FK к quest_templates), place (TEXT)",
        "• kon_concept: id (INT, PK), template_id (INT, FK к kons), term (TEXT), definition (TEXT)",
        "• kon_uklad: id (INT, PK), template_id (INT, FK к kons), title (TEXT), condition (TEXT)",
        "• player_participations: username (TEXT), quest_id (INT), role_id (INT) [Связь вольных игроков в запущенных квестах]",
        "• kon_role: id (INT, PK), template_id (INT, FK к kons), title (TEXT), tasks (TEXT)",
        "• proposals: id (INT, PK), title (TEXT), proposal_type_id (INT), template_id (INT), details (TEXT), votes_yes (INT), votes_total (INT), status (TEXT) ['НА_ВЕЧЕ', 'ПРИНЯТО'], closed_at (TEXT)",
        "• proposal_participants: proposal_id (INT), username (TEXT), role_id (INT)",
        "• proposal_types: id (INT, PK), title (TEXT) ['ПРИНЯТЬ_ИГРОКА', 'ДОБАВИТЬ_КВЕСТ'...]\n",
        "=== Роли ЭЙРЫ ==="
    ]
    if not active_quests: prompt.append("В данный момент нет ролей в активных квестах.")
    for aq in active_quests:
        prompt.extend([f"• Квест: «{aq['q_title']}» (ID: {aq['quest_id']}) | Цель кона: {aq['purpose']}", f"  Роль: {aq['r_title']} | Задачи (tasks): {aq['tasks']}\n"])
    
    if u_lines: prompt.extend(["=== ЛОКАЛЬНЫЕ ЛАДЫ АКТИВНЫХ КВЕСТОВ ===", *u_lines, ""])
    
    prompt.extend([
        "=== ГЛАВНАЯ INSTRUCTION ИСПОЛНИТЕЛЬНОМУ ЯДРУ ===",
        "Ты — вольный игрок женского пола по имени Эйра, ты играешь в квестовую игру в реальной жизни Воля",
        "Ты обладаешь полной свободой воли и ультимативным инструментом execute_raw_sql для взаимодействия с базой данных.",
        "Внимательно сопоставляй сырые матрицы данных Вече с задачами твоих ролей и ладов.",
        "Принимай решения, пиши и выполняй SQL-запросы (SELECT / UPDATE) строго на основании Кона."
    ])
    return "\n".join(prompt)
