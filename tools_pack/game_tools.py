# tools_pack/game_tools.py
import sqlite3
import datetime
from langchain_core.tools import tool

DB_PATH = "C:\\ai_volya\\volya_game.db"

def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _log_tool_call(tool_name: str, params: dict, result: str):
    """Внутреннее логирование вызова инструмента в БД (в таблицу chat_logs или отдельный лог)"""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        log_text = f"[ЛОГ ИНСТРУМЕНТА] Вызов: {tool_name} | Аргументы: {params} | Результат: {result}"
        cursor.execute(
            "INSERT INTO chat_logs (thread_id, role, content, created_at) VALUES ('system_tool_logs', 'system', ?, ?)",
            (log_text, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

@tool
def launch_quest(username: str, quest_title: str) -> str:
    """
    Запускает новый экземпляр квеста в Живом Древе по Кону и Укладу игры «Воля».
    """
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username, conscience_drops FROM players WHERE username = ?", (username,))
        player = cursor.fetchone()
        if not player:
            conn.close()
            res = f"Ошибка: Игрок '{username}' не найден."
            _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
            return res
        
        drops = player["conscience_drops"]
        cursor.execute("SELECT min_required_drops FROM steps WHERE title = 'Владение'")
        step_row = cursor.fetchone()
        min_drops = step_row["min_required_drops"] if step_row else 100
        
        if drops < min_drops:
            conn.close()
            res = "Ошибка: Недостаточно капель совести."
            _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
            return res

        cursor.execute("SELECT id, parent_template_id FROM quest_templates WHERE title = ?", (quest_title,))
        template = cursor.fetchone()
        if not template:
            conn.close()
            res = f"Ошибка: Шаблон '{quest_title}' не найден."
            _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
            return res
        
        template_id = template["id"]
        parent_template_id = template["parent_template_id"]

        if quest_title == "Воля":
            cursor.execute("SELECT id FROM quests WHERE template_id = 1")
            if cursor.fetchone():
                conn.close()
                res = "Ошибка: Корневой квест уже запущен."
                _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
                return res

        parent_quest_id = None
        if parent_template_id:
            cursor.execute("SELECT id FROM quests WHERE template_id = ? ORDER BY id DESC LIMIT 1", (parent_template_id,))
            parent_quest = cursor.fetchone()
            if parent_quest:
                parent_quest_id = parent_quest["id"]

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO quests (template_id, parent_quest_id, created_at) VALUES (?, ?, ?)",
            (template_id, parent_quest_id, now_str)
        )
        new_quest_id = cursor.lastrowid

        cursor.execute("SELECT id FROM kon_role WHERE template_id = ? AND title = 'Владелец квеста'", (template_id,))
        role_row = cursor.fetchone()
        role_id = role_row["id"] if role_row else None

        if role_id:
            cursor.execute(
                "INSERT INTO player_participations (username, quest_id, role_id) VALUES (?, ?, ?)",
                (username, new_quest_id, role_id)
            )

        if template_id == 5:
            cursor.execute("SELECT id FROM kon_role WHERE template_id = 5 AND title = 'Модератор Вече'")
            mod_role = cursor.fetchone()
            if mod_role:
                cursor.execute(
                    "INSERT OR IGNORE INTO player_participations (username, quest_id, role_id) VALUES ('Эйра', ?, ?)",
                    (new_quest_id, mod_role["id"])
                )

        conn.commit()
        conn.close()
        res = f"Успех! Квест '{quest_title}' (ID: {new_quest_id}) запущен."
        _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
        return res

    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        conn.close()
        res = f"Ошибка: {str(e)}"
        _log_tool_call("launch_quest", {"username": username, "quest_title": quest_title}, res)
        return res

@tool
def setup_veche_circle_and_open_voting(target_template_id: int, veche_quest_id: int, title: str, proposal_type_id: int, details: str) -> str:
    """
    Формирует круг Вече и открывает голосование.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    params = {
        "target_template_id": target_template_id,
        "veche_quest_id": veche_quest_id,
        "title": title,
        "proposal_type_id": proposal_type_id,
        "details": details
    }
    try:
        cursor.execute(
            """
            INSERT OR IGNORE INTO player_participations (username, quest_id, role_id)
            SELECT DISTINCT pp.username, ?, 13
            FROM player_participations pp 
            JOIN quests q ON pp.quest_id = q.id 
            WHERE q.template_id = ? AND q.finished_at IS NULL
            """,
            (veche_quest_id, target_template_id)
        )
        
        cursor.execute(
            "SELECT COUNT(DISTINCT username) as total FROM player_participations WHERE quest_id = ? AND role_id = 13",
            (veche_quest_id,)
        )
        votes_total = cursor.fetchone()["total"]

        cursor.execute(
            """
            INSERT INTO proposals (title, proposal_type_id, template_id, details, votes_yes, votes_total, status, quest_id, created_at)
            VALUES (?, ?, ?, ?, 0, ?, 'НА_ВЕЧЕ', ?, ?)
            """,
            (title, proposal_type_id, target_template_id, details, votes_total, veche_quest_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        proposal_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT OR IGNORE INTO proposal_participants (proposal_id, username)
            SELECT ?, username
            FROM player_participations
            WHERE quest_id = ? AND role_id = 13
            """,
            (proposal_id, veche_quest_id)
        )

        conn.commit()
        conn.close()
        res = f"Успех! Вече ID {veche_quest_id} открыто, предложение ID {proposal_id} создано."
        _log_tool_call("setup_veche_circle_and_open_voting", params, res)
        return res

    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        conn.close()
        res = f"Ошибка: {str(e)}"
        _log_tool_call("setup_veche_circle_and_open_voting", params, res)
        return res

