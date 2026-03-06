import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text
from app.db.session import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String, nullable=False)
    output_type = Column(String, nullable=False)  # pdf/png/jpg

    status = Column(String, nullable=False, default="queued")  # queued/planning/processing/validating/complete/failed
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String, nullable=True)

    input_path = Column(String, nullable=False)
    output_path = Column(String, nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)