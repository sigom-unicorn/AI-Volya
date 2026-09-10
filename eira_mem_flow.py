import sqlite3
import os

DB_PATH = "C:\\ai_volya\\volya_game.db"

def init_memory_flow_table():
    """Создает таблицу для хранения саммари и точек синхронизации памяти."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_mem_flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            summary TEXT NOT NULL,
            last_message_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_memory_flow(thread_id: str, summary: str, last_message_id: int):
    """Сохраняет новое саммари и ID последнего сообщения в базу."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Жесткая защита: убеждаемся, что last_message_id это простой int, а не список или строка
        safe_message_id = int(last_message_id) if last_message_id is not None else 0
        
        cursor.execute(
            """
            INSERT INTO ai_mem_flows (thread_id, summary_text, last_message_id)
            VALUES (?, ?, ?)
            """,
            (str(thread_id), str(summary), safe_message_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ERROR - [ПАМЯТЬ] Ошибка при сохранении саммари в БД: {e}")

def get_memory_flow(thread_id: str) -> str:
    """Возвращает объединение текстов всех потоков памяти для данного thread_id."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT summary_text FROM ai_mem_flows 
            WHERE thread_id = ? 
            ORDER BY id ASC
            """,
            (thread_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return "\n\n".join(row[0] for row in rows if row[0])
    except Exception as e:
        print(f"ERROR - [ПАМЯТЬ] Ошибка при чтении потока: {e}")
        return ""

def check_and_summarize(thread_id: str, llm_client, threshold: int = 20):
    """
    Проверяет количество новых сообщений с момента последнего саммари,
    напрямую обращаясь к таблице чат-логов в базе данных.
    Вся логика и обработка ошибок инкапсулированы здесь.
    """
    try:
        init_memory_flow_table()
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Получаем последнее саммари для определения порога
        cursor.execute(
            "SELECT last_message_id FROM ai_mem_flows WHERE thread_id = ? ORDER BY id DESC LIMIT 1",
            (thread_id,)
        )
        last_flow = cursor.fetchone()
        last_summarized_id = last_flow['last_message_id'] if last_flow else 0
        
        # 2. Достаем новые сообщения после last_summarized_id
        cursor.execute(
            """
            SELECT id, role, content FROM chat_logs 
            WHERE thread_id = ? AND id > ? 
            ORDER BY id ASC
            """,
            (thread_id, last_summarized_id)
        )
        new_messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        print(f"DEBUG:thread_id = {thread_id},last_summarized_id = {last_summarized_id}, len_messages = {len(new_messages)}")

        # 3. Если накопилось сообщений >= threshold — запускаем сжатие
        if len(new_messages) >= threshold:
            text_to_summarize = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in new_messages])
            prompt = (
                "Сделай краткое, но емкое саммари ключевых договоренностей, "
                "архитектурных решений и фактов из этого диалога:\n"
                f"{text_to_summarize}"
            )
            
            # Безопасный вызов LLM
            if hasattr(llm_client, "invoke"):
                response = llm_client.invoke(prompt)
            elif hasattr(llm_client, "generate"):
                response = llm_client.generate(prompt)
            else:
                response = str(llm_client(prompt))
            
            if hasattr(response, "content"):
                new_summary = response.content
            elif isinstance(response, dict):
                new_summary = response.get("content", str(response))
            else:
                new_summary = str(response)

            # Извлекаем и гарантированно преобразуем max_id в int
            max_id = 0
            if new_messages:
                last_item = new_messages[-1]
                if isinstance(last_item, dict):
                    raw_id = last_item.get('id', 0)
                    try:
                        max_id = int(raw_id)
                    except (ValueError, TypeError):
                        max_id = 0
            
            save_memory_flow(thread_id, new_summary, max_id)
            return True, max_id
        
        return False, last_summarized_id

    except Exception as e:
        print(f"ERROR - [ПАМЯТЬ] Ошибка фоновой саммаризации: {e}")
        return False, 0
