import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

print("Loading embedding model (first run downloads it, ~90MB)...")
model = SentenceTransformer("all-MiniLM-L6-v2")

controls_df = pd.read_csv("data/synthetic/compliance_controls.csv")

conn = psycopg.connect(os.getenv("DATABASE_URL"))
register_vector(conn)

with conn.cursor() as cur:
    cur.execute("DELETE FROM controls;")
    for _, row in controls_df.iterrows():
        text_to_embed = f"{row['control_name']}: {row['description']}"
        embedding = model.encode(text_to_embed).tolist()
        cur.execute(
            """INSERT INTO controls (control_id, framework, control_name, category, criticality, description, embedding)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (row["control_id"], row["framework"], row["control_name"], row["category"],
             row["criticality"], row["description"], embedding)
        )
conn.commit()
conn.close()
print(f"Inserted {len(controls_df)} controls with embeddings.")