from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Booking(Base):
    __tablename__ = 'bookings'

    id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, unique=True, nullable=False)
    phone_number = Column(String(12), nullable=False)  # Format: 123-456-7890
    time = Column(String(10), nullable=False)  # Format: H:MM AM/PM
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Booking(booking_id={self.booking_id}, phone_number={self.phone_number}, time={self.time})>"