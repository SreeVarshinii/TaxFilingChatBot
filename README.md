# 🎓 F-1 Scholar Tax Navigator

A specialized Retrieval-Augmented Generation (RAG) system built to navigate the complexities of 2025 IRS tax regulations for international students on F-1, J-1, M-1, and Q-1 visas.

This AI-powered application ingests complex IRS Publications (like Pub 519) and legal forms (like Form 1040-NR, Form 8843), performs **Hybrid Search (Vector Embeddings + BM25 Reciprocal Rank Fusion)** against a Supabase `pgvector` database, and utilizes LangChain and Google's Gemini models to provide accurate, context-aware tax guidance.

## 🌟 Key Features

*   **Hybrid Search Engine**: Solves the classic "lexical vs. semantic mismatch" problem by combining `BAAI/bge-small` semantic vector embeddings with native PostgreSQL Full-Text Keyword Search (BM25) via a custom Supabase RRF (Reciprocal Rank Fusion) RPC.
*   **Intelligent Prompting**: Orchestration layer correctly identifies "Resident Alien" vs. "Nonresident Alien" status using the Substantial Presence Test and 5-Year Rule logic before answering queries.
*   **Headless Inference Engine**: Built to run entirely as a programmatic backend via the CLI, ensuring clean, dependency-isolated tax query resolution. 
*   **Source Citation**: Enforces strict LLM grounding by enforcing that generated answers cite the specific IRS Form, Publication number, and page excerpt retrieved from the database.
*   **Dockerized Deployment**: A highly-portable `docker-compose` environment bypassing native local Windows pip dependency fragmentation.

---

## 🛠️ Architecture

1.  **Ingestion (`src/ingest.py`)**: Uses LangChain Document Loaders (`UnstructuredPDFLoader` and `PyPDFLoader`) to chunk PDFs located in `/data` via Semantic and Title-Aware chunking strategies.
2.  **Vector Store (Supabase)**: Extracted chunks are passed through `HuggingFaceBgeEmbeddings` and stored directly into a remote Supabase Postgres database.
3.  **Engine (`src/engine.py`)**: LangChain interface managing context retrieval logic via a customized `SupabaseRestRetriever`.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.11+
*   Docker & Docker Compose
*   Supabase Account (Free Tier Postgres DB)
*   Google Gemini API Key

### Installation

1.  **Clone the Repository** and open the directory.
2.  **Environment Setup**: Copy `.env.example` to `.env` and fill in your keys.
    ```env
    # Your Remote Supabase project endpoints
    SUPABASE_URL=https://<your-project>.supabase.co
    SUPABASE_KEY=<your-service-role-key>

    # Used by psycopg2 migration scripts
    SUPABASE_DB_URL=postgresql://postgres:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres

    GOOGLE_API_KEY=<your-gemini-key>
    ```

3.  **Local Pip Installation (Required for CLI tools)**:
    ```bash
    # We strictly enforce 0.3.x bounds for LangChain to avoid Pydantic module conflicts
    pip install -r requirements.txt
    ```

### Supabase Full-Text Search Configuration

Because this project utilizes robust **Hybrid Search**, you must run the following SQL migration in your Supabase SQL Editor BEFORE running queries:

```sql
-- Add tsvector column for full-text search
ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts tsvector 
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Index it
CREATE INDEX IF NOT EXISTS documents_fts_idx ON documents USING gin(fts);

-- Create hybrid search function
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(384),
    match_count INT DEFAULT 5,
    rrf_k INT DEFAULT 60
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE sql
AS $$
WITH
vector_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> query_embedding) AS rank
    FROM documents ORDER BY embedding <=> query_embedding LIMIT 50
),
keyword_results AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(fts, websearch_to_tsquery('english', query_text)) DESC) AS rank
    FROM documents WHERE fts @@ websearch_to_tsquery('english', query_text) ORDER BY rank LIMIT 50
),
rrf AS (
    SELECT
        COALESCE(v.id, k.id) AS id,
        COALESCE(1.0 / (rrf_k + v.rank), 0.0) +
        COALESCE(1.0 / (rrf_k + k.rank), 0.0) AS rrf_score
    FROM vector_results v
    FULL OUTER JOIN keyword_results k ON v.id = k.id
)
SELECT d.id, d.content, d.metadata, rrf.rrf_score AS similarity
FROM rrf JOIN documents d ON d.id = rrf.id
ORDER BY rrf_score DESC LIMIT match_count;
$$;
```

---

## 💻 CLI Tools

This project features an extensive suite of CLI scripts for analyzing LLM behaviors.

**1. Data Ingestion**
Reparses the `/data` folder PDFs to upload to Supabase:
```bash
python src/ingest.py
```

**2. Evaluate Embedding Clusters**
Extracts 2D dimensions of documents to visualize semantic mapping in a `.png` chart.
```bash
python src/analyze_embeddings.py
```

**3. Test Raw Database Retrieval**
Bypasses LangChain entirely to print the top 5 database strings returned by the pure `hybrid_search` Reciprocal Rank backend for a given string:
```bash
python check_retrieval.py
```

**4. Ask a Question**
Run a single query through the full LangChain orchestration loop:
```bash
python ask.py "Why do I need to file Form 8843?"
```

**5. Bulk Evaluation CSV Export**
Iterate through the `test_questions.txt` array, evaluate retrieval effectiveness against Gemini, and output `bulk_evaluation_results.csv`:
```bash
python bulk_test.py
```
