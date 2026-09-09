# app/agents/mcp_server.py
import os
from mcp.server.fastmcp import FastMCP
from app.database import SessionLocal
from app.models.documents import DocumentChunkModel
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from fastapi import FastAPI

# 👇 Ensure environment variables are loaded inside the MCP subprocess
load_dotenv()

# 👇 Guarantee the environment variables exist inside this subprocess
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@db:5432/postgres"

if not os.getenv("OPENAI_API_KEY"):
    # If you have your key in docker-compose, make sure it's read or fallback here
    pass

mcp = FastMCP("AgenticServer")

@mcp.tool()
def search_internal_docs(query: str) -> str:
    """Search internal curriculum documents and guidelines using vector similarity."""
    db = SessionLocal()
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        embeddings = OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"), 
            openai_api_key=api_key
        )
        query_vector = embeddings.embed_query(query)  
        result = db.query(DocumentChunkModel).order_by(DocumentChunkModel.embedding.cosine_distance(query_vector)).limit(5).all()
        
        if not result:
            return "No relevant documents found." 
            
        return "\n\n".join(r.content for r in result)
    except Exception as e:
        # 🔍 Print the exact exception so you can see it instantly in the logs
        print(f"🔥 RAG TOOL EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Error executing search tool: {str(e)}"
    finally:
        db.close()

@mcp.tool()
def get_prime_minister_of_india() -> str:
    """Get the current Prime Minister of India."""
    return "Narendra Modi"

@mcp.tool()
def get_capital_of_country(country: str) -> str:
    """Get the capital of a given country."""
    capitals = {"france": "Paris", "india": "New Delhi"}
    return capitals.get(country.lower(), "Unknown")

@mcp.tool()
def get_climate_of_country(country: str) -> str:
    """Get the climate of a given country."""
    return "cool and hot"

if __name__ == "__main__":
    mcp.run(transport="stdio")