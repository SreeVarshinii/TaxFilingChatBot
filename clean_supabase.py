import os
from dotenv import load_dotenv
from supabase.client import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing Supabase credentials in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def clear_documents():
    print("Clearing 'documents' table in Supabase...")
    # Delete all records by matching all IDs that are not nil UUID, or just use a generic condition
    res = supabase.table("documents").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    print(f"Cleared table successfully. Records deleted: {len(res.data) if res.data else 0}")

if __name__ == "__main__":
    clear_documents()
