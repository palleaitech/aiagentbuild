# This holds your chat session history model.

import datetime
from sqlalchemy import Column, String, Text, DateTime
from app.database import Base

class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    thread_id = Column(String, primary_key=True, index=True)
    user_prompt = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    routed_worker = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    