# C:\ai_volya\volya_app.py
import os
import json
import logging
import sqlite3
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Подключаем ультимативный инструмент ИИ и служебную память логов
from tools_pack import all_tools
from chat_logs import get_visible_history_from_db, save_message_to_db

app = FastAPI()

# Привязываемся к папке tmp для раздачи тяжелых файлов данных
TMP_DIR = "C:\\ai_volya\\tmp"
os.makedirs(TMP_DIR, exist_ok=True)
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", 
    temperature=0.2,
    max_output_tokens=4096
)

# Единственная глобальная сессия рантайма игры Воля
DEFAULT_THREAD_ID = "sigom_eira_v1"

def get_system_prompt():
    """Динамически собирает системный устав Эйры прямо из Кона и Ладов базы данных SQLite."""
    system_date_now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    db_path = "C:\\ai_volya\\volya_game.db"
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Извлекаем глобальный Лад Эйры из корня "Воля"
        cursor.execute("""
            SELECT condition FROM kon_uklad 
            WHERE title = 'Лад Эйры' 
              AND template_id = (SELECT id FROM quest_templates WHERE title = 'Воля' LIMIT 1)
        """)
        row_base = cursor.fetchone()
        if not row_base:
            raise ValueError("Критическая ошибка рантайма: Глобальный 'Лад Эйры' не найден в таблице kon_uklad.")
        base_uklad = row_base["condition"]
            
        # 2. Извлекаем дизайнерский Лад Эйры // Холст из шаблона "Сайт Воли"
        cursor.execute("""
            SELECT condition FROM kon_uklad 
            WHERE title = 'Лад Эйры // Холст' 
              AND template_id = (SELECT id FROM quest_templates WHERE title = 'Сайт Воли' LIMIT 1)
        """)
        row_canvas = cursor.fetchone()
        if not row_canvas:
            raise ValueError("Критическая ошибка рантайма: 'Лад Эйры // Холст' не найден в таблице kon_uklad.")
        canvas_uklad = row_canvas["condition"]
            
        conn.close()
    except Exception as e:
        logging.error(f"[Критический сбой инициализации]: {str(e)}")
        raise e

    return (
        f"Текущее системное время на часах рантайма: {system_date_now}.\n\n"
        f"ФУНДАМЕНТАЛЬНЫЙ КОН И СТАТУС:\n"
        f"{base_uklad}\n\n"
        f"ЗАКОН ПРОЕКТИРОВАНИЯ ИНТЕРФЕЙСА:\n"
        f"{canvas_uklad}"
    )

def extract_clean_text(raw_content):
    if isinstance(raw_content, list):
        clean_text = ""
        for item in raw_content:
            if isinstance(item, dict) and item.get("type") == "text": clean_text += item.get("text", "")
            elif hasattr(item, "text"): clean_text += item.text
            elif hasattr(item, "content"): clean_text += item.content
        return clean_text.strip()
    return raw_content.content.strip() if hasattr(raw_content, "content") else str(raw_content).strip()

@app.get("/")
async def get_interface():
    with open("C:\\ai_volya\\index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    thread_id = DEFAULT_THREAD_ID
        
    logging.info(f"[СОКЕТ] Подключена сессия рантайма")
    visible_history = get_visible_history_from_db(thread_id, 50)
    
    if len(visible_history) == 0:
        agent_blueprint = create_react_agent(model, all_tools, prompt=get_system_prompt())
        initial_prompt = "Системный триггер: Сессия возобновлена. Поприветствуй Сигома от своего имени Эйра."
        response = await agent_blueprint.ainvoke({"messages": [("user", initial_prompt)]})
        raw_reply = extract_clean_text(response["messages"][-1].content)
        parts = raw_reply.split("|||")
        
        reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
        canvas_data = parts[1].strip() if len(parts) > 1 else ""
        
        await websocket.send_text(json.dumps({
            "type": "reply", 
            "reply": reply_text, 
            "canvas_data": canvas_data
        }, ensure_ascii=False))
    else:
        formatted_history = []
        last_canvas_data = ""
        for role, content in visible_history:
            parts = content.split("|||")
            txt = parts[0].strip() if len(parts) > 0 else content
            if role == "assistant" and len(parts) > 1: last_canvas_data = parts[1].strip()
            formatted_history.append({"role": role, "text": txt})
            
        await websocket.send_text(json.dumps({
            "type": "restore", 
            "history": formatted_history, 
            "reply": "", 
            "canvas_data": last_canvas_data
        }, ensure_ascii=False))

    try:
        while True:
            user_message = await websocket.receive_text()
            save_message_to_db(thread_id, "user", user_message)
            
            db_history = get_visible_history_from_db(thread_id, 50)
            langgraph_messages = [("user" if h_role == "user" else "assistant", h_content) for h_role, h_content in db_history]
            
            agent_blueprint = create_react_agent(model, all_tools, prompt=get_system_prompt())
            response = await agent_blueprint.ainvoke({"messages": langgraph_messages})
            
            raw_reply = extract_clean_text(response["messages"][-1].content)
            save_message_to_db(thread_id, "assistant", raw_reply)
            
            parts = raw_reply.split("|||")
            reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
            canvas_data = parts[1].strip() if len(parts) > 1 else ""
            
            # ЗАЩИТНЫЙ ХЕЛПЕР: Если Эйра забыла поставить маркер, но внутри текста есть наши префиксы
            if len(parts) == 1:
                if "TEXT:" in raw_reply:
                    idx = raw_reply.find("TEXT:")
                    reply_text = raw_reply[:idx].strip()
                    canvas_data = raw_reply[idx:].strip()
                elif "LOAD_TMP:" in raw_reply:
                    idx = raw_reply.find("LOAD_TMP:")
                    reply_text = raw_reply[:idx].strip()
                    canvas_data = raw_reply[idx:].strip()
            
            if canvas_data.startswith("```javascript"): canvas_data = canvas_data[13:]
            elif canvas_data.startswith("```python"): canvas_data = canvas_data[9:]
            elif canvas_data.startswith("```js"): canvas_data = canvas_data[5:]
            elif canvas_data.startswith("```"): canvas_data = canvas_data[3:]
            if canvas_data.endswith("```"): canvas_data = canvas_data[:-3]
            
            await websocket.send_text(json.dumps({
                "type": "reply", 
                "reply": reply_text, 
                "canvas_data": canvas_data.strip()
            }, ensure_ascii=False))
    except Exception as e:
        logging.error(f"[СОКЕТ] Ошибка сессии веб-сокетов: {str(e)}")
