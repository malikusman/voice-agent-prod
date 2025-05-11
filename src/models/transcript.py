from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Transcript(Base):
    __tablename__ = 'transcripts'

    id = Column(Integer, primary_key=True)
    call_sid = Column(String(34), ForeignKey('calls.call_sid'), nullable=False)
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    text = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Transcript(call_sid={self.call_sid}, role={self.role}, text={self.text})>"