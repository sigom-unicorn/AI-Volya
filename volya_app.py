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

# Импортируем наше вольное ядро сборки промпта из eira_core
from eira_core import build_eira_system_prompt
from tools_pack import all_tools
from chat_logs import get_visible_history_from_db, save_message_to_db
from eira_mem_flow import get_memory_flow, check_and_summarize

# 🧵 ИМПОРТ ФОНОВОГО ВОРКЕРА «НИТИ ЭЙРЫ»
from ai_task import start_ai_worker_background

app = FastAPI()

# Привязываемся к папке images для раздачи локальных картинок
IMAGES_DIR = "C:\\ai_volya\\images"
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Привязываемся к папке tmp для раздачи файлов данных вольного рантайма
TMP_DIR = "C:\\ai_volya\\tmp"
os.makedirs(TMP_DIR, exist_ok=True)
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")

model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite", 
    max_output_tokens=30000
)

# 🧵 ЗАПУСК ФОНОВОГО ВОРКЕРА ПРИ СТАРТЕ РАНТАЙМА
try:
    start_ai_worker_background()
    logging.info("[AI Worker] Фоновый поток 'Нити Эйры' успешно запущен.")
except Exception as e:
    logging.error(f"[AI Worker Error при старте]: {e}")

# Единственная глобальная сессия вольного рантайма игры Воля
DEFAULT_THREAD_ID = "sigom_eira_v4_2"
MEMORY_WINDOW = 20

def extract_clean_text(raw_content):
    """Извлекает сырой текстовый контент из ответа ИИ-агента."""
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

def parse_agent_json_reply(raw_reply: str):
    """Пытается распарсить JSON-ответ модели напрямую или извлечь из блока ```json ... ```.
    При неудаче формирует fallback JSON с текстом сообщения и пустым холстом."""
    cleaned = raw_reply.strip()
    # Убираем обертку маркдоров кода при наличии
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) > 2:
            cleaned = "\n".join(lines[1:-1]).strip()
        elif len(lines) == 2:
            cleaned = lines[1].strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            chat_text = str(data.get("chat_text", "") or data.get("message", "") or "")
            canvas_content = str(data.get("canvas_content", "") or "")
            canvas_type = str(data.get("canvas_type", "html") or "html")
            return chat_text, canvas_type, canvas_content
    except json.JSONDecodeError:
        pass

    # Если модель вернула обычный текст без JSON, отдаем весь текст в чат, а холст оставляем пустым
    return raw_reply, "html", ""

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
    
    visible_history = get_visible_history_from_db(thread_id, MEMORY_WINDOW)
    
    if len(visible_history) == 0:
        # Первичный вольный запуск
        try:
            dynamic_prompt = build_eira_system_prompt()
            agent_blueprint = create_react_agent(model, all_tools, prompt=dynamic_prompt)
            initial_prompt = "Системный триггер: Сессия возобновлена. Поприветствуй вольного игрока Сигома."
            
            response = await agent_blueprint.ainvoke({"messages": [("user", initial_prompt)]})
            raw_reply = extract_clean_text(response["messages"][-1].content)
            chat_text, canvas_type, canvas_content = parse_agent_json_reply(raw_reply)
        except Exception as e:
            logging.error(f"[INIT ERROR] {e}")
            chat_text, canvas_type, canvas_content = "Эйра не может обработать ваш запрос", "html", ""
        
        await websocket.send_text(json.dumps({
            "type": "reply",
            "chat_text": chat_text,
            "canvas_type": canvas_type,
            "canvas_content": canvas_content
        }, ensure_ascii=False))
    else:
        # Восстановление истории из БД
        formatted_history = []
        last_canvas_data = ""
        for role, content in visible_history:
            c_txt, c_type, c_cont = parse_agent_json_reply(content)
            if role == "assistant" and c_cont: 
                last_canvas_data = c_cont
            formatted_history.append({"role": role, "text": c_txt})
            
        await websocket.send_text(json.dumps({
            "type": "restore",
            "history": formatted_history,
            "chat_text": "",
            "canvas_type": "html",
            "canvas_content": last_canvas_data
        }, ensure_ascii=False))

    try:
        while True:
            raw_incoming = await websocket.receive_text()
            try:
                incoming_data = json.loads(raw_incoming)
                user_message = incoming_data.get("chat_text", "").strip() or incoming_data.get("message", "").strip()
            except json.JSONDecodeError:
                user_message = raw_incoming.strip()

            if not user_message:
                continue

            save_message_to_db(thread_id, "user", user_message)
            
            try:
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
                chat_text, canvas_type, canvas_content = parse_agent_json_reply(raw_reply)
            except Exception as model_err:
                logging.error(f"[MODEL ERROR / LIMIT EXCEEDED] {model_err}")
                chat_text = "Эйра не может обработать ваш запрос"
                canvas_type = "html"
                canvas_content = "<div style='padding:15px; text-align:center; color:#ff6b6b;'><h3>⚠️ Сбой обработки запроса</h3><p>Модель временно недоступна или исчерпан лимит.</p></div>"
                raw_reply = json.dumps({
                    "type": "reply",
                    "chat_text": chat_text,
                    "canvas_type": canvas_type,
                    "canvas_content": canvas_content
                }, ensure_ascii=False)

            save_message_to_db(thread_id, "assistant", raw_reply)
            
            # 3. Фоновый триггер сжатия памяти
            try:
                check_and_summarize(thread_id, model, threshold=MEMORY_WINDOW)
            except Exception:
                pass

            await websocket.send_text(json.dumps({
                "type": "reply",
                "chat_text": chat_text,
                "canvas_type": canvas_type,
                "canvas_content": canvas_content
            }, ensure_ascii=False))
    except Exception as e:
        logging.error(f"[СОКЕТ] Ошибка сессии веб-сокетов вольного рантайма: {str(e)}")
