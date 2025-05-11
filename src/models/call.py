from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Call(Base):
    __tablename__ = 'calls'

    call_sid = Column(String(34), primary_key=True)
    caller_phone = Column(String(12))  # Format: 123-456-7890
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(20))  # e.g., 'initiated', 'completed'

    def __repr__(self):
        return f"<Call(call_sid={self.call_sid}, status={self.status})>"