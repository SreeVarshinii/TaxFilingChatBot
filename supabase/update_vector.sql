-- 1. Empty the table completely so PostgreSQL doesn't crash on existing 384-dim vectors
TRUNCATE TABLE documents;

-- 2. Increase the dimension of the embedding vector column to support Gemini (3072 dims natively)
ALTER TABLE documents ALTER COLUMN embedding TYPE vector(3072);

-- 3. Drop the old hybrid_search function 
DROP FUNCTION IF EXISTS hybrid_search(text, vector(384), integer, integer);
DROP FUNCTION IF EXISTS hybrid_search(text, vector(768), integer, integer);

-- 4. Recreate the function expecting 3072 dimension vectors
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(3072),
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
