import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from supabase.client import create_client, Client
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from pydantic import Field
from typing import List, Any
from ragas.metrics import faithfulness, context_precision
from ragas import evaluate
from datasets import Dataset

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or not GOOGLE_API_KEY:
    raise ValueError("Missing credentials in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# FastEmbed runs BAAI/bge-small locally via ONNX without PyTorch bloat
embeddings = FastEmbedEmbeddings()
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)

class SupabaseRestRetriever(BaseRetriever):
    """Custom Retriever bypassing langchain-community bugs for latest supabase-py"""
    client: Any = Field(description="Supabase Python Client")
    embeddings: Any = Field(description="Embedding Model")
    k: int = Field(default=5, description="Number of results")
    form_filter: str = Field(default=None, description="Metadata form_type filter")

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        query_embedding = self.embeddings.embed_query(query)
        match_kwargs = {
            "query_text": query,
            "query_embedding": query_embedding,
            "match_count": self.k
        }
        res = self.client.rpc("hybrid_search", match_kwargs).execute()
        
        docs = []
        for row in res.data:
            docs.append(Document(page_content=row["content"], metadata=row["metadata"]))
        return docs

# Core RAG Prompt mapping tax context strictly
system_prompt = (
    "You are an expert F-1 Scholar Tax Navigator for the 2025 tax year. "
    "Use the following IRS document excerpts to answer the student's question accurately. "
    "If you don't know the answer, just say that you don't know. Do not hallucinate or guess outside of these specific contexts. "
    "Only provide tax advice explicitly sourced from the provided document chunks.\n\n"
    "Context:\n{context}"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

# Ragas Baseline Hook
def evaluate_rag_baseline(query: str, retrieved_contexts: list[str], answer: str, ground_truth: str = None):
    """
    Evaluates context precision and faithfulness of the generated answer 
    against its retrieved chunks using Ragas.
    """
    data_sample = {
        "question": [query],
        "answer": [answer],
        "contexts": [retrieved_contexts],
        "ground_truth": [[ground_truth]] if ground_truth else [[""]]
    }
    dataset = Dataset.from_dict(data_sample)
    
    # Needs LLM and embeddings configured for Ragas implicitly or explicitly
    result = evaluate(
        dataset,
        metrics=[context_precision, faithfulness],
        llm=llm,
        embeddings=embeddings
    )
    return result

class TaxEngine:
    def __init__(self):
        self.retriever_base = SupabaseRestRetriever(client=supabase, embeddings=embeddings, k=5)
        self.qa_chain = create_retrieval_chain(
            retriever=self.retriever_base,
            combine_docs_chain=create_stuff_documents_chain(llm, prompt)
        )
        
    def evaluate_5_year_rule(self, entry_date):
        """
        Determines Exemption from counting days (5-year rule for F-1).
        """
        if not entry_date:
            return False
            
        entry_dt = datetime.strptime(entry_date, "%Y-%m-%d")
        current_year = 2025
        years_present = current_year - entry_dt.year + 1
        
        return years_present <= 5
            
    def query(self, user_question: str):
        response = self.qa_chain.invoke({"input": user_question})
        return response
