# C:\ai_volya\volya_app.py
import os
import json
import uuid
import sqlite3
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response, Cookie
from fastapi.responses import HTMLResponse, JSONResponse
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

DB_PATH = "C:\\ai_volya\\volya_game.db"
MEMORY_WINDOW = 20

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    """Пытается распарсить JSON-ответ модели напрямую или извлечь из блока ```json ... ```."""
    cleaned = raw_reply.strip()
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

    return raw_reply, "html", ""

def verify_session_token(token: str):
    """Проверяет токен сессии в таблице players и возвращает имя игрока или None."""
    if not token:
        return None
    conn = get_db_connection()
    row = conn.execute("SELECT username FROM players WHERE session_token = ?", (token,)).fetchone()
    conn.close()
    return row["username"] if row else None

# --- REST ЭНДПОИНТЫ АВТОРИЗАЦИИ И НИТЕЙ ---

@app.get("/api/players")
async def api_get_players():
    """Возвращает список зарегистрированных вольных игроков."""
    conn = get_db_connection()
    rows = conn.execute("SELECT username, conscience_drops, bio FROM players").fetchall()
    conn.close()
    return [{"username": r["username"], "conscience_drops": r["conscience_drops"], "bio": r["bio"]} for r in rows]

@app.post("/api/login")
async def api_login(request: Request, response: Response):
    """Аутентификация по вольному имени с генерацией токена сессии."""
    try:
        body = await request.json()
        username = body.get("username", "").strip()
        if not username:
            return JSONResponse({"success": False, "error": "Не указано вольное имя."}, status_code=400)
        
        conn = get_db_connection()
        player = conn.execute("SELECT username FROM players WHERE username = ?", (username,)).fetchone()
        
        if not player:
            conn.execute(
                "INSERT INTO players (username, conscience_drops, status_id, bio) VALUES (?, 0, 1, ?)",
                (username, f"Вольный игрок {username}")
            )
        
        session_token = str(uuid.uuid4())
        conn.execute("UPDATE players SET session_token = ? WHERE username = ?", (session_token, username))
        conn.commit()
        conn.close()
        
        response.set_cookie(key="volya_session", value=session_token, httponly=False, max_age=30*24*60*60, samesite="lax")
        return {"success": True, "username": username, "token": session_token}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/threads")
async def api_get_threads(volya_session: str = Cookie(default=None)):
    """Возвращает список нитей текущего игрока."""
    username = verify_session_token(volya_session)
    if not username:
        return JSONResponse({"error": "Требуется авторизация"}, status_code=401)
    
    conn = get_db_connection()
    threads = conn.execute(
        "SELECT thread_id, title, created_at, updated_at FROM ai_threads WHERE username = ? ORDER BY created_at DESC",
        (username,)
    ).fetchall()
    conn.close()
    
    return [
        {
            "thread_id": t["thread_id"],
            "title": t["title"],
            "created_at": t["created_at"],
            "updated_at": t["updated_at"]
        } for t in threads
    ]

@app.post("/api/threads")
async def api_create_thread(request: Request, volya_session: str = Cookie(default=None)):
    """Создает новую нить диалога для игрока."""
    username = verify_session_token(volya_session)
    if not username:
        return JSONResponse({"error": "Требуется авторизация"}, status_code=401)
    
    try:
        body = await request.json()
        title = body.get("title", "Новая нить воли").strip()
        thread_id = f"thread_{username}_{uuid.uuid4().hex[:8]}"
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO ai_threads (thread_id, username, title, created_at, updated_at) VALUES (?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))",
            (thread_id, username, title)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "thread_id": thread_id, "title": title}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.delete("/api/threads/{thread_id}")
