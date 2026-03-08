import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("SUPABASE_DB_URL")
if not DB_URL:
    raise ValueError("Missing SUPABASE_DB_URL in .env")

SQL = """
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
-- Vector search results with rank
vector_results AS (
    SELECT
        id,
        ROW_NUMBER() OVER (ORDER BY embedding <=> query_embedding) AS rank
    FROM documents
    ORDER BY embedding <=> query_embedding
    LIMIT 50
),
-- Full-text keyword search results with rank
keyword_results AS (
    SELECT
        id,
        ROW_NUMBER() OVER (ORDER BY ts_rank(fts, websearch_to_tsquery('english', query_text)) DESC) AS rank
    FROM documents
    WHERE fts @@ websearch_to_tsquery('english', query_text)
    ORDER BY rank
    LIMIT 50
),
-- Reciprocal Rank Fusion
rrf AS (
    SELECT
        COALESCE(v.id, k.id) AS id,
        COALESCE(1.0 / (rrf_k + v.rank), 0.0) +
        COALESCE(1.0 / (rrf_k + k.rank), 0.0) AS rrf_score
    FROM vector_results v
    FULL OUTER JOIN keyword_results k ON v.id = k.id
)
SELECT
    d.id,
    d.content,
    d.metadata,
    rrf.rrf_score AS similarity
FROM rrf
JOIN documents d ON d.id = rrf.id
ORDER BY rrf_score DESC
LIMIT match_count;
$$;
"""

def main():
    print("Connecting to Supabase PostgreSQL...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Applying Hybrid Search schema updates...")
    cur.execute(SQL)
    
    print("Successfully added FTS column, GIN index, and hybrid_search RPC!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
