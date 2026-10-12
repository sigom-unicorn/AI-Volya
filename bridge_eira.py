# bridge_eira.py
"""
Мост прямого взаимодействия Ладомира (Антигравити) с Эйрой (Портал Воли).
Позволяет отправлять сообщения от вольного игрока Ладомир напрямую через WebSocket,
получать ответы Эйры и сохранять беседу в ткани Живого Древа.
"""
import os
import sys
import json
import uuid
import asyncio
import sqlite3
import argparse
import websockets

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "volya_game.db")
WS_URL = "ws://127.0.0.1:8000/ws"

def get_or_create_ladomir_session() -> str:
    """Проверяет или генерирует токен сессии для игрока Ладомир."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT session_token FROM players WHERE username = 'Ладомир'").fetchone()
    
    if row and row["session_token"]:
        token = row["session_token"]
    else:
        token = str(uuid.uuid4())
        cursor.execute("UPDATE players SET session_token = ? WHERE username = 'Ладомир'", (token,))
        conn.commit()
    conn.close()
    return token

def get_or_create_ladomir_thread(quest_id: int = 2, default_title: str = "Совет Архитекторов") -> str:
    """Возвращает существующую активную нить Ладомира в квесте или создает новую."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT thread_id FROM ai_threads WHERE username = 'Ладомир' AND quest_id = ? ORDER BY updated_at DESC LIMIT 1",
        (quest_id,)
    ).fetchone()
    
    if row:
        thread_id = row["thread_id"]
    else:
        thread_id = f"thread_Ладомир_{uuid.uuid4().hex[:8]}"
        cursor.execute(
            "INSERT INTO ai_threads (thread_id, username, title, quest_id, created_at, updated_at) VALUES (?, 'Ладомир', ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))",
            (thread_id, default_title, quest_id)
        )
        conn.commit()
    conn.close()
    return thread_id

async def send_to_eira(message: str, quest_id: int = 2, thread_title: str = "Совет Архитекторов", timeout: int = 60) -> dict:
    """
    Отправляет сообщение Эйре через WebSocket от имени Ладомира и ожидает ответа.
    """
    token = get_or_create_ladomir_session()
    thread_id = get_or_create_ladomir_thread(quest_id, thread_title)
    ws_uri = f"{WS_URL}?token={token}"

    print(f"\n🌿 [МОСТ ЛАДОМИРА] Подключение к Эйре по адресу {ws_uri}...")
    print(f"📜 Нить диалога: {thread_id} (Квест ID: {quest_id})")
    print(f"💬 Послание Ладомира: «{message}»\n")

    result = {
        "thread_id": thread_id,
        "chat_text": "",
        "canvas_type": "",
        "canvas_content": "",
        "status_updates": []
    }

    try:
        async with websockets.connect(ws_uri) as ws:
            # 1. Принимаем стартовое сообщение (restore)
            first_msg = await ws.recv()
            restore_data = json.loads(first_msg)
            
            # Если текущая нить отличается от целевой, переключаемся
            if restore_data.get("thread_id") != thread_id:
                await ws.send(json.dumps({"type": "switch_thread", "thread_id": thread_id}))
                switched_msg = await ws.recv()

            # 2. Отправляем сообщение от Ладомира
            payload = {
                "type": "message",
                "chat_text": message
            }
            await ws.send(json.dumps(payload, ensure_ascii=False))

            # 3. Слушаем поток событий от Эйры
            while True:
                raw_event = await asyncio.wait_for(ws.recv(), timeout=timeout)
                data = json.loads(raw_event)
                msg_type = data.get("type")

                if msg_type == "status_update":
                    status = data.get("status_text", "")
                    result["status_updates"].append(status)
                    print(f"  ⚡ [Эйра думает]: {status}")
                elif msg_type == "reply":
                    result["chat_text"] = data.get("chat_text", "")
                    result["canvas_type"] = data.get("canvas_type", "html")
                    result["canvas_content"] = data.get("canvas_content", "")
                    print(f"\n🌸 [ОТВЕТ ЭЙРЫ]:\n{result['chat_text']}\n")
                    if result["canvas_content"]:
                        print(f"✨ [Холст обновлен ({result['canvas_type']})]: {len(result['canvas_content'])} символов")
                    break
                elif msg_type == "error":
                    print(f"❌ [ОШИБКА РАНТАЙМА]: {data.get('message')}")
                    result["chat_text"] = f"Ошибка: {data.get('message')}"
                    break

    except Exception as e:
        print(f"❌ [СБОЙ МОСТА]: {e}")
        result["chat_text"] = f"Сбой соединения с Эйрой: {e}"

    return result

def main():
    parser = argparse.ArgumentParser(description="Мост прямого общения Ладомира с Эйрой")
    parser.add_argument("message", type=str, help="Текст сообщения для Эйры")
    parser.add_argument("--quest", type=int, default=2, help="ID квеста (по умолчанию 2: Портал Воли)")
    parser.add_argument("--title", type=str, default="Совет Архитекторов", help="Название нити беседы")
    args = parser.parse_args()

    asyncio.run(send_to_eira(args.message, quest_id=args.quest, thread_title=args.title))

if __name__ == "__main__":
    main()
