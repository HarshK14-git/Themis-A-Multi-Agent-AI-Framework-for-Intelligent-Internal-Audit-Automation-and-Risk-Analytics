import os
import psycopg
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
print("Looking for .env at:", env_path)
print("Does it exist?", env_path.exists())
load_dotenv(dotenv_path=env_path)

try:
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    print("✅ Connected successfully!")
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        print(cur.fetchone())
    conn.close()
except Exception as e:
    print("❌ Connection failed:", e)