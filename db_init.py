# C:\ai_volya\db_init.py
import sqlite3

DB_PATH = "C:\\ai_volya\\volya_game.db"

def init_db():
    print(f"[СТРУКТУРА] Разворачиваем каркас базы данных по пути: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    # --- 0. СИСТЕМНАЯ ПАМЯТЬ РАНТАЙМА (ЛОГИ ЧАТА) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # --- 1. ТАБЛИЦЫ-СПРАВОЧНИКИ (СЛОВАРИ СИСТЕМЫ) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL,
        min_required_drops INTEGER DEFAULT NULL,
        min_reward_drops INTEGER DEFAULT NULL,
        max_reward_drops INTEGER DEFAULT NULL
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quest_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quest_subtypes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_id INTEGER NOT NULL,
        title TEXT UNIQUE NOT NULL,
        FOREIGN KEY (type_id) REFERENCES quest_types (id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_statuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS result_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proposal_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL
    )""")
    
    # --- 2. ТАБЛИЦЫ АРХИТЕКТУРЫ ДРЕВА И КОНА (ШАБЛОНЫ) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quest_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE NOT NULL,
        parent_template_id INTEGER DEFAULT NULL,
        step_id INTEGER NOT NULL,
        type_id INTEGER NOT NULL,
        subtype_id INTEGER DEFAULT NULL,
        purpose TEXT NOT NULL,
        FOREIGN KEY (parent_template_id) REFERENCES quest_templates (id) ON DELETE SET NULL,
        FOREIGN KEY (step_id) REFERENCES steps (id),
        FOREIGN KEY (type_id) REFERENCES quest_types (id),
        FOREIGN KEY (subtype_id) REFERENCES quest_subtypes (id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kons (
        template_id INTEGER PRIMARY KEY,
        place TEXT NOT NULL,
        FOREIGN KEY (template_id) REFERENCES quest_templates (id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kon_concept (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        term TEXT NOT NULL,
        definition TEXT NOT NULL,
        FOREIGN KEY (template_id) REFERENCES kons (template_id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kon_role (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        responsibility TEXT NOT NULL,
        tasks TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (template_id) REFERENCES kons (template_id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kon_uklad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        condition TEXT NOT NULL,
        FOREIGN KEY (template_id) REFERENCES kons (template_id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kon_result (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        result_type_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT NULL,
        FOREIGN KEY (template_id) REFERENCES kons (template_id) ON DELETE CASCADE,
        FOREIGN KEY (result_type_id) REFERENCES result_types (id)
    )""")
    
    # --- 3. ЖИВЫЕ ЭКЗЕМПЛЯРЫ, ВОЛЬНЫЕ ИГРОКИ И УЧАСТИЕ ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        template_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        finished_at TEXT DEFAULT NULL,
        FOREIGN KEY (template_id) REFERENCES quest_templates (id) ON DELETE RESTRICT
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        username TEXT PRIMARY KEY,
        conscience_drops INTEGER DEFAULT 0,
        status_id INTEGER NOT NULL,
        bio TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (status_id) REFERENCES player_statuses (id)
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_participations (
        username TEXT NOT NULL,
        quest_id INTEGER NOT NULL,
        role_id INTEGER NOT NULL,
        PRIMARY KEY (username, quest_id, role_id),
        FOREIGN KEY (username) REFERENCES players (username) ON DELETE CASCADE,
        FOREIGN KEY (quest_id) REFERENCES quests (id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES kon_role (id) ON DELETE CASCADE
    )""")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        proposal_type_id INTEGER NOT NULL,
        template_id INTEGER DEFAULT NULL,
        details TEXT NOT NULL,
        votes_yes INTEGER DEFAULT 0,
        votes_total INTEGER DEFAULT 1,
        status TEXT DEFAULT 'НА_ВЕЧЕ',
        created_at TEXT NOT NULL,
        closed_at TEXT DEFAULT NULL,
        FOREIGN KEY (proposal_type_id) REFERENCES proposal_types (id),
        FOREIGN KEY (template_id) REFERENCES quest_templates (id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS proposal_participants (
        proposal_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        role_id INTEGER NOT NULL,
        PRIMARY KEY (proposal_id, username, role_id),
        FOREIGN KEY (proposal_id) REFERENCES proposals (id) ON DELETE CASCADE,
        FOREIGN KEY (username) REFERENCES players (username) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES kon_role (id) ON DELETE CASCADE
    )""")
    
    # --- 4. ИНДЕКСЫ ДЛЯ ОПТИМИЗАЦИИ РАНТАЙМА ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quests_active ON quests(finished_at) WHERE finished_at IS NULL;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_participations_user ON player_participations(username, quest_id);")
    
    conn.commit()
    
    # --- 5. АВТОЗАПОЛНЕНИЕ БАЗОВЫХ СИСТЕМНЫХ СЛОВАРЕЙ ---
    print("[СТРУКТУРА] Наполняем вольные системные справочники данными...")
    
    for s in ["Бытие", "Познание", "Созидание", "Искусство", "Путешествия", "Владение"]:
        cursor.execute("INSERT OR IGNORE INTO steps (title) VALUES (?)", (s,))
        
    cursor.execute("INSERT OR IGNORE INTO quest_types (title) VALUES ('Непрерывный')")
    cursor.execute("INSERT OR IGNORE INTO quest_types (title) VALUES ('Конечный')")
    
    for sub in ["Разовый", "Цикличный", "По потребности"]:
        cursor.execute("INSERT OR IGNORE INTO quest_subtypes (type_id, title) VALUES (2, ?)", (sub,))
        
    for stat in ["В_ИГРЕ", "ИЗГНАН", "ВЫШЕЛ_ПО_ВОЛЕ"]:
        cursor.execute("INSERT OR IGNORE INTO player_statuses (title) VALUES (?)", (stat,))
        
    for r_type in ["Ресурс", "Артефакт", "Условие быта", "Взаимопонимание"]:
        cursor.execute("INSERT OR IGNORE INTO result_types (title) VALUES (?)", (r_type,))
        
    for prop in ["ДОБАВИТЬ_КВЕСТ", "ДОБАВИТЬ_ЛАД", "ИЗМЕНИТЬ_ПОНЯТИЕ", "ПРИНЯТЬ_ИГРОКА"]:
        cursor.execute("INSERT OR IGNORE INTO proposal_types (title) VALUES (?)", (prop,))
        
    conn.commit()
    print("[СТРУКТУРА] Все вольные таблицы, справочники и логи памяти успешно развернуты.")
    conn.close()

if __name__ == "__main__":
    init_db()
