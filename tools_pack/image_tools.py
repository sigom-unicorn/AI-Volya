# C:\ai_volya\tools_pack\image_tools.py
import os
import base64
from langchain_core.tools import tool

BASE_DIR = "C:\\ai_volya"
TMP_DIR = "C:\\ai_volya\\tmp"

def _ensure_safe_path(file_path: str) -> str:
    """Проверка безопасности пути к файлу изображения."""
    abs_path = os.path.abspath(os.path.join(BASE_DIR, file_path))
    if not abs_path.startswith(os.path.abspath(BASE_DIR)):
        raise PermissionError(f"Доступ запрещен: Путь {file_path} выходит за рамки суверенной папки.")
    return abs_path

@tool
def read_image_file(file_name: str) -> str:
    """Инструмент чтения и анализа файлов-изображений из папки tmp (или корневой папки). Возвращает base64-кодированное изображение или описание."""
    try:
        # Если передан просто файл, ищем в tmp или базовой папке
        target_path = os.path.abspath(os.path.join(TMP_DIR, file_name))
        if not os.path.exists(target_path):
            target_path = _ensure_safe_path(file_name)
            
        if not os.path.exists(target_path):
            return f"Ошибка: Изображение '{file_name}' не найдено в папках рантайма."
            
        ext = os.path.splitext(target_path)[1].lower()
        if ext not in ['.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg']:
            return f"Предупреждение: Файл '{file_name}' не является стандартным изображением."
            
        with open(target_path, "rb") as f:
            encoded_data = base64.b64encode(f.read()).decode("utf-8")
            
        mime_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        mime_type = mime_map.get(ext, 'image/png')
        
        # Возвращаем специальный маркер и тег для визуализации на холсте
        return f"[IMAGE_DATA:{file_name}:{mime_type}:{encoded_data}]"
    except Exception as e:
        return f"Ошибка чтения изображения: {str(e)}"
