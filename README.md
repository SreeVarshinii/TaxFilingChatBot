# 🎓 F-1 Scholar Tax Navigator

**[🚀 Live Demo Available Here!](https://zealous-flower-0db75870f.2.azurestaticapps.net/)**

A specialized Retrieval-Augmented Generation (RAG) system built to navigate the complexities of 2025 IRS tax regulations for international students on F-1, J-1, M-1, and Q-1 visas.

This AI-powered application ingests complex IRS Publications (like Pub 519) and legal forms (like Form 1040-NR, Form 8843), performs **Hybrid Search (Vector Embeddings + BM25 Reciprocal Rank Fusion)** against a Supabase `pgvector` database, and utilizes LangChain and Google's Gemini models to provide accurate, context-aware tax guidance.

## 🌟 Key Features

*   **Azure Serverless Architecture**: Fully decoupled frontend (Vanilla JS/CSS) and backend (`api/` running on Azure Functions), optimized to fit seamlessly within Azure's strict 100MB deployment limits.
*   **Hybrid Search Engine**: Solves the classic "lexical vs. semantic mismatch" problem by combining Google Gemini 3072-dimension semantic vectors with native PostgreSQL Full-Text Keyword Search (BM25) via a custom Supabase RRF (Reciprocal Rank Fusion) RPC.
*   **Intelligent Prompting**: Orchestration layer correctly identifies "Resident Alien" vs. "Nonresident Alien" status using the Substantial Presence Test and 5-Year Rule logic before answering queries.
*   **Stateless Inference Engine**: Built to run entirely as a programmatic abstraction via LCEL (LangChain Expression Language), ensuring fast, stateless query resolution perfectly suited for serverless scaling. 
*   **Source Citation**: Enforces strict LLM grounding by ensuring that generated answers cite the specific IRS Form, Publication number, and page excerpt retrieved from the database.

---

## 🛠️ Architecture

1.  **Frontend (`/frontend`)**: A premium, pure Vanilla JavaScript, HTML, and CSS single-page application featuring dark-mode glassmorphism. Communicates strictly via REST to the `/api/chat` endpoint.
2.  **API Backend (`/api`)**: An Azure Functions (Python v2 model) wrapper containing `function_app.py` and the core `engine.py` RAG logic.
3.  **Data Ingestion (`/src/ingest.py`)**: Uses local Recursive Character Splitters to intelligently parse PDFs and upload embeddings to Supabase, fortified with anti-rate-limit batching.
4.  **Vector Store (Supabase)**: Extracted chunks are passed through `GoogleGenerativeAIEmbeddings` and stored directly into a remote Supabase Postgres database as `vector(3072)`.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.11
*   Azure Static Web Apps CLI (`swa-cli`)
*   Supabase Account (Free Tier Postgres DB)
*   Google Gemini API Key

### Installation

1.  **Clone the Repository** and open the directory.
2.  **Environment Setup**: Copy `.env.example` to `.env` and fill in your keys.
    ```env
    # Your Remote Supabase project endpoints
    SUPABASE_URL=https://<your-project>.supabase.co
    SUPABASE_KEY=<your-service-role-key>

    GOOGLE_API_KEY=<your-gemini-key>
    ```

3.  **Local Pip Installation**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r api/requirements.txt
    ```

### Running Locally

To run the full stack locally using the Azure Emulator:

**Terminal 1 (Backend):**
```bash
cd api
func start
```

**Terminal 2 (Frontend):**
```bash
cd frontend
python3 -m http.server 8080
```
Then navigate to `http://localhost:8080` in your browser.

---

## 🐞 Development Log: Challenges & Solutions

During the migration of this application to a fully cloud-native Azure Static Web App architecture, several deep architectural bugs and ecosystem limits were encountered and systematically conquered:

### 1. The Azure 100MB Serverless Limit
*   **Problem:** The initial deployment was rejected by Azure Oryx because the zipped `/api` artifact exceeded the 100MB hard limit for Static Web App managed functions.
*   **Root Cause:** The backend relied on `FastEmbed` for local embedding creation, which intrinsically bundled `onnxruntime`, a ~135MB C++ machine learning library.
*   **Solution:** Eradicated `FastEmbed` entirely and reverted the architecture back to `GoogleGenerativeAIEmbeddings` via REST API, cleanly shrinking our Python footprint to under 10MB.

### 2. Google Gemini API 429 Quota & Mac SSL packet Drops
*   **Problem:** Uploading the 1,133 IRS document chunks to Supabase caused Google API `429 Quota Exceeded` errors, followed by Mac `[SSL: SSLV3_ALERT_BAD_RECORD_MAC]` HTTPS stream crashes.
*   **Root Cause:** Google's Free Tier enforces a highly strict limit of exactly *100 embedding chunks per minute*. Attempting to buffer massive 3072-dimension JSON payloads via `httpx` while being rate-limited caused the SSL stream wrapper to maliciously fragment and drop the idle connection.
*   **Solution:** Rewrote the ingestion script to perfectly thread the needle of the quota math: It now uploads chunks in tight batches of 85, invokes a hard `time.sleep(60)` to cleanly reset the Google 1-minute sliding window, and includes a 3-strike generic exponential backoff to handle transient TLS drops.

### 3. Native Python 3.14 & Pydantic Validation Crashes
*   **Problem:** The `bulk_test.py` and local backend consistently crashed with `TypeError: 'function' object is not subscriptable` when parsing `Dict[str, Any]` type hints.
*   **Root Cause:** A deeply nested bug inside `langchain_core` leveraging Pydantic V1 type evaluations inherently breaks when running under Python 3.14 due to changes in PEP 649/740 regarding how class methods shadow built-in dict annotations.
*   **Solution:** Completely bypassed the buggy standard LangChain abstractions (`create_retrieval_chain` / `create_stuff_documents_chain`) by explicitly rewriting `engine.py` into pure natively structured LCEL (LangChain Expression Language).

### 4. Supabase pgvector Dimension Mismatches
*   **Problem:** Uploading vectors returned `22000: expected 768 dimensions, not 3072`, followed by another mismatch error stating `not 384`.
*   **Root Cause:** The database logic was originally tuned for `BAAI/bge-small` (384 dimensions). When switching to Gemini, Google's `models/gemini-embedding-001` silently returned a staggering 3072 numbers per vector instead of the standard 768.
*   **Solution:** Executed a hard SQL truncation (`TRUNCATE TABLE`) and updated the `update_vector.sql` schema to explicitly `ALTER COLUMN embedding TYPE vector(3072)`.

### 5. MacOS `Code 139 (0x8B)` Segfaults on `func start`
*   **Problem:** Emulating the Azure Functions runtime locally on MacOS ARM64 repeatedly crashed the host process with a Segmentation Fault before the endpoints could even register.
*   **Root Cause:** Local heavy data-science libraries `ragas` and `datasets` (which relied on `pyarrow` C+ binaries) aggressively collided with the Azure GRPC worker's internal threading stack during boot mapping.
*   **Solution:** Purged all evaluation/data-science wrappers from the production API code, allowing the Python v2 worker to boot completely isolated and clean.

### 6. Azure Module 404 Resolution
*   **Problem:** Azure completely deployed the static frontend but returned a `404 Not Found` for the `/api/chat` route, despite it working locally.
*   **Root Cause:** Azure Actions inherently zips *only* the mapped `api_location` (`/api/`) folder. Because the core inference engine was stored in `/src/engine.py`, it was excluded from the cloud payload, triggering a silent `ModuleNotFoundError` during cloud bootloader instantiation.
*   **Solution:** Placed `engine.py` structurally inside `/api/` and corrected localized paths within `function_app.py`, allowing Azure to officially capture the required logic block.
