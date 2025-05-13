from sqlalchemy import Column, String, DateTime, Integer
from src.models.base import Base
from datetime import datetime

class Call(Base):
    __tablename__ = 'calls'

    id = Column(Integer, primary_key=True)
    call_sid = Column(String, unique=True, nullable=False)
    caller_phone = Column(String)
    status = Column(String, default='initiated')
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)