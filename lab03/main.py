import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

# Загружаем переменные из файла .env
load_dotenv()

# Создаём приложение FastAPI
app = FastAPI(title="LLM Proxy Service")

# Читаем настройки из переменных окружения
LLM_API_KEY = os.getenv("OPENAI_API_KEY")
_base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
LLM_API_URL = f"{_base}/chat/completions"
LLM_MODEL = os.getenv("MODEL_NAME", "gemini-3.6-flash")


@app.get("/health")
def health():
    """
    Простая проверка, что сервис запущен.
    """
    return {"status": "ok"}


@app.get("/ask")
def ask(q: str = Query(..., min_length=1, description="Вопрос для LLM")):
    """
    Эндпоинт принимает вопрос и отправляет его в LLM API.
    """

    # Проверяем, что ключ и адрес заданы
    if not LLM_API_URL or not LLM_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Не заданы LLM_API_URL или LLM_API_KEY. Проверь файл .env"
        )

    # Заголовки запроса к LLM API
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    # Тело запроса к LLM API
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": q
            }
        ],
        "temperature": 0.3
    }

    try:
        # Отправляем POST-запрос в LLM API
        response = requests.post(
            LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        # Если код ответа не 2xx, поднимаем ошибку
        response.raise_for_status()

    except requests.HTTPError as exc:
        detail = {
            "error": "LLM API вернул ошибку",
            "status_code": exc.response.status_code if exc.response else None,
            "response_text": exc.response.text if exc.response else None,
        }
        raise HTTPException(status_code=502, detail=detail)

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не удалось подключиться к LLM API: {str(exc)}"
        )

    # Разбираем JSON-ответ
    data = response.json()

    # Для OpenAI-совместимых API ответ обычно лежит здесь:
    try:
        answer = data["choices"][0]["message"]["content"]
        return {
            "question": q,
            "answer": answer
        }
    except (KeyError, IndexError, TypeError):
        # Если структура ответа другая, возвращаем сырой ответ для отладки
        return {
            "question": q,
            "answer": None,
            "raw_response": data
        }