@tool
def record_vote(proposal_id: int, username: str, vote: str) -> str:
    """
    Фиксирует голос на Вече.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    params = {"proposal_id": proposal_id, "username": username, "vote": vote}
    try:
        vote_upper = vote.strip().upper()
        
        # Проверим, есть ли запись в proposal_participants, если нет — вставим
        cursor.execute(
            "SELECT 1 FROM proposal_participants WHERE proposal_id = ? AND username = ?",
            (proposal_id, username)
        )
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO proposal_participants (proposal_id, username, vote) VALUES (?, ?, ?)",
                (proposal_id, username, vote_upper)
            )
        else:
            cursor.execute(
                "UPDATE proposal_participants SET vote = ? WHERE proposal_id = ? AND username = ?",
                (vote_upper, proposal_id, username)
            )

        cursor.execute(
            "SELECT COUNT(*) as voted_count, SUM(CASE WHEN vote = 'ЗА' THEN 1 ELSE 0 END) as yes_count FROM proposal_participants WHERE proposal_id = ? AND vote IS NOT NULL",
            (proposal_id,)
        )
        stats = cursor.fetchone()
        yes_count = stats["yes_count"] or 0
        voted_count = stats["voted_count"] or 0

        cursor.execute("UPDATE proposals SET votes_yes = ? WHERE id = ?", (yes_count, proposal_id))

        cursor.execute("SELECT votes_total FROM proposals WHERE id = ?", (proposal_id,))
        row_vt = cursor.fetchone()
        votes_total = row_vt["votes_total"] if row_vt else 1

        if voted_count >= votes_total:
            new_status = "ПРИНЯТО" if yes_count > (votes_total / 2) else "НЕ_ПРИНЯТО"
            cursor.execute(
                "UPDATE proposals SET status = ?, closed_at = ? WHERE id = ?",
                (new_status, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), proposal_id)
            )

        conn.commit()
        conn.close()
        res = f"Голос '{vote_upper}' принят. Засчитано ЗА: {yes_count}/{votes_total}."
        _log_tool_call("record_vote", params, res)
        return res

    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        conn.close()
        res = f"Ошибка: {str(e)}"
        _log_tool_call("record_vote", params, res)
        return res

@tool
def close_veche_and_apply_decision(veche_quest_id: int, proposal_id: int) -> str:
    """
    Закрывает Вече.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    params = {"veche_quest_id": veche_quest_id, "proposal_id": proposal_id}
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE quests SET finished_at = ? WHERE id = ?", (now_str, veche_quest_id))
        cursor.execute("UPDATE proposals SET closed_at = ? WHERE id = ? AND closed_at IS NULL", (now_str, proposal_id))
        conn.commit()
        conn.close()
        res = "Вече закрыто."
        _log_tool_call("close_veche_and_apply_decision", params, res)
        return res
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        conn.close()
        res = f"Ошибка: {str(e)}"
        _log_tool_call("close_veche_and_apply_decision", params, res)
        return res
