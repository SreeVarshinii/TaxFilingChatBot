---
title: F1 Scholar Tax Navigator
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: gradio
app_file: app.py
pinned: false
---

# 🎓 F-1 Scholar Tax Navigator

**[👉 Check it out live on Hugging Face Spaces!](https://huggingface.co/spaces/Sreevarshinii/taxapp)**

A production-grade **Retrieval-Augmented Generation (RAG)** system built to navigate the complexities of IRS tax regulations for international students on F-1, J-1, M-1, and Q-1 visas. 

This is **not a toy application**—it is a rigorously tested, domain-specific AI assistant deployed to production, successfully serving real users handling complex, high-stakes tax scenarios (e.g., determining Substantial Presence, interpreting the 5-Year Rule, and parsing Form 1040-NR instructions).

---

## 🌟 System Architecture

The project utilizes a decoupled, resilient architecture designed around open-source AI tooling:

* **Frontend Engine (Gradio)**: Provides a stateful, interactive chat interface hosted on Hugging Face Spaces. It handles user state (such as tracking arrival dates for the 5-Year Rule) and securely streams LLM responses.
* **Orchestration Layer (LangChain)**: Implements LangChain Expression Language (LCEL) for stateless inference chains, ensuring thread safety and rapid context switching during complex multi-document queries.
* **LLM Engine**: Powered by `Qwen/Qwen2.5-7B-Instruct` via the Hugging Face Serverless Inference API (`langchain-huggingface`). The model is wrapped in `ChatHuggingFace` to ensure flawless prompt template formatting across `SystemMessage` and `HumanMessage` schemas.
* **Vector Database (Supabase)**: We rely on a robust **PostgreSQL** instance with the `pgvector` extension. Our database executes a custom RPC (Remote Procedure Call) to perform **Hybrid Search**, fusing traditional BM25 Full-Text Search with 384-dimensional Semantic Vector Search using Reciprocal Rank Fusion (RRF).
* **Local Embeddings**: Document semantic processing is powered entirely locally by `sentence-transformers/all-MiniLM-L6-v2`, guaranteeing high-speed vector generation without external rate limits or token costs.

## 🛡️ Failure Handling & Reliability

Production systems require resilience against failure. This system implements multiple layers of error handling:

1. **Ingestion Retry Mechanisms**: The document ingestion pipeline (`src/ingest.py`) implements automated exponential backoff to handle network drops, database connection timeouts, and dynamic payload limits during large batch operations to Supabase.
2. **Context Fallback Strategy**: The LLM is strictly prompted to refuse hallucination. If the vector database retrieves low-confidence documents, the model responds with: *"I do not have enough information from the official IRS publications to answer."*
3. **Stateless API Handling**: By isolating the LangChain logic in `TaxEngine`, we protect the LLM context limits from overflowing and handle any Hugging Face serverless API provider outages with graceful UI exception catches in the Gradio interface.

## 📊 Quality Evaluation

To ensure the bot provides legally sound IRS guidance, the underlying data corpus and LLM logic were heavily evaluated:

1. **Dual-Chunking Strategy**: We avoided naive text splitting. Documents are chunked using `RecursiveCharacterTextSplitter` with heavily overlapping windows, ensuring critical context (like tax treaty exceptions spanning multiple pages) is not lost.
2. **Deterministic Pre-Flighting**: The system does *not* trust the LLM to do date math. The Substantial Presence Test (5-Year Rule) is evaluated deterministically in Python (`evaluate_5_year_rule()`) before passing the verified residency status to the LLM context.
3. **Retrieval Verification**: The system was tested using RAG evaluation frameworks. We measured strict grounding—ensuring the LLM cites the exact Form, Publication number, and page excerpt retrieved from the database on every response. 

## 🌍 Real-World Deployment

This application was successfully deployed into a production environment where it was tested by actual international students navigating their 2025 tax filings. Originally engineered to meet strict 100MB serverless footprint limits on Azure Static Web Apps, the platform has now been completely transitioned to a fully open-source stack hosted seamlessly on **Hugging Face Spaces**.

---

## 🚀 Local Development Guide

1. Clone the repository and create a `.env` file with the following variables:
   ```env
   SUPABASE_URL=https://<your-project>.supabase.co
   SUPABASE_KEY=<your-service-role-key>
   HF_TOKEN=hf_<your-huggingface-token>
   ```

2. Activate your virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. (Optional) Run the local ingestion script to parse IRS PDFs and populate your Vector Database:
   ```bash
   python src/ingest.py
   ```

4. Run the production Gradio application:
   ```bash
   python app.py
   ```

Check out the configuration reference at [Hugging Face Spaces Config Reference](https://huggingface.co/docs/hub/spaces-config-reference).
