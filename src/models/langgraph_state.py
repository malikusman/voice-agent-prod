from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class LangGraphState(Base):
    __tablename__ = 'langgraph_states'

    id = Column(Integer, primary_key=True)
    call_sid = Column(String(34), ForeignKey('calls.call_sid'), nullable=False)
    caller_phone = Column(String(12), nullable=False)  # Format: 123-456-7890
    state_json = Column(String, nullable=False)  # JSON string of LangGraph state
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LangGraphState(call_sid={self.call_sid}, caller_phone={self.caller_phone})>"