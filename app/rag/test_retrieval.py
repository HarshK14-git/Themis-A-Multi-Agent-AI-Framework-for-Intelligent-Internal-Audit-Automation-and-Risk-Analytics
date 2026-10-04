import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

model = SentenceTransformer("all-MiniLM-L6-v2")
query = "privileged accounts without multi-factor authentication"
query_embedding = model.encode(query).tolist()

conn = psycopg.connect(os.getenv("DATABASE_URL"))
register_vector(conn)

with conn.cursor() as cur:
    cur.execute(
        """SELECT control_id, control_name, category, criticality, embedding <=> %s::vector AS distance
           FROM controls ORDER BY distance ASC LIMIT 5;""",
        (query_embedding,)
    )
    results = cur.fetchall()
conn.close()

print(f"Query: '{query}'\n\nTop matching controls:")
for control_id, name, category, criticality, distance in results:
    print(f"  {control_id} - {name} ({category}, {criticality}) | distance: {distance:.4f}")