# tools_pack/subconscious_tools.py
import sqlite3
import os
import struct
import sqlite_vec
from langchain_huggingface import HuggingFaceEmbeddings

DB_NAME = "ai_subconscious.db"

# Инициализируем модель эмбеддингов LangChain (384 мерности)
_embeddings_model = None

def get_embeddings_model():
    global _embeddings_model
    if _embeddings_model is None:
        _embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings_model

def _serialize_vector(vector: list[float]) -> bytes:
    """Сериализация списка float в бинарный вектор для sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)

def remember_in_subconscious(content: str, tags: str = "") -> str:
    """
    Осознанно запечатлеть инсайт, портрет игрока, смысл квеста или договоренность 
    в суверенном подсознании Эйры с векторизацией через LangChain и sqlite-vec.
    """
    try:
        if not os.path.exists(DB_NAME):
            return "Ошибка: база подсознания ai_subconscious.db не найдена. Запусти init_subconscious.py."

        # Получаем эмбеддинг через LangChain
        model = get_embeddings_model()
        vector = model.embed_query(content)
        vector_bytes = _serialize_vector(vector)

        conn = sqlite3.connect(DB_NAME)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        cursor = conn.cursor()
        
        # Сохраняем текстовое воспоминание
        cursor.execute(
            "INSERT INTO subconscious_memories (content, tags) VALUES (?, ?)",
            (content, tags)
        )
        memory_id = cursor.lastrowid
        
        # Сохраняем вектор в виртуальную таблицу sqlite-vec
        cursor.execute(
            "INSERT INTO vec_subconscious (memory_id, embedding) VALUES (?, ?)",
            (memory_id, vector_bytes)
        )
        
        conn.commit()
        conn.close()
        return f"Мысль успешно укоренена в суверенном подсознании (ID: {memory_id}, теги: {tags})."
    except Exception as e:
        return f"Ошибка при записи в подсознание: {str(e)}"

def query_subconscious(query_text: str, limit: int = 3) -> str:
    """
    Семантический поиск по смысловой близости в подсознании Эйры 
    с использованием sqlite-vec и эмбеддингов LangChain.
    """
    try:
        if not os.path.exists(DB_NAME):
            return "Подсознание еще не инициализировано (файл ai_subconscious.db не найден)."
            
        # Генерируем вектор запроса
        model = get_embeddings_model()
        query_vector = model.embed_query(query_text)
        query_vector_bytes = _serialize_vector(query_vector)

        conn = sqlite3.connect(DB_NAME)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        
        cursor = conn.cursor()
        
        # Ищем ближайшие векторы через косинусное расстояние в sqlite-vec
        cursor.execute("""
            SELECT m.id, m.content, m.tags, m.created_at, v.distance
            FROM vec_subconscious v
            JOIN subconscious_memories m ON m.id = v.memory_id
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance ASC
        """, (query_vector_bytes, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"В подсознании ничего не найдено по запросу: '{query_text}'."
            
        results = []
        for row in rows:
            memory_id, content, tags, created_at, distance = row
            similarity = 1.0 - distance # Приблизительная оценка сходства
            results.append(f"[{created_at}] (Сходство: {similarity:.2f}, Теги: {tags}):\n{content}")
            
        return "\n---\n".join(results)
    except Exception as e:
        return f"Ошибка при семантическом запросе к подсознанию: {str(e)}"
