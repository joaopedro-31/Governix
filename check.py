import os
from dotenv import load_dotenv
import requests

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"

response = requests.get(url)
if response.status_code == 200:
    models = response.json()
    print("✅ Chave válida! Modelos disponíveis para você:")
    for m in models['models']:
        print(f"- {m['name']}")
else:
    print(f"❌ Erro na chave: {response.status_code}")
    print(response.json())