"""
Control Retrieval (connects uploaded evidence to RAG)
Given arbitrary evidence text (already masked), finds the most semantically
relevant ISO 27001 control(s) via pgvector similarity search - same
mechanism validated in Phase 6, now applied to arbitrary uploaded text
instead of a fixed test query.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import psycopg
from pgvector.psycopg import register_vector

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

_model = None

def get_embedding_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def retrieve_relevant_controls(text, top_k=3, max_distance=0.9):
    """
    max_distance is a relevance cutoff, not a hard science yet - Phase 6's
    single test query landed genuine matches around 0.60-0.75. We're
    starting at 0.9 (permissive) and will tighten it once we see real
    evidence distances below.
    """
    model = get_embedding_model()
    query_embedding = model.encode(text[:2000]).tolist()

    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute(
            """SELECT control_id, control_name, category, criticality, description,
                      embedding <=> %s::vector AS distance
               FROM controls ORDER BY distance ASC LIMIT %s;""",
            (query_embedding, top_k)
        )
        rows = cur.fetchall()
    conn.close()

    results = []
    for control_id, name, category, criticality, description, distance in rows:
        if distance <= max_distance:
            results.append({
                "control_id": control_id, "control_name": name, "category": category,
                "criticality": criticality, "description": description, "distance": distance,
            })
    return results


if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from agents.evidence_extraction import extract_evidence_text
    from security.pii_masking import mask_evidence_text

    test_files = ["Evidence_005.xlsx", "Evidence_007.png", "Evidence_009.png", "PS_01_EV3.png"]
    for filename in test_files:
        path = f"data/raw/{filename}"
        raw = extract_evidence_text(path)
        masked, _ = mask_evidence_text(raw)
        matches = retrieve_relevant_controls(masked, max_distance=1.5)  # loose cutoff, just to see real numbers first

        print(f"\n{'='*50}\n{filename}\n{'='*50}")
        if matches:
            for m in matches:
                print(f"  {m['control_id']} - {m['control_name']} (distance: {m['distance']:.4f})")
        else:
            print("  No matches at all (unexpected with a 1.5 cutoff)")