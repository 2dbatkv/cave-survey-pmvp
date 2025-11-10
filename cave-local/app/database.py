from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from datetime import datetime
from .config import get_settings

settings = get_settings()

# Configure SSL for production PostgreSQL (e.g., Render)
connect_args = {}
if settings.database_url.startswith("postgresql://") or settings.database_url.startswith("postgres://"):
    # For production databases that require SSL
    connect_args = {"sslmode": "require"}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    surveys = relationship("Survey", back_populates="owner")

class Survey(Base):
    __tablename__ = "surveys"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    section = Column(String, index=True)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # S3 storage info
    s3_json_key = Column(String)
    s3_png_key = Column(String)
    json_url = Column(String)
    png_url = Column(String)
    
    # Survey metadata
    num_stations = Column(Integer)
    num_shots = Column(Integer)
    total_slope_distance = Column(Float)
    total_horizontal_distance = Column(Float)
    
    # Bounding box
    min_x = Column(Float)
    max_x = Column(Float)
    min_y = Column(Float)
    max_y = Column(Float)
    min_z = Column(Float)
    max_z = Column(Float)
    
    owner = relationship("User", back_populates="surveys")

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    feedback_text = Column(Text, nullable=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    user_session = Column(String)
    category = Column(String, default="general")
    priority = Column(String, default="normal")
    status = Column(String, default="new")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)