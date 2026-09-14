import sqlite3
import time
import threading
import logging
import os
from datetime import datetime
from langgraph.prebuilt import create_react_agent
from tools_pack import db_tools
from langchain_groq import ChatGroq

DB_PATH = "C:\\ai_volya\\volya_game.db"

# Создаем модель qwen/qwen3.8-27b через Groq API для фонового воркера
worker_model = ChatGroq(
    model="qwen/qwen3.8-27b", 
    temperature=0.1,
    api_key=os.environ.get("GROQ_API_KEY")
)

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

def sanitize_result(res):
    if res is None:
        return ""
    if isinstance(res, str):
        return res
    if isinstance(res, list):
        text_parts = []
        for item in res:
            if isinstance(item, dict):
                if "text" in item:
                    text_parts.append(str(item["text"]))
                else:
                    text_parts.append(str(item))
            else:
                text_parts.append(str(item))
        return "\n".join(text_parts)
    if isinstance(res, dict):
        if "text" in res:
            return str(res["text"])
        return str(res)
    return str(res)

def run_ai_task_worker(model=None):
    """Фоновый воркер-агент для обработки задач Нитей Эйры с передачей схемы БД"""
    active_model = worker_model if model is None else model
    
    current_local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logging.info("[AI Worker Agent] Фоновый поток запущен с моделью groq/compound-mini и полной схемой БД...")
    
    try:
        auditor_system_prompt = (
            "Ты — суверенный ИИ-аудитор фонового воркера во вселенной игры «Воля». "
            f"Текущая локальная дата и время рантайма: {current_local_time}. \n"
            f"{DB_SCHEMA_DESCRIPTION}\n"
            "Твоя задача — проверить фактическое состояние базы данных с помощью инструмента execute_sql_query. "
            "Сделай реальные SELECT-запросы к таблицам `quests`, `player_participations` и другим, чтобы убедиться, что все необходимые записи действительно созданы и связаны. "
            "Если все связанные таблицы успешно заполнены, напиши 'ВЫПОЛНЕНО: все связанные записи в базе подтверждены инструментом'. "
            "Если хоть одна таблица пуста или данные повреждены, напиши 'ОШИБКА: целостность данных в базе не подтверждена'."
        )
        auditor_executor = create_react_agent(active_model, db_tools, prompt=auditor_system_prompt)
    except Exception as e:
        logging.error(f"[AI Worker Agent] Не удалось создать агента-аудитора: {e}")
        return

    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            query = """
                SELECT id, template_id, init_prompt, thread_id 
                FROM ai_task_runs 
                WHERE state = 'ОЖИДАНИЕ' 
                ORDER BY id ASC 
                LIMIT 1;
            """
            cursor.execute(query)
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                time.sleep(5)
                continue
                
            task_id, template_id, init_prompt, thread_id = row
            
            if thread_id:
                cursor.execute("""
                    SELECT COUNT(*) FROM ai_task_runs 
                    WHERE thread_id = ? AND id < ? AND state != 'ВЫПОЛНЕНО';
                """, (thread_id, task_id))
                pending_count = cursor.fetchone()[0]
                if pending_count > 0:
                    conn.close()
                    time.sleep(3)
                    continue

            logging.info(f"[AI Worker Agent] Найдена задача ID {task_id} (шаблон {template_id}, thread: {thread_id}). Переводим в В_РАБОТЕ.")
            
            cursor.execute("UPDATE ai_task_runs SET state = 'В_РАБОТЕ' WHERE id = ?;", (task_id,))
            conn.commit()
            
            cursor.execute("SELECT prompt, expected_result FROM ai_task_templates WHERE id = ?;", (template_id,))
            template_row = cursor.fetchone()
            
            if not template_row:
                cursor.execute("UPDATE ai_task_runs SET state = 'ОШИБКА', result_log = ? WHERE id = ?;", 
                               ("Шаблон не найден", task_id))
                conn.commit()
                conn.close()
                continue
                
            template_prompt, expected_result = template_row
                        
            system_prompt = (
                f"Ты — исполняемый воркер баз данных 'Нити Эйры' во вселенной игры «Воля». "
                f"Текущая локальная дата и время рантайма: {current_local_time}. \n"
                f"{DB_SCHEMA_DESCRIPTION}\n"
                "Используй эту метку времени при создании записей. "
                "Твоя задача — техническое выполнение инструкций через инструмент execute_sql_query, строго опираясь на реальную структуру таблиц БД. "
                "После выполнения работы дай краткий технический отчет о проделанной работе."
            )
            
            try:
                agent_executor = create_react_agent(active_model, db_tools, prompt=system_prompt)
            except Exception as e:
                logging.error(f"[AI Worker Agent] Не удалось создать агента-исполнителя: {e}")
                continue

            if init_prompt:
                full_prompt = f"Текущее локальное время рантайма: {current_local_time}\n{init_prompt}\n\nИнструкция шаблона:\n{template_prompt}\n\nВЫЗОВИ ИНСТРУМЕНТ execute_sql_query И ВЫПОЛНИ ВСЕ НЕОБХОДИМЫЕ SQL-ЗАПРОСЫ с учетом реальной схемы БД!"
            else:
                full_prompt = f"Текущее локальное время рантайма: {current_local_time}\n{template_prompt}"
            
            try:
                response = agent_executor.invoke({"messages": [("user", full_prompt)]})
                messages = response.get("messages", [])
                raw_result = messages[-1].content if messages else "Нет ответа от агента"
            except Exception as agent_err:
                raw_result = f"Ошибка выполнения агента: {agent_err}"
            
            sanitized_raw = sanitize_result(raw_result)
            
            cursor.execute("UPDATE ai_task_runs SET result_log = ?, state = 'НА_ПРОВЕРКЕ' WHERE id = ?;", 
                           (sanitized_raw, task_id))
            conn.commit()
            
            audit_prompt = f"""
            Проверь результат выполнения задачи.
            Текущее время: {current_local_time}
            Промпт задачи: {full_prompt}
            Фактический отчет агента: {sanitized_raw}
            Ожидаемый эталонный результат: {expected_result}
            
            Используй инструмент execute_sql_query, чтобы последовательно проверить таблицы `quests`, `player_participations` и убедиться в корректности созданных записей.
            Вынеси вердикт согласно системному промпту (начни ответ с 'ВЫПОЛНЕНО: ...' либо 'ОШИБКА: ...').
            """
            
            try:
                audit_response = auditor_executor.invoke({"messages": [("user", audit_prompt)]})
                audit_messages = audit_response.get("messages", [])
                audit_raw = audit_messages[-1].content if audit_messages else "Нет ответа от аудитора"
                audit_result = sanitize_result(audit_raw)
            except Exception as audit_err:
                audit_result = f"Ошибка аудита: {audit_err}"
                
            final_state = "ВЫПОЛНЕНО" if "ВЫПОЛНЕНО" in audit_result else "ОШИБКА"
            final_log = f"ФАКТ АГЕНТА:\n{sanitized_raw}\n\nАУДИТ АГЕНТОМ ПО ВСЕМ ТАБЛИЦАМ:\n{audit_result}"
            
            cursor.execute("UPDATE ai_task_runs SET result_log = ?, state = ?, finished_at = datetime('now', 'localtime') WHERE id = ?;", 
                           (final_log, final_state, task_id))
            conn.commit()
            conn.close()
            
            logging.info(f"[AI Worker Agent] Задача ID {task_id} завершена со статусом {final_state}.")
            
        except Exception as e:
            logging.error(f"[AI Worker Agent Error]: {e}")
            try:
                conn.close()
            except:
                pass
            time.sleep(5)

def start_ai_worker_background(model=None):
    """Запуск агента-воркера в отдельном потоке с моделью groq/compound-mini"""
    t = threading.Thread(target=run_ai_task_worker, args=(model,), daemon=True)
    t.start()