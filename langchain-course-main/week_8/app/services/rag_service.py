# Step 4: Create app/services/rag_service.py
# Let's also pull out your document ingestion tool and helper function so your business logic is cleanly separated.

import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from app.config import OPENAI_API_KEY, DATABASE_URL
from app.database import SessionLocal
from app.models.documents import DocumentChunkModel

def ingest_document(pdf_path: str):
    """Load a PDF, split it into chunks, embed each chunk, and save to PostgreSQL."""
    if not os.path.exists(pdf_path):
        print(f"PDF path not found: {pdf_path}")
        return

    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(docs)
    db = SessionLocal()

    try:
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", openai_api_key=OPENAI_API_KEY)

        for chunk in chunks:
            vector = embeddings.embed_query(chunk.page_content)
            doc_entry = DocumentChunkModel(
                content=chunk.page_content,
                embedding=vector,
                source_file=os.path.basename(pdf_path)
            )
            db.add(doc_entry)
    
        db.commit()
        print(f"Successfully ingested {len(chunks)} chunks from {pdf_path}")
    except Exception as e:
        print(f"Error during document ingestion: {e}")
        db.rollback()
    finally:
        db.close()

        