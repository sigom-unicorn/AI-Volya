# C:\ai_volya\ai_game_flow.py
import os
import sqlite3
import datetime
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
import json

class AIGameFlowState(TypedDict):
    thread_id: str
    messages: list
    system_prompt: str
    tools: list
    raw_chat_text: str
    draft_chat_text: str
    canvas_type: str
    canvas_content: str
    retry_count: int
    canvas_validation_status: str
    validation_reason: str

DB_PATH = "C:\\ai_volya\\volya_game.db"

def log_to_db(thread_id: str, step_name: str, status: str, details: str):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO graph_log (thread_id, step_name, status, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (thread_id, step_name, status, details, now_str)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка логирования графа в БД: {e}")

# --- НОДА ГЕНЕРАТОРА (Асинхронная, создает агента на лету с перехватом событий инструментов) ---
async def generator_node(state: AIGameFlowState) -> AIGameFlowState:
    thread_id = state["thread_id"]
    messages = state["messages"]
    system_prompt = state["system_prompt"]
    tools = state["tools"]
    retry_count = state["retry_count"]
    validation_reason = state.get("validation_reason", "")

    current_messages = list(messages)
    if validation_reason and retry_count > 0:
        current_messages.append(("user", f"[Системное уточнение валидатора]: {validation_reason}"))

    try:
        model = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", max_output_tokens=30000)
        agent = create_react_agent(model, tools, prompt=system_prompt)
        
        # Вызываем инвокацию агента асинхронно
        response = await agent.ainvoke({"messages": current_messages})
        final_messages = response["messages"]
        last_msg = final_messages[-1]
        raw_reply = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        
        if isinstance(raw_reply, list):
            text_acc = ""
            for item in raw_reply:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_acc += item.get("text", "")
                elif hasattr(item, "text"):
                    text_acc += item.text
                elif hasattr(item, "content"):
                    text_acc += item.content
            raw_reply = text_acc.strip()

        cleaned = raw_reply.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1]).strip()
            elif len(lines) == 2:
                cleaned = lines[1].strip()

        chat_text, canvas_type, canvas_content = raw_reply, "html", ""
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                chat_text = str(data.get("chat_text", "") or data.get("message", "") or "")
                canvas_content = str(data.get("canvas_content", "") or "")
                canvas_type = str(data.get("canvas_type", "html") or "html")
        except json.JSONDecodeError:
            pass

        log_to_db(thread_id, "generator_node", "success", f"Успешная асинхронная генерация (попытка {retry_count}).")
        return {
            **state,
            "raw_chat_text": raw_reply,
            "draft_chat_text": chat_text,
            "canvas_type": canvas_type,
            "canvas_content": canvas_content
        }
    except Exception as e:
        log_to_db(thread_id, "generator_node", "error", f"Ошибка асинхронной генерации: {str(e)}")
        return {
            **state,
            "raw_chat_text": f"Ошибка генерации: {str(e)}",
            "draft_chat_text": "Эйра не может обработать ваш запрос",
            "canvas_content": ""
        }

async def canvas_audit_node(state: AIGameFlowState) -> AIGameFlowState:
    thread_id = state["thread_id"]
    draft_text = state["draft_chat_text"]
    retry_count = state["retry_count"]

    if draft_text.strip().startswith("{") and '"chat_text"' in draft_text:
        log_to_db(thread_id, "canvas_audit_node", "retry", "Обнаружен сырой JSON в чате.")
        return {
            **state,
            "canvas_validation_status": "retry",
            "validation_reason": "Обнаружен сырой JSON в поле chat_text.",
            "retry_count": retry_count + 1
        }

    log_to_db(thread_id, "canvas_audit_node", "success", "Валидация успешна.")
    return {
        **state,
        "canvas_validation_status": "success",
        "validation_reason": ""
    }

def should_retry(state: AIGameFlowState) -> str:
    if state["canvas_validation_status"] == "retry" and state["retry_count"] < 3:
        return "retry"
    return "end"

workflow = StateGraph(AIGameFlowState)
workflow.add_node("generator_node", generator_node)
workflow.add_node("canvas_audit_node", canvas_audit_node)
workflow.set_entry_point("generator_node")
workflow.add_edge("generator_node", "canvas_audit_node")
workflow.add_conditional_edges("canvas_audit_node", should_retry, {"retry": "generator_node", "end": END})

ai_game_graph = workflow.compile()
