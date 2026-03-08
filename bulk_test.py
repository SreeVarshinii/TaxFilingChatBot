import os
import csv
from dotenv import load_dotenv
from typing import List, Dict

# Assuming the Tax Engine uses these same embeddings under the hood
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from supabase.client import create_client
from src.engine import TaxEngine

def main():
    print("Loading environment and initializing services...")
    load_dotenv()
    
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    embeddings_model = HuggingFaceBgeEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        encode_kwargs={"normalize_embeddings": True}
    )
    
    # We will also use the TaxEngine to get the full LLM generated answer
    print("Initializing Tax Engine...")
    engine = TaxEngine()
    
    questions = []
    with open("test_questions.txt", "r", encoding="utf-8") as f:
        for line in f:
            q = line.strip()
            # Strip the numbers "1. " "2. " from the start
            if q and q[0].isdigit() and ". " in q:
                q = q.split(". ", 1)[1]
            if q:
                questions.append(q)
                
    results = []
    
    print(f"Processing {len(questions)} questions...")
    for i, q in enumerate(questions, 1):
        print(f"\n[{i}/{len(questions)}] Querying: {q}")
        
        # 1. Get raw hybrid search retrieval context directly
        q_emb = embeddings_model.embed_query(q)
        hybrid_res = supabase.rpc("hybrid_search", {
            "query_text": q,
            "query_embedding": q_emb,
            "match_count": 3  # Get top 3 sources to keep CSV clean
        }).execute()
        
        sources_str = ""
        if hybrid_res.data:
            for idx, r in enumerate(hybrid_res.data, 1):
                meta = r.get("metadata", {})
                form_type = meta.get("form_type", "Unknown")
                score = round(r.get("similarity", 0), 4)
                preview = r.get("content", "")[:100].replace('\n', ' ')
                sources_str += f"[{idx}] {form_type} (score: {score}): {preview}...\n"
        
        # 2. Get LLM Answer via LangChain Engine
        try:
            llm_response = engine.query(q)
            answer = llm_response.get('answer', 'No answer returned')
        except Exception as e:
            answer = f"ERROR: {e}"
            
        results.append({
            "Question": q,
            "Generated Answer": answer,
            "Top 3 Retrieved Sources (Hybrid)": sources_str.strip()
        })
        
    csv_file = "bulk_evaluation_results.csv"
    print(f"\nSaving results to {csv_file}...")
    
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Question", "Generated Answer", "Top 3 Retrieved Sources (Hybrid)"])
        writer.writeheader()
        for r in results:
            writer.writerow(r)
            
    print("Done!")

if __name__ == "__main__":
    main()
