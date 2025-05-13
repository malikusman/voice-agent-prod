from sqlalchemy import Column, Integer, String
from src.models.base import Base

class Booking(Base):
    __tablename__ = 'bookings'

    booking_id = Column(Integer, primary_key=True)
    phone_number = Column(String, nullable=False)
    time = Column(String, nullable=False)