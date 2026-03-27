import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import create_client, Client

load_dotenv()

# Load Environment Variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")  # Usually you need service_role key for inserting, but anon key might work if RLS is disabled
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("Missing Supabase credentials in .env")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env")

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

    print("Initializing BAAI/bge-small-en-v1.5 Embeddings...")
    from langchain_community.embeddings import HuggingFaceBgeEmbeddings
    model_name = "BAAI/bge-small-en-v1.5"
    model_kwargs = {'device': 'cpu'}
    encode_kwargs = {'normalize_embeddings': True} # set True to compute cosine similarity
    embeddings = HuggingFaceBgeEmbeddings(
        model_name=model_name,
        model_kwargs=model_kwargs,
        encode_kwargs=encode_kwargs
    )

    print(f"Splitting {len(semantic_docs)} publication pages using Semantic Chunking...")
    # Semantic chunking uses the embedding model to find logical breakpoints
    from langchain_experimental.text_splitter import SemanticChunker
    text_splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
    
    semantic_chunks = text_splitter.split_documents(semantic_docs)
    print(f"Created {len(semantic_chunks)} semantic chunks.")
    
    print(f"Loaded {len(form_docs)} structure-aware chunks from forms.")
    
    chunks = semantic_chunks + form_docs
    print(f"Total chunks to upload: {len(chunks)}")

    print("Uploading chunks and embeddings to Supabase...")
    # We use SupabaseVectorStore.from_documents to embed and upload
    # 'documents' is the default table name expected by SupabaseVectorStore
    vector_store = SupabaseVectorStore.from_documents(
        chunks,
        embeddings,
        client=supabase,
        table_name="documents",
        query_name="match_documents"
    )
    
    print("Ingestion complete! Data successfully uploaded to Supabase pgvector.")

if __name__ == "__main__":
    main()
