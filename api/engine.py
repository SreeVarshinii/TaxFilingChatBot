import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from supabase.client import create_client, Client
from langchain_core.prompts import ChatPromptTemplate
from pydantic import Field
from typing import List, Any

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_KEY", "")

class TaxEngine:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", 
            "You are an expert F-1 Tax Navigator. You provide clear, concise, step-by-step guidance "
            "for international students on F-1 visas filing taxes in the US.\n\n"
            "Use ONLY the retrieved publications and instructions to answer the question.\n"
            "If the answer cannot be found in the context, explicitly state 'I do not have enough information "
            "from the official IRS publications to answer.'\n\n"
            "Context:\n{context}"
            ),
            ("human", "{input}"),
        ])
        
    def evaluate_5_year_rule(self, entry_date_str: str) -> bool:
        try:
            entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d")
            current_year = datetime.now().year
            years_present = current_year - entry_date.year
            return years_present <= 5
        except (ValueError, TypeError):
            return True

    def retrieve(self, query: str):
        q_emb = self.embeddings.embed_query(query)
        res = self.supabase.rpc(
            "hybrid_search",
            {
                "query_text": query,
                "query_embedding": q_emb,
                "match_count": 5,
                "rrf_k": 60
            }
        ).execute()
        if res.data:
            return [doc.get("content", "") for doc in res.data]
        return []

    def query(self, user_question: str, entry_date_str: str = None) -> dict:
        prefix = ""
        if entry_date_str:
            is_exempt = self.evaluate_5_year_rule(entry_date_str)
            if is_exempt:
                prefix = f"[User Entry Date: {entry_date_str}. They are in their first 5 years and are likely a NONRESIDENT ALIEN.]\n"
            else:
                prefix = f"[User Entry Date: {entry_date_str}. They have exceeded 5 years and are likely a RESIDENT ALIEN for tax purposes.]\n"

        full_query = prefix + user_question
        
        # 1. Retrieve Raw Contexts from Supabase
        contexts = self.retrieve(full_query)
        context_str = "\n\n---\n\n".join(contexts)
        
        # 2. Query LLM
        chain = self.prompt | self.llm
        response = chain.invoke({"context": context_str, "input": full_query})
        
        return {
            "answer": response.content,
            "context": contexts
        }
