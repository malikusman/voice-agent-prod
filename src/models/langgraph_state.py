from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from src.models.base import Base

class LangGraphState(Base):
    __tablename__ = 'langgraph_states'

    id = Column(Integer, primary_key=True)
    call_id = Column(Integer, ForeignKey('calls.id'), nullable=False)
    state = Column(JSON, nullable=False)