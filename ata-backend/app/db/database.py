# /ata-backend/app/db/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Get the database URL from the environment variable we set on Railway.
# The second argument is a default value for local development.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# Create the SQLAlchemy engine.
# Configure connection pooling for production PostgreSQL to handle connection timeouts
if DATABASE_URL.startswith("sqlite"):
    engine_args = {"connect_args": {"check_same_thread": False}}
else:
    # PostgreSQL/Production settings
    engine_args = {
        "pool_pre_ping": True,  # Test connections before using them (fixes EOF errors)
        "pool_size": 10,  # Maximum number of connections to keep open
        "max_overflow": 20,  # Allow up to 20 additional connections beyond pool_size
        "pool_recycle": 3600,  # Recycle connections after 1 hour (3600 seconds)
        "pool_timeout": 30,  # Wait up to 30 seconds for a connection from the pool
        "connect_args": {
            "connect_timeout": 10,  # 10 second timeout for establishing new connections
            "options": "-c statement_timeout=30000"  # 30 second query timeout
        }
    }

engine = create_engine(DATABASE_URL, **engine_args)

# Create a SessionLocal class. Each instance of this class will be a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class. Our database model classes will inherit from this.
Base = declarative_base()

# Dependency to get a DB session. This will be used in our API routers.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()