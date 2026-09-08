import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector
from langchain_core.documents import Document

# Connect to your PostgreSQL / pgvector container database
DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@postgres_vector_db:5432/vector_db")
COLLECTION_NAME = "my_docs"

# Initialize embeddings model
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# Define sample documentation answering the previous query
docs = [
    Document(page_content="System Architecture: This application uses PostgreSQL with the pgvector extension as the primary database for storing and querying vector embeddings."),
    Document(page_content="Infrastructure Details: The vector database runs inside a Docker container named postgres_vector_db on port 5432 and uses psycopg for connection handling.")
]

print("Ingesting sample documents into PGVector...")
vectorstore = PGVector.from_documents(
    documents=docs,
    embedding=embeddings,
    connection_string=DB_CONNECTION,
    collection_name=COLLECTION_NAME,
    pre_delete_collection=False  # Set to True if you want to clear old docs first
)
print("Documents successfully ingested into vector store!")