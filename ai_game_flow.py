import os
import sqlite3
import datetime
import json
import ast
import traceback
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI

DB_PATH = "volya_game.db"

class AIGameFlowState(TypedDict):
    thread_id: str
    messages: List[Any]
    system_prompt: str
    tools: List[Any]
    llm_reply: str
    chat_text: str
    canvas_type: str
    canvas_content: str
    validation_status: str
    retry_count: int
    validation_error: str

def log_to_db(thread_id: str, step_name: str, status: str, details: str):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cursor = conn.cursor()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO graph_log (thread_id, step_name, status, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, step_name, status, details, now)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Graph Log Error]: {e}")

def safe_parse_json(text: str) -> Dict[str, Any]:
    """Строгая проверка и парсинг JSON ответа."""
    if not isinstance(text, str):
        text = str(text or "")
        
    cleaned = text.strip()
    
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # 1. Пробуем стандартный json.loads
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # 2. Пробуем ast.literal_eval (на случай одинарных кавычек)
    try:
        data = ast.literal_eval(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    raise ValueError("Не удалось распарсить валидный JSON-словарь из ответа")

async def generator_node(state: AIGameFlowState) -> Dict[str, Any]:
    thread_id = state.get("thread_id", "unknown") if isinstance(state, dict) else "unknown"
    retry_count = state.get("retry_count", 0) if isinstance(state, dict) else 0
    
    log_to_db(thread_id, "generator_node", "start", f"Запуск агента (попытка {retry_count + 1})")
    
    try:
        messages = state.get("messages", []) if isinstance(state, dict) else []
        system_prompt = state.get("system_prompt", "") if isinstance(state, dict) else ""
        tools = state.get("tools", []) if isinstance(state, dict) else []
        validation_error = state.get("validation_error", "") if isinstance(state, dict) else ""

        current_messages = list(messages)
        json_strict_rule = "\n\nВАЖНО: Твой финальный ответ ДОЛЖЕН быть строго JSON-объектом формата: {\"chat_text\": \"...\", \"canvas_content\": \"...\", \"canvas_type\": \"html\"}. Никаких иных обёрток!"
        
        if isinstance(system_prompt, str):
            system_prompt += json_strict_rule

        if validation_error and retry_count > 0:
            current_messages.append(("user", f"[Системное требование]: Произошла ошибка парсинга: {validation_error}. Верни ответ strictly в JSON!"))

        model = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            max_output_tokens=30000,
            temperature=0.7
        )

        agent = create_react_agent(model, tools, prompt=system_prompt)
        response = await agent.ainvoke({"messages": current_messages})

        final_messages = response.get("messages", [])
        last_msg = final_messages[-1] if final_messages else ""

        # Извлекаем чистую строку из атрибута content
        if hasattr(last_msg, "content"):
            reply_content = last_msg.content
            # Если content вернулся как список блоков [{'type': 'text', 'text': '...'}]
            if isinstance(reply_content, list):
                reply_content = "".join([
                    block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                    for block in reply_content
                ])
        else:
            reply_content = str(last_msg)

        return {
            "llm_reply": str(reply_content),
            "retry_count": retry_count + 1
        }
    except Exception as e:
        tb = traceback.format_exc()
        error_msg = f"[ОШИБКА В generator_node]: {type(e).__name__}: {str(e)}\nTraceback:\n{tb}"
        log_to_db(thread_id, "generator_node", "CRASH", error_msg)
        print(error_msg)
        return {
            "llm_reply": f"Ошибка генерации: {str(e)}",
            "retry_count": retry_count + 1,
            "validation_status": "failed",
            "validation_error": error_msg
        }

async def check_and_parse_json_reply_node(state: Any) -> Dict[str, Any]:
    if isinstance(state, dict):
        thread_id = state.get("thread_id", "unknown")
        llm_reply = str(state.get("llm_reply", ""))
    else:
        llm_reply = str(state or "")
        thread_id = "unknown"

    log_to_db(thread_id, "check_and_parse_json_reply_node", "start", "Запуск парсинга ответа.")
    
    try:
        parsed = safe_parse_json(llm_reply)
        
        chat_text = parsed.get("chat_text") or parsed.get("message") or ""
        canvas_content = parsed.get("canvas_content") or ""
        canvas_type = parsed.get("canvas_type", "html") or "html"

        log_to_db(thread_id, "check_and_parse_json_reply_node", "success", "Успешный парсинг JSON.")
        return {
            "chat_text": str(chat_text),
            "canvas_type": str(canvas_type),
            "canvas_content": str(canvas_content),
            "validation_status": "passed",
            "validation_error": ""
        }

    except Exception as e:
        tb = traceback.format_exc()
        err_msg = f"[ОШИБКА ПАРСИНГА]: {type(e).__name__}: {str(e)}\nTraceback:\n{tb}"
        log_to_db(thread_id, "check_and_parse_json_reply_node", "FAILED", err_msg)
        print(err_msg)
        
        # Согласно твоему требованию: при ошибке парсинга фиксированный текст в чате, а llm_reply как есть в канвасе
        return {
            "chat_text": "Произошла ошибка при обработке ответа",
            "canvas_type": "html",
            "canvas_content": llm_reply,
            "validation_status": "failed",
            "validation_error": err_msg
        }

def should_retry(state: AIGameFlowState) -> str:
    thread_id = state.get("thread_id", "unknown") if isinstance(state, dict) else "unknown"
    try:
        status = state.get("validation_status") if isinstance(state, dict) else "passed"
        retry_count = state.get("retry_count", 0) if isinstance(state, dict) else 0
        
        if status == "failed" and retry_count < 3:
            log_to_db(thread_id, "should_retry", "decision", f"Решение: Retry (попытка {retry_count}).")
            return "retry"
        
        log_to_db(thread_id, "should_retry", "decision", "Решение: Завершение графа.")
        return "end"
    except Exception as e:
        log_to_db(thread_id, "should_retry", "CRASH", f"Ошибка условного перехода: {e}")
        return "end"

workflow = StateGraph(AIGameFlowState)
workflow.add_node("generator_node", generator_node)
workflow.add_node("check_and_parse_json_reply_node", check_and_parse_json_reply_node)

workflow.add_edge(START, "generator_node")
workflow.add_edge("generator_node", "check_and_parse_json_reply_node")
workflow.add_conditional_edges(
    "check_and_parse_json_reply_node",
    should_retry,
    {
        "retry": "generator_node",
        "end": END
    }
)

ai_game_graph = workflow.compile()