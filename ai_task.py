import sqlite3
import time
import threading
import logging

DB_PATH = "C:\\ai_volya\\volya_game.db"

def sanitize_result(res):
    """Надежно преобразует любой ответ модели (список словарей, строку, dict) в чистый текст."""
    if res is None:
        return ""
    if isinstance(res, str):
        return res
    if isinstance(res, list):
        text_parts = []
        for item in res:
            if isinstance(item, dict):
                # Если это блок вида {'type': 'text', 'text': '...'}
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

def execute_ai_model_call(model, prompt):
    """Безопасный вызов языковой модели"""
    try:
        response = model.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return sanitize_result(content)
    except Exception as e:
        return f"Ошибка вызова модели: {e}"

def run_ai_task_worker(model):
    """Фоновый воркер для обработки задач Нитей Эйры"""
    logging.info("[AI Worker] Фоновый поток запущен и слушает базу данных...")
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 1. Ищем задачу в статусе ОЖИДАНИЕ
            cursor.execute("SELECT id, template_id FROM ai_task_runs WHERE state = 'ОЖИДАНИЕ' LIMIT 1;")
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                time.sleep(5)
                continue
                
            task_id, template_id = row
            logging.info(f"[AI Worker] Найдена задача ID {task_id} (шаблон {template_id}). Переводим в В_РАБОТЕ.")
            
            # Переводим в В_РАБОТЕ
            cursor.execute("UPDATE ai_task_runs SET state = 'В_РАБОТЕ' WHERE id = ?;", (task_id,))
            conn.commit()
            
            # Достаем промпт и эталон из шаблона
            cursor.execute("SELECT prompt, expected_result FROM ai_task_templates WHERE id = ?;", (template_id,))
            template_row = cursor.fetchone()
            
            if not template_row:
                cursor.execute("UPDATE ai_task_runs SET state = 'ОШИБКА', result_log = ? WHERE id = ?;", 
                               ("Шаблон не найден", task_id))
                conn.commit()
                conn.close()
                continue
                
            prompt, expected_result = template_row
            
            # 2. Выполняем задачу (Этап 1: выполнение промпта моделью)
            raw_result = execute_ai_model_call(model, prompt)
            
            cursor.execute("UPDATE ai_task_runs SET result_log = ?, state = 'НА_ПРОВЕРКЕ' WHERE id = ?;", 
                           (raw_result, task_id))
            conn.commit()
            
            # 3. Аудит и верификация (Этап 2: сравнение с эталоном)
            audit_prompt = f"""
            Проверь результат выполнения задачи.
            Промпт: {prompt}
            Фактический результат: {raw_result}
            Ожидаемый эталонный результат: {expected_result}
            
            Вердикт: если фактический результат соответствует ожиданиям, напиши 'ВЫПОЛНЕНО: [причина]'. Если нет, напиши 'ОШИБКА: [причина]'.
            """
            
            audit_result = execute_ai_model_call(model, audit_prompt)
            final_state = "ВЫПОЛНЕНО" if "ВЫПОЛНЕНО" in audit_result else "ОШИБКА"
            
            final_log = f"ФАКТ:\n{raw_result}\n\nАУДИТ:\n{audit_result}"
            
            cursor.execute("UPDATE ai_task_runs SET result_log = ?, state = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?;", 
                           (final_log, final_state, task_id))
            conn.commit()
            conn.close()
            
            logging.info(f"[AI Worker] Задача ID {task_id} завершена со статусом {final_state}.")
            
        except Exception as e:
            logging.error(f"[AI Worker Error]: {e}")
            try:
                conn.close()
            except:
                pass
            time.sleep(5)

def start_ai_worker_background(model):
    """Запуск воркера в отдельном потоке"""
    t = threading.Thread(target=run_ai_task_worker, args=(model,), daemon=True)
    t.start()
