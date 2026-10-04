import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = genai.Client(api_key=os.getenv("LLM_API_KEY"))

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Reply with exactly: Themis LLM connection working."
)

print(response.text)