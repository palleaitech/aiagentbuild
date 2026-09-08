# This holds your vector embeddings model using pgvector.

from sqlalchemy import Column, Integer, Text
from pgvector.sqlalchemy import Vector
from app.database import Base

class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(3072), nullable=False)
    source_file = Column(Text, nullable=True)

    