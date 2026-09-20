import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

try:
    print("Запрашиваю список доступных моделей для вашего ключа...")
    models = client.models.list()
    print("\n✅ Вот модели, к которым у вас есть доступ:")
    for m in models.data:
        print(f"➡️  {m.id}")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    print("Проверьте, что ключ в файле .env не содержит пробелов в конце строки.")