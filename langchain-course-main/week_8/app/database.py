# Step 2: This module sets up your SQLAlchemy engine, session maker, and base model class.
import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# If pytest is running, force "localhost" instead of "db" in the connection string
if "pytest" in os.environ.get("_", "") or os.getenv("PYTEST_CURRENT_TEST") or "PYTEST_VERSION" in os.environ:
    DATABASE_URL = DATABASE_URL.replace("@db:", "@localhost:")

engine = create_engine(DATABASE_URL)

# 🛠️ Explicitly create the pgvector extension safely
try:
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()
except Exception as e:
    print(f"Warning: Could not initialize pgvector extension on startup: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""
The error type "vector" does not exist happens because even though you are using the ankane/pgvector image, PostgreSQL requires the vector 
extension to be explicitly activated inside the specific database before it can understand the VECTOR data type.
 SQLAlchemy tries to run CREATE TABLE document_chunks on startup, but PostgreSQL rejects it because the extension hasn't been 
 enabled yet.

How to Fix It Permanently:
You can fix this by explicitly telling SQLAlchemy to create the extension the moment it connects, right before it attempts 
to build your tables.

Update your week_8/app/database.py file to automatically execute CREATE EXTENSION IF NOT EXISTS vector; upon startup:
"""        