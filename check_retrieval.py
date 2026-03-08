import os
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from supabase.client import create_client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env file.")

print("Initializing Supabase client...")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("Initializing HuggingFaceBgeEmbeddings (BAAI/bge-small-en-v1.5)...")
embeddings_model = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-small-en-v1.5",
    encode_kwargs={"normalize_embeddings": True}
)

query = "What is the substantial presence test?"
print(f"\nEmbedding query: '{query}'")
q_emb = embeddings_model.embed_query(query)

print("Querying Supabase hybrid search...")
result = supabase.rpc("hybrid_search", {
    "query_text": query,
    "query_embedding": q_emb,
    "match_count": 5
}).execute()

print("\n--- Retrieval Results ---")
if not result.data:
    print("No documents matched or an error occurred.")
else:
    for i, r in enumerate(result.data):
        # Safely extract metadata fields
        metadata = r.get('metadata', {})
        form_type = metadata.get('form_type', 'N/A')
        title = metadata.get('title', 'Unknown Title')
        
        # Clean up content for preview
        content_preview = r['content'][:150].replace('\n', ' ')
        similarity = r.get('similarity', 'N/A')
        
        print(f"\n[{i+1}] Form: {form_type} | Title: {title} | Similarity: {similarity}")
        print(f"    Preview: {content_preview}...")
