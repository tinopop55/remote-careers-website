import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

# Setup database
db_path = os.getenv('USER_DB_PATH', 'sqlite:///users.db')
engine = create_engine(db_path)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    language_preference = Column(String(10), default='ro')  # 'ro' or 'en'
    cv_analyzed_count = Column(Integer, default=0)
    last_analysis_at = Column(DateTime, nullable=True)
    subscribed_to_emails = Column(Boolean, default=True)
    
def setup_database():
    """Create tables if they don't exist"""
    Base.metadata.create_all(engine)

def register_user(email, language='ro'):
    """Register a new user or update existing user"""
    try:
        setup_database()
        session = Session()
        
        # Check if user exists
        user = session.query(User).filter_by(email=email).first()
        
        if user:
            # Update existing user
            user.updated_at = datetime.utcnow()
            user.language_preference = language
            logger.info(f"Updated existing user: {email}")
        else:
            # Create new user
            user = User(
                email=email,
                language_preference=language
            )
            session.add(user)
            logger.info(f"Registered new user: {email}")
        
        session.commit()
        session.close()
        return True
    except Exception as e:
        logger.error(f"Failed to register user: {e}")
        return False

def record_cv_analysis(email):
    """Record a CV analysis for a user"""
    try:
        session = Session()
        user = session.query(User).filter_by(email=email).first()
        
        if user:
            user.cv_analyzed_count += 1
            user.last_analysis_at = datetime.utcnow()
            session.commit()
            logger.info(f"Recorded CV analysis for user: {email}")
        
        session.close()
        return True
    except Exception as e:
        logger.error(f"Failed to record CV analysis: {e}")
        return False

def update_language_preference(email, language):
    """Update user's language preference"""
    try:
        session = Session()
        user = session.query(User).filter_by(email=email).first()
        
        if user:
            user.language_preference = language
            session.commit()
            logger.info(f"Updated language preference for user: {email} to {language}")
            success = True
        else:
            logger.warning(f"User not found: {email}")
            success = False
        
        session.close()
        return success
    except Exception as e:
        logger.error(f"Failed to update language preference: {e}")
        return False 