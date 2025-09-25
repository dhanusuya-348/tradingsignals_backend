# models.py
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime,
    JSON, Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session
from contextlib import contextmanager
import os

Base = declarative_base()

# ==========================
# DATABASE MODELS
# ==========================

class Watchlist(Base):
    __tablename__ = "watchlists"
    id = Column(Integer, primary_key=True)
    user_sub = Column(String, index=True)   # Cognito user ID
    email = Column(String, index=True)      # store email for notifications
    symbol = Column(String, index=True)
    created_at = Column(DateTime, nullable=False)


class Signal(Base):
    """
    Represents a unique trading signal for a coin+timeframe.
    Shared across many users via UserSignal.
    """
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    timeframe = Column(String, index=True)  # e.g., "1h", "4h"
    payload = Column(JSON)                  # JSON blob from algo
    created_at = Column(DateTime, nullable=False)
    pdf_url = Column(String, nullable=True) # S3 URL if PDF generated

    # Ensure uniqueness of signal per symbol+timeframe+created_at minute
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "created_at", name="uq_signal_per_coin_tf_time"),
    )

    # relationship to users
    users = relationship("UserSignal", back_populates="signal")


class UserSignal(Base):
    """
    Join table mapping users to signals.
    Each user gets notified once per signal.
    """
    __tablename__ = "user_signals"
    id = Column(Integer, primary_key=True)
    user_sub = Column(String, index=True)   # Cognito ID
    email = Column(String, index=True)      # Email address
    signal_id = Column(Integer, ForeignKey("signals.id"))
    delivery_status = Column(String, default="pending")  # pending/sent/failed

    signal = relationship("Signal", back_populates="users")


class User(Base):
    """
    User profile table to store Cognito user details
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_sub = Column(String, unique=True, index=True)  # Cognito user ID
    email = Column(String, unique=True, index=True)     # Email address
    name = Column(String, nullable=True)                # Display name
    phone = Column(String, nullable=True)               # Phone number for SMS
    subscription_status = Column(String, default="free") # free/active/cancelled
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


# ==========================
# DATABASE ENGINE & SESSIONS
# ==========================

def get_engine_from_env():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    engine = create_engine(
        db_url,
        pool_size=5,           # number of persistent connections
        max_overflow=5,        # extra connections beyond pool_size
        pool_timeout=30,       # wait time before giving up on a connection
        pool_recycle=1800,     # recycle connections every 30 minutes
        pool_pre_ping=True     # check connections before using
    )
    return engine

# Thread-safe scoped session
engine = get_engine_from_env()
SessionLocal = scoped_session(sessionmaker(bind=engine))

@contextmanager
def get_session_context():
    """Context manager for a DB session. Auto commit/rollback/close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

# Optional helper for legacy code (not recommended for heavy load)
def get_session():
    """Return a normal session (without context manager)."""
    return SessionLocal()
