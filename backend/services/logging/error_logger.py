import logging
import json
import traceback
from datetime import datetime
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup database
db_path = os.getenv('ERROR_DB_PATH', 'sqlite:///errors.db')
engine = create_engine(db_path)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class ErrorLog(Base):
    __tablename__ = 'error_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    error_type = Column(String(100))
    error_message = Column(Text)
    user_email = Column(String(255), nullable=True)
    request_data = Column(Text, nullable=True)  # JSON stringified
    stack_trace = Column(Text)
    
def setup_database():
    """Create tables if they don't exist"""
    Base.metadata.create_all(engine)
    
def log_error(error_type, error_message, user_email=None, request_data=None):
    """Log error to database and standard logger"""
    try:
        setup_database()
        stack_trace = traceback.format_exc()
        
        session = Session()
        error_log = ErrorLog(
            error_type=error_type,
            error_message=str(error_message),
            user_email=user_email,
            request_data=json.dumps(request_data) if request_data else None,
            stack_trace=stack_trace
        )
        
        session.add(error_log)
        session.commit()
        session.close()
        
        # Also log to standard logger
        logger.error(f"ERROR [{error_type}]: {error_message} | User: {user_email}")
        
    except Exception as e:
        # Fallback to standard logging if DB logging fails
        logger.error(f"Failed to log to database: {e}")
        logger.error(f"Original error [{error_type}]: {error_message} | User: {user_email}") 