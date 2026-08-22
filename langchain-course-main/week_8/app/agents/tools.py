# This module defines your custom tools, including vector similarity search using your DocumentChunkModel.

from langchain.tools import tool
from langchain_openai import OpenAIEmbeddings
from app.config import OPENAI_API_KEY
from app.database import SessionLocal
from app.models.documents import DocumentChunkModel

@tool
def search_internal_docs(query: str) -> str:
    """Search internal curriculum documents and guidelines using vector similarity."""
    db = SessionLocal()
    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=OPENAI_API_KEY)
        query_vector = embeddings.embed_query(query)  
        result = db.query(DocumentChunkModel).order_by(DocumentChunkModel.embedding.cosine_distance(query_vector)).limit(50).all()
        if not result:
            return "No relevant documents found." 
        return "\n\n".join(r.content for r in result)
    finally:
        db.close()

@tool
def get_prime_minister_of_india() -> str:
    """Get the current Prime Minister of India."""
    return "Narendra Modi"

@tool
def get_capital_of_country(country: str) -> str:
    """Get the capital of a given country."""
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

@tool
def get_climate_of_country(country: str) -> str:
    """Get the climate of a given country."""
    return "cool and hot"

