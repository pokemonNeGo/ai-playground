import os
from dotenv import load_dotenv
from openai import OpenAI

# Загружаем переменные окружения из файла .env
load_dotenv()

# Читаем настройки
api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_BASE_URL") or None
model = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Проверяем, что ключ существует
if not api_key:
    raise SystemExit("Не найден ключ OPENAI_API_KEY. Проверьте файл .env")

# Создаём клиент для обращения к LLM API
client = OpenAI(api_key=api_key, base_url=base_url)

# Вопрос, который отправляем модели
question = input("Введите вопрос: ")

# Отправляем запрос
response = client.chat.completions.create(
    model=model,
    messages=[
        {
            "role": "user",
            "content": question
        }
    ],
    temperature=0.3
)

# Достаём текст ответа
answer = response.choices[0].message.content

# Печатаем результат
print("Вопрос:", question)
print("Ответ модели:")
print(answer)