"""
AIDE-X Database Module
SQLite integration with SQLAlchemy ORM
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging

logger = logging.getLogger("AIDE-X.database")

DATABASE_URL = "sqlite:///./aide_x.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── ORM Models ───────────────────────────────────────────────────────────────

class WorkflowTask(Base):
    """Stores every processed workflow request."""
    __tablename__ = "workflow_tasks"

    id = Column(Integer, primary_key=True, index=True)
    raw_input = Column(Text, nullable=False)
    intent = Column(String(100))
    entities = Column(JSON)             # JSON blob of extracted entities
    confidence = Column(Float)
    execution_mode = Column(String(50)) # auto_execute | request_approval | clarification_needed
    status = Column(String(50), default="pending")
    result_message = Column(Text)
    risk_level = Column(String(20))
    compliance_status = Column(String(20))
    agent_logs = Column(JSON)           # Full multi-agent log
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    """Immutable audit trail for all executions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer)
    action = Column(String(100))
    actor = Column(String(50), default="AIDE-X")
    details = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_db():
    """Dependency: yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created/verified.")