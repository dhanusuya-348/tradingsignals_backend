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
    user_sub = Column(String, index=True, nullable=False)   # Cognito user ID
    email = Column(String, index=True, nullable=False)      # store email for notifications
    symbol = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Watchlist(user_sub={self.user_sub}, symbol={self.symbol})>"

class Signal(Base):
    """
    Represents a unique trading signal for a coin+timeframe.
    Shared across many users via UserSignal.
    """
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    timeframe = Column(String, index=True, nullable=False, default="1h")  # default 1h timeframe
    payload = Column(JSON, nullable=True)                  # JSON blob from algo
    created_at = Column(DateTime, nullable=False)
    pdf_url = Column(String, nullable=True)               # S3 URL if PDF generated
    processed = Column(Boolean, default=False, nullable=False)  # <--- ADDED

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "created_at", name="uq_signal_per_coin_tf_time"),
    )

    # relationship to users
    users = relationship("UserSignal", back_populates="signal", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Signal(symbol={self.symbol}, timeframe={self.timeframe}, created_at={self.created_at}, processed={self.processed})>"

class UserSignal(Base):
    """
    Join table mapping users to signals.
    Each user gets notified once per signal.
    """
    __tablename__ = "user_signals"
    id = Column(Integer, primary_key=True)
    user_sub = Column(String, index=True, nullable=False)   # Cognito ID
    email = Column(String, index=True, nullable=False)      # Email address
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=False)
    delivery_status = Column(String, default="pending", nullable=False)  # pending/sent/failed

    # === PDF-related columns ===
    pdf_status = Column(String, nullable=True)  # NULL / 'initiated' / 'generated' / 'failed'
    pdf_url = Column(String, nullable=True)     # S3 URL once PDF is generated

    signal = relationship("Signal", back_populates="users")

    def __repr__(self):
        return (f"<UserSignal(user_sub={self.user_sub}, signal_id={self.signal_id}, "
                f"delivery_status={self.delivery_status}, pdf_status={self.pdf_status})>")

class User(Base):
    """
    User profile table to store Cognito user details
    """
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_sub = Column(String, unique=True, index=True, nullable=False)  # Cognito user ID
    email = Column(String, unique=True, index=True, nullable=False)     # Email address
    name = Column(String, nullable=True)                                # Display name
    phone = Column(String, nullable=True)                               # Phone number for SMS
    subscription_status = Column(String, default="free", nullable=False) # free/active/cancelled
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<User(user_sub={self.user_sub}, email={self.email})>"

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

def get_session():
    """Return a normal session (without context manager)."""
    return SessionLocal()
