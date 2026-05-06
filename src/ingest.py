import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import create_client, Client

load_dotenv()

# Load Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")  # Usually you need service_role key for inserting, but anon key might work if RLS is disabled
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing Supabase credentials in .env")

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def get_metadata_from_filename(filename: str):
    """"Extracts basic metadata based on the filename of the tax document."""
    name = filename.lower()
    metadata = {"tax_year": 2025}
    if "519" in name:
        metadata["title"] = "Publication 519"
        metadata["form_type"] = "pub519"
    elif "901" in name:
        metadata["title"] = "Publication 901"
        metadata["form_type"] = "pub901"
    elif "f1040nr" in name and "i1040nr" not in name and "f1040nro" not in name:
         metadata["title"] = "Form 1040-NR"
         metadata["form_type"] = "1040nr"
    elif "f1040nro" in name:
         metadata["title"] = "Form 1040-NR (Schedule OI)"
         metadata["form_type"] = "1040nr_oi"
    elif "i1040nr" in name:
         metadata["title"] = "Instructions 1040-NR"
         metadata["form_type"] = "1040nr_instr"
    elif "8843" in name:
         metadata["title"] = "Form 8843"
         metadata["form_type"] = "8843"
    else:
         metadata["title"] = filename
         metadata["form_type"] = "unknown"
    return metadata

def main():
    print("Loading PDFs from data/ directory and applying dual chunking strategy...")
    form_docs = []
    semantic_docs = []
    
    for filename in os.listdir("./data"):
        if not filename.endswith(".pdf"):
            continue
            
        file_path = os.path.join("./data", filename)
        source_file = os.path.basename(file_path)
        custom_metadata = get_metadata_from_filename(source_file)
        
        if filename.lower().startswith("f"):
            print(f"Skipping form '{filename}' (not embedding forms)...")
            continue
        else:
            print(f"Loading '{filename}' with PyPDFLoader for semantic chunking...")
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            for doc in docs:
                doc.metadata.update(custom_metadata)
            semantic_docs.extend(docs)

    print("Initializing Open-Source Hugging Face Embeddings...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    print(f"Splitting {len(semantic_docs)} publication pages using Recursive Character Chunking...")
    # Replacing the API-heavy SemanticChunker with a local Recursive Splitter to avoid 429 Rate Limits
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        length_function=len
    )
    
    semantic_chunks = text_splitter.split_documents(semantic_docs)
    print(f"Created {len(semantic_chunks)} chunks.")
    
    print(f"Loaded {len(form_docs)} structure-aware chunks from forms.")
    
    chunks = semantic_chunks + form_docs
    print(f"Total chunks to upload: {len(chunks)}")

    print("Uploading chunks and embeddings to Supabase in batches...")
    # 'documents' is the default table name expected by SupabaseVectorStore
    import time
    batch_size = 200
    total_chunks = len(chunks)
    
    for i in range(0, total_chunks, batch_size):
        batch = chunks[i: i + batch_size]
        print(f"Uploading batch {i//batch_size + 1} ({i+1} to {min(i+batch_size, total_chunks)} of {total_chunks})...")
        
        for attempt in range(3):
            try:
                SupabaseVectorStore.from_documents(
                    batch,
                    embeddings,
                    client=supabase,
                    table_name="documents",
                    query_name="match_documents"
                )
                break # Success, break out of retry loop
            except Exception as e:
                print(f"Network error on batch {i}: {e}. Retrying {attempt+1}/3 in 10 seconds...")
                time.sleep(10)
    
    print("Ingestion complete! Data successfully uploaded to Supabase pgvector.")

if __name__ == "__main__":
    main()
