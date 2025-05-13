from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from src.models.base import Base
from datetime import datetime

class Transcript(Base):
    __tablename__ = 'transcripts'

    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey('calls.id'), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    text = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)