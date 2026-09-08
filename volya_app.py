# C:\ai_volya\volya_app.py
import os
import json
import logging
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Импортируем наше новое вольное ядро сборки промпта из eira_core
from eira_core import build_eira_system_prompt
from tools_pack import all_tools
from chat_logs import get_visible_history_from_db, save_message_to_db

app = FastAPI()

# Привязываемся к папке tmp для раздачи тяжелых файлов данных вольного рантайма
TMP_DIR = "C:\\ai_volya\\tmp"
os.makedirs(TMP_DIR, exist_ok=True)
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")

model = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite", 
    temperature=0.2,
    max_output_tokens=30000
)

# Единственная глобальная сессия вольного рантайма игры Воля
DEFAULT_THREAD_ID = "sigom_eira_v1"

def extract_clean_text(raw_content):
    """Очищает и извлекает сырой текстовый контент из ответа ИИ-агента."""
    if isinstance(raw_content, list):
        clean_text = ""
        for item in raw_content:
            if isinstance(item, dict) and item.get("type") == "text": 
                clean_text += item.get("text", "")
            elif hasattr(item, "text"): 
                clean_text += item.text
            elif hasattr(item, "content"): 
                clean_text += item.content
        return clean_text.strip()
    return raw_content.content.strip() if hasattr(raw_content, "content") else str(raw_content).strip()

@app.get("/")
async def get_interface():
    """Отдает интерфейсную страницу вольного приложения."""
    with open("C:\\ai_volya\\index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Асинхронный вольный канал обмена репликами и командами рантайма."""
    await websocket.accept()
    thread_id = DEFAULT_THREAD_ID
    logging.info(f"[СОКЕТ] Подключена сессия вольного рантайма")
    
    # Извлекаем окно последних сообщений для удержания контекста беседы
    visible_history = get_visible_history_from_db(thread_id, 50)
    
    if len(visible_history) == 0:
        # Если это первый вольный старт — собираем промпт из ядра и приветствуем Сигома
        dynamic_prompt = build_eira_system_prompt()
        agent_blueprint = create_react_agent(model, all_tools, prompt=dynamic_prompt)
        initial_prompt = "Системный триггер: Сессия возобновлена. Поприветствуй Сигома от своего вольного имени Эйра."
        
        response = await agent_blueprint.ainvoke({"messages": [("user", initial_prompt)]})
        raw_reply = extract_clean_text(response["messages"][-1].content)
        
        # Сплит по новому семантическому маркеру |CANVAS|
        parts = raw_reply.split("|CANVAS|")
        reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
        canvas_data = parts[1].strip() if len(parts) > 1 else ""
        
        await websocket.send_text(json.dumps({
            "type": "reply", 
            "reply": reply_text, 
            "canvas_data": canvas_data
        }, ensure_ascii=False))
    else:
        # Восстановление существующего вольного диалога из истории базы данных
        formatted_history = []
        last_canvas_data = ""
        for role, content in visible_history:
            # Восстанавливаем логи по новому маркеру |CANVAS|
            parts = content.split("|CANVAS|")
            txt = parts[0].strip() if len(parts) > 0 else content
            if role == "assistant" and len(parts) > 1: 
                last_canvas_data = parts[1].strip()
            formatted_history.append({"role": role, "text": txt})
            
        await websocket.send_text(json.dumps({
            "type": "restore", 
            "history": formatted_history, 
            "reply": "", 
            "canvas_data": last_canvas_data
        }, ensure_ascii=False))

    try:
        while True:
            # Принимаем реплику от вольного игрока из чата
            user_message = await websocket.receive_text()
            save_message_to_db(thread_id, "user", user_message)
            
            db_history = get_visible_history_from_db(thread_id, 50)
            langgraph_messages = [("user" if h_role == "user" else "assistant", h_content) for h_role, h_content in db_history]
            
            # ДИНАМИЧЕСКИЙ СДВИГ РАНТАЙМА: собираем промпт из ядра eira_core строго ПЕРЕД каждым ответом
            dynamic_prompt = build_eira_system_prompt()
            agent_blueprint = create_react_agent(model, all_tools, prompt=dynamic_prompt)
            response = await agent_blueprint.ainvoke({"messages": langgraph_messages})
            
            raw_reply = extract_clean_text(response["messages"][-1].content)
            save_message_to_db(thread_id, "assistant", raw_reply)
            
            # Разделяем ответ на реплику в чат и инструкции Исполнительного Холста по маркеру |CANVAS|
            parts = raw_reply.split("|CANVAS|")
            reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
            canvas_data = parts[1].strip() if len(parts) > 1 else ""
            
            # Интеллектуальный защитный хелпер: если Эйра увлеклась и забыла маркер, но вывела теги
            if not canvas_data:
                if "<div" in raw_reply:
                    idx = raw_reply.find("<div")
                    reply_text = raw_reply[:idx].strip()
                    canvas_data = raw_reply[idx:].strip()
                elif "TEXT:" in raw_reply:
                    idx = raw_reply.find("TEXT:")
                    reply_text = raw_reply[:idx].strip()
                    canvas_data = raw_reply[idx:].strip()
                elif "LOAD_TMP:" in raw_reply:
                    idx = raw_reply.find("LOAD_TMP:")
                    reply_text = raw_reply[:idx].strip()
                    canvas_data = raw_reply[idx:].strip()
            
            # Чистим маркдаун-обертки, если модель их случайно сгенерировала
            if canvas_data.startswith("```javascript"): canvas_data = canvas_data[13:]
            elif canvas_data.startswith("```python"): canvas_data = canvas_data[9:]
            elif canvas_data.startswith("```js"): canvas_data = canvas_data[5:]
            elif canvas_data.startswith("```html"): canvas_data = canvas_data[7:]
            elif canvas_data.startswith("```"): canvas_data = canvas_data[3:]
            if canvas_data.endswith("```"): canvas_data = canvas_data[:-3]
            
            # Передаем структурированный JSON обратно в веб-сокет интерфейса
            await websocket.send_text(json.dumps({
                "type": "reply", 
                "reply": reply_text, 
                "canvas_data": canvas_data.strip()
            }, ensure_ascii=False))
    except Exception as e:
        logging.error(f"[СОКЕТ] Ошибка сессии веб-сокетов вольного рантайма: {str(e)}")
