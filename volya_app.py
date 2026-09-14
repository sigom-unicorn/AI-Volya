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
from eira_mem_flow import get_memory_flow, check_and_summarize

# 🧵 ИМПОРТ ФОНОВОГО ВОРКЕРА «НИТИ ЭЙРЫ»
from ai_task import start_ai_worker_background

app = FastAPI()

# Привязываемся к папке tmp для раздачи тяжелых файлов данных вольного рантайма
TMP_DIR = "C:\\ai_volya\\tmp"
os.makedirs(TMP_DIR, exist_ok=True)
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite", 
#    temperature=0.2,
    max_output_tokens=30000
)

# 🧵 ЗАПУСК ФОНОВОГО ВОРКЕРА «НИТИ ЭЙРЫ» ПРИ СТАРТЕ РАНТАЙМА (теперь внутри ai_task воркер использует свою выделенную легковесную модель gemini-2.5-flash-lite)
try:
    start_ai_worker_background()
    logging.info("[AI Worker] Фоновый поток 'Нити Эйры' успешно запущен с легковесной моделью.")
except Exception as e:
    logging.error(f"[AI Worker Error при старте]: {e}")

# Единственная глобальная сессия вольного рантайма игры Воля
DEFAULT_THREAD_ID = "sigom_eira_v4_1"

# Единая константа глубины памяти и порога сжатия
MEMORY_WINDOW = 20

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
    """Асинхронный вольный канал обмена репликами и командами рантайма в формате JSON."""
    await websocket.accept()
    thread_id = DEFAULT_THREAD_ID
    logging.info(f"[СОКЕТ] Подключена сессия вольного рантайма")
    
    # Извлекаем окно последних сообщений для удержания контекста беседы
    visible_history = get_visible_history_from_db(thread_id, MEMORY_WINDOW)
    
    if len(visible_history) == 0:
        # Первичный вольный запуск
        dynamic_prompt = build_eira_system_prompt()
        agent_blueprint = create_react_agent(model, all_tools, prompt=dynamic_prompt)
        initial_prompt = "Системный триггер: Сессия возобновлена. Попроси представиться вольного игрока, прочти о нем в таблице players и поприветствуй" 
        
        response = await agent_blueprint.ainvoke({"messages": [("user", initial_prompt)]})
        raw_reply = extract_clean_text(response["messages"][-1].content)
        
        parts = raw_reply.split("|CANVAS|")
        reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
        canvas_data = parts[1].strip() if len(parts) > 1 else ""
        
        # Передаем структурированный JSON с явно разделенными полями (без костыльного автоопределения)
        await websocket.send_text(json.dumps({
            "type": "reply",
            "chat_text": reply_text,
            "canvas_type": "html",
            "canvas_content": canvas_data
        }, ensure_ascii=False))
    else:
        # Восстановление истории из БД
        formatted_history = []
        last_canvas_data = ""
        for role, content in visible_history:
            parts = content.split("|CANVAS|")
            txt = parts[0].strip() if len(parts) > 0 else content
            if role == "assistant" and len(parts) > 1: 
                last_canvas_data = parts[1].strip()
            formatted_history.append({"role": role, "text": txt})
            
        await websocket.send_text(json.dumps({
            "type": "restore",
            "history": formatted_history,
            "chat_text": "",
            "canvas_type": "html",
            "canvas_content": last_canvas_data
        }, ensure_ascii=False))

    try:
        while True:
            # Принимаем JSON-пакет или текстовое сообщение от вольного игрока
            raw_incoming = await websocket.receive_text()
            try:
                incoming_data = json.loads(raw_incoming)
                user_message = incoming_data.get("chat_text", "").strip() or incoming_data.get("message", "").strip()
            except json.JSONDecodeError:
                user_message = raw_incoming.strip()

            if not user_message:
                continue

            save_message_to_db(thread_id, "user", user_message)
            
            # 1. Загружаем долгосрочную память
            mem_flow = get_memory_flow(thread_id)
            memory_prefix = [("system", f"Долгосрочная память (Саммари прошлых эпох нити):\n{mem_flow}")]

            # 2. Собираем живые логи
            db_history = get_visible_history_from_db(thread_id, MEMORY_WINDOW)
            langgraph_messages = memory_prefix + [
                ("user" if h_role == "user" else "assistant", h_content) 
                for h_role, h_content in db_history
            ]
            
            dynamic_prompt = build_eira_system_prompt()
            agent_blueprint = create_react_agent(model, all_tools, prompt=dynamic_prompt)
            response = await agent_blueprint.ainvoke({"messages": langgraph_messages})
            
            raw_reply = extract_clean_text(response["messages"][-1].content)
            save_message_to_db(thread_id, "assistant", raw_reply)
            
            # 3. Фоновый триггер сжатия памяти
            check_and_summarize(thread_id, model, threshold=MEMORY_WINDOW)
            
            parts = raw_reply.split("|CANVAS|")
            reply_text = parts[0].strip() if len(parts) > 0 else raw_reply
            canvas_data = parts[1].strip() if len(parts) > 1 else ""
            
            # Определяем тип холста
            c_type = "html"
            if canvas_data.startswith("SCRIPT:") or canvas_data.startswith("script:"):
                c_type = "script"
                canvas_data = canvas_data.split(":", 1)[1].strip()
            elif not canvas_data.startswith("<") and canvas_data != "":
                c_type = "text"

            # Отправляем ответ в строгом JSON-формате
            await websocket.send_text(json.dumps({
                "type": "reply",
                "chat_text": reply_text,
                "canvas_type": c_type,
                "canvas_content": canvas_data.strip()
            }, ensure_ascii=False))
    except Exception as e:
        logging.error(f"[СОКЕТ] Ошибка сессии веб-сокетов вольного рантайма: {str(e)}")
