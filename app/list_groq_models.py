import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = Groq(api_key=os.getenv("LLM_API_KEY"))
models = client.models.list()

print("Currently available Groq models on your account:\n")
for m in models.data:
    print(" -", m.id)