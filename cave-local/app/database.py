from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from datetime import datetime
import logging
import re
from .config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Configure database URL with SSL parameters for production PostgreSQL (e.g., Render)
database_url = settings.database_url

# Sanitize URL for logging (hide password)
def sanitize_url(url):
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', url)

logger.info(f"Original database URL: {sanitize_url(database_url)}")

if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
    # Render PostgreSQL requires SSL - append sslmode parameter to URL if not present
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"
        logger.info(f"Modified database URL with SSL: {sanitize_url(database_url)}")
    else:
        logger.info(f"Database URL already contains sslmode parameter: {sanitize_url(database_url)}")

# Create engine with connection pool settings for better reliability
try:
    logger.info("Creating SQLAlchemy engine...")
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        echo=False  # Set to True for SQL query logging
    )
    logger.info("SQLAlchemy engine created successfully")
except Exception as e:
    logger.error(f"Failed to create SQLAlchemy engine: {e}")
    raise

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
    try:
        logger.info("Attempting to connect to database and create tables...")

        # Test the connection first
        from sqlalchemy import text
        with engine.connect() as conn:
            logger.info("Database connection successful!")
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"PostgreSQL version: {version}")

        # Create tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")

    except Exception as e:
        logger.error(f"Failed to create tables: {type(e).__name__}: {e}")
        logger.error("Full error details:", exc_info=True)

        # Provide helpful error messages based on error type
        if "SSL" in str(e):
            logger.error("SSL connection issue detected. This may be due to:")
            logger.error("1. Database URL missing SSL parameters")
            logger.error("2. Incorrect SSL mode configuration")
            logger.error("3. Network or firewall issues")
            logger.error(f"Current database URL: {sanitize_url(database_url)}")

        raise