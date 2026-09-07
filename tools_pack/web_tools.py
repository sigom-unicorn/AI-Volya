# tools_pack/web_tools.py
import time
from langchain_core.tools import tool
from langchain_community.utilities import SearxSearchWrapper

@tool
def search_online(query: str) -> str:
    """Ищет актуальную информацию или погоду в интернете через открытый бесплатный поисковик SearXNG."""
    time.sleep(1)
    print(f"\n[ДИАГНОСТИКА] Локальный поисковик SearXNG получил запрос: '{query}'")
    try:
        # Наш проверенный IP-адрес машины Podman в WSL
        searx_host = "http://172.23.252.219:8080"
        search_wrapper = SearxSearchWrapper(searx_host=searx_host)
        raw_results = search_wrapper.results(query, num_results=3)
        print(f"[ДИАГНОСТИКА] Ответ от локального сервера SearXNG получен успешно.\n")
        if not raw_results:
            return "Поиск во внешней сети не дал результатов."
        return "\n\n".join([f"Сайт: {r.get('title')}\nКонтент: {r.get('snippet')}" for r in raw_results])
    except Exception as e:
        print(f"[ДИАГНОСТИКА] Сбой SearXNG: {str(e)}\n")
        return f"Поисковый сервер временно недоступен: {str(e)}. Запустите контейнер в Podman Desktop."

@tool
def browse_website(url: str) -> str:
    """Переходит по указанной ссылке (URL) и полностью читает текстовое содержимое сайта для глубокого анализа."""
    print(f"\n[ДИАГНОСТИКА] Агент переходит по ссылке: '{url}'")
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=7)
        
        if response.status_code != 200:
            return f"Не удалось открыть сайт. Код ошибки: {response.status_code}"
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Удаляем лишний мусор со страницы
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.extract()
            
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        
        return clean_text[:4000] if len(clean_text) > 4000 else clean_text
        
    except Exception as e:
        return f"Ошибка при чтении сайта: {str(e)}"
