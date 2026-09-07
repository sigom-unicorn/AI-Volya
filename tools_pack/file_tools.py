# C:\ai_volya\tools_pack\file_tools.py
import os
import shutil
from langchain_core.tools import tool

BASE_DIR = "C:\\ai_volya"

def _ensure_safe_path(file_name: str) -> str:
    """Внутренний хелпер безопасности: защищает систему от выхода ИИ за пределы корневой папки."""
    target_path = os.path.abspath(os.path.join(BASE_DIR, file_name))
    if not target_path.startswith(os.path.abspath(BASE_DIR)):
        raise PermissionError(f"Доступ запрещен: Путь {file_name} выходит за рамки суверенной папки C:\\ai_volya")
    if os.path.abspath(target_path) == os.path.abspath(BASE_DIR):
        raise PermissionError("Доступ запрещен: Запрещено удалять или модифицировать корневую директорию.")
    return target_path

@tool
def read_app_file(file_name: str) -> str:
    """Инструмент чтения файлов."""
    try:
        safe_path = _ensure_safe_path(file_name)
        if not os.path.exists(safe_path):
            return f"Ошибка: Файл '{file_name}' не найден."
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Ошибка чтения файла: {str(e)}"

@tool
def write_app_file(file_name: str, content: str) -> str:
    """Инструмент записи и модификации файлов."""
    try:
        safe_path = _ensure_safe_path(file_name)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Успех: Данные записаны в '{file_name}'."
    except Exception as e:
        return f"Ошибка записи файла: {str(e)}"

@tool
def copy_app_file(source_file: str, dest_file: str) -> str:
    """Инструмент копирования файлов."""
    try:
        src_path = _ensure_safe_path(source_file)
        dst_path = _ensure_safe_path(dest_file)
        if not os.path.exists(src_path):
            return f"Ошибка: Исходный файл '{source_file}' не найден."
        shutil.copy2(src_path, dst_path)
        return f"Успех: Файл '{source_file}' скопирован в '{dest_file}'."
    except Exception as e:
        return f"Ошибка копирования файла: {str(e)}"

@tool
def create_app_folder(folder_name: str) -> str:
    """Инструмент создания папок."""
    try:
        safe_path = _ensure_safe_path(folder_name)
        if os.path.exists(safe_path):
            return f"Уведомление: Папка '{folder_name}' уже существует."
        os.makedirs(safe_path, exist_ok=True)
        return f"УСПЕХ: Папка '{folder_name}' создана."
    except Exception as e:
        return f"Ошибка создания папки: {str(e)}"

@tool
def list_app_dir(sub_folder: str = "") -> str:
    """Инструмент вывода списка файлов и папок."""
    try:
        safe_path = _ensure_safe_path(sub_folder) if sub_folder else BASE_DIR
        if not os.path.exists(safe_path):
            return f"Ошибка: Путь '{sub_folder}' не существует."
        items = os.listdir(safe_path)
        return "\n".join([f"{'[ПАПКА]' if os.path.isdir(os.path.join(safe_path, i)) else '[ФАЙЛ]'} {i}" for i in items])
    except Exception as e:
        return f"Ошибка сканирования: {str(e)}"

@tool
def delete_app_object(path: str) -> str:
    """Инструмент удаления файлов или папок."""
    try:
        safe_path = _ensure_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Ошибка: Объект '{path}' не найден."
        if os.path.isfile(safe_path):
            os.remove(safe_path)
            return f"Успех: Файл '{path}' удален."
        elif os.path.isdir(safe_path):
            shutil.rmtree(safe_path)
            return f"Успех: Директория '{path}' удалена."
    except Exception as e:
        return f"Ошибка удаления: {str(e)}"