async def api_delete_thread(thread_id: str, volya_session: str = Cookie(default=None)):
    """Удаляет нить диалога и ее сообщения."""
    username = verify_session_token(volya_session)
    if not username:
        return JSONResponse({"error": "Требуется авторизация"}, status_code=401)
    
    conn = get_db_connection()
    t = conn.execute("SELECT thread_id FROM ai_threads WHERE thread_id = ? AND username = ?", (thread_id, username)).fetchone()
    if not t:
        conn.close()
        return JSONResponse({"error": "Нить не найдена или нет прав"}, status_code=403)
    
    conn.execute("DELETE FROM ai_threads WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM chat_logs WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM ai_mem_flows WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

@app.get("/")
async def get_interface():
    """Отдает интерфейсную страницу вольного приложения."""
    with open("C:\\ai_volya\\index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# --- WEBSOCKET С УЧЕТОМ ТОКЕНА И ТРЕХ НИТЕЙ ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Асинхронный вольный канал обмена репликами и командами рантайма в формате JSON."""
    # Получаем токен из query параметров или куки
    query_token = websocket.query_params.get("token")
    
    cookie_header = websocket.headers.get("cookie", "")
    session_token = query_token
    if not session_token:
        for cookie in cookie_header.split(";"):
            if "volya_session=" in cookie:
                session_token = cookie.split("volya_session=")[1].strip()
                break
            
    username = verify_session_token(session_token)
    if not username:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Требуется авторизация вольного игрока."
        }, ensure_ascii=False))
        await websocket.close()
        return

    await websocket.accept()
    logging.info(f"[СОКЕТ] Подключен вольный игрок: {username}")

    conn = get_db_connection()
    active_thread = conn.execute(
        "SELECT thread_id FROM ai_threads WHERE username = ? ORDER BY created_at DESC LIMIT 1",
        (username,)
    ).fetchone()
    
    if active_thread:
        thread_id = active_thread["thread_id"]
    else:
        thread_id = f"thread_{username}_default"
        conn.execute(
            "INSERT OR IGNORE INTO ai_threads (thread_id, username, title, created_at, updated_at) VALUES (?, ?, 'Священный Баньян', datetime('now', 'localtime'), datetime('now', 'localtime'))",
            (thread_id, username)
        )
        conn.commit()
    conn.close()

    try:
        while True:
            raw_incoming = await websocket.receive_text()
            try:
                incoming_data = json.loads(raw_incoming)
                msg_type = incoming_data.get("type", "message")
                
                if msg_type == "switch_thread":
                    new_thread_id = incoming_data.get("thread_id")
                    if new_thread_id:
                        conn = get_db_connection()
                        t_check = conn.execute("SELECT thread_id FROM ai_threads WHERE thread_id = ? AND username = ?", (new_thread_id, username)).fetchone()
                        conn.close()
                        if t_check:
                            thread_id = new_thread_id
                            visible_history = get_visible_history_from_db(thread_id, MEMORY_WINDOW)
                            formatted_history = []
                            last_canvas_data = ""
                            for h_role, h_content in visible_history:
                                c_txt, c_type, c_cont = parse_agent_json_reply(h_content)
                                if h_role == "assistant" and c_cont: 
                                    last_canvas_data = c_cont
                                formatted_history.append({"role": h_role, "text": c_txt})
                                
                            await websocket.send_text(json.dumps({
                                "type": "restore",
                                "thread_id": thread_id,
                                "history": formatted_history,
                                "chat_text": "",
                                "canvas_type": "html",
                                "canvas_content": last_canvas_data
                            }, ensure_ascii=False))
                            continue
                
                user_message = incoming_data.get("chat_text", "").strip() or incoming_data.get("message", "").strip()
            except json.JSONDecodeError:
                user_message = raw_incoming.strip()

            if not user_message:
                continue

            save_message_to_db(thread_id, "user", user_message)
            
            try:
                mem_flow = get_memory_flow(thread_id)
                memory_prefix = [("system", f"Долгосрочная память (Саммари прошлых эпох нити):\n{mem_flow}")]

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
            
            conn = get_db_connection()
            conn.execute("UPDATE ai_threads SET updated_at = datetime('now', 'localtime') WHERE thread_id = ?", (thread_id,))
            conn.commit()
            conn.close()

            try:
                check_and_summarize(thread_id, model, threshold=MEMORY_WINDOW)
            except Exception:
                pass

            await websocket.send_text(json.dumps({
                "type": "reply",
                "thread_id": thread_id,
                "chat_text": chat_text,
                "canvas_type": canvas_type,
                "canvas_content": canvas_content
            }, ensure_ascii=False))
    except WebSocketDisconnect:
        logging.info(f"[СОКЕТ] Вольный игрок {username} отключился.")
    except Exception as e:
        logging.error(f"[СОКЕТ] Ошибка сессии веб-сокетов вольного рантайма: {str(e)}")
