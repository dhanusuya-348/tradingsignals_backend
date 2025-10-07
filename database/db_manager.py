# database/db_manager.py

import sys
import os

# Add project root to path to import models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Signal, get_session_context
from datetime import datetime


def get_signal_by_id(signal_id):
    """
    Fetch a single signal by its unique ID from the database using SQLAlchemy.
    
    Args:
        signal_id (int or str): The unique ID of the signal
        
    Returns:
        dict: Signal data with all fields, or None if not found
    """
    try:
        with get_session_context() as session:
            # Query the signal by ID
            signal = session.query(Signal).filter(Signal.id == int(signal_id)).first()
            
            if not signal:
                print(f"⚠️ No signal found with ID: {signal_id}")
                return None
            
            # Extract payload JSON (which contains all your signal data)
            payload = signal.payload or {}
            
            # Build the response matching your expected format
            signal_data = {
                "id": signal.id,
                "symbol": signal.symbol,
                "interval": signal.timeframe,  # Your model uses 'timeframe'
                "signal": payload.get('signal', 'HOLD'),
                "confidence": payload.get('confidence', 0),
                "price": payload.get('price', 0),
                "sentiment": payload.get('sentiment', 'neutral'),
                "indicators": payload.get('indicators', {}),
                "risk": payload.get('risk', {}),
                "strategies": payload.get('strategies', {}),
                "decision": payload.get('decision', 'REJECTED'),
                "timing": payload.get('timing', {}),
                "scored_headlines": payload.get('scored_headlines', []),
                "created_at": signal.created_at.isoformat() if signal.created_at else datetime.utcnow().isoformat(),
                "pdf_url": signal.pdf_url
            }
            
            print(f"✅ Signal retrieved: {signal_data['symbol']} - {signal_data['signal']}")
            return signal_data
            
    except Exception as e:
        print(f"❌ Error fetching signal by ID: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_user_signals(user_sub, limit=50):
    """
    Get all signals for a specific user via UserSignal join table.
    
    Args:
        user_sub (str): User's unique identifier (Cognito user ID)
        limit (int): Maximum number of signals to return
        
    Returns:
        list: List of signal dictionaries
    """
    try:
        from models import UserSignal
        
        with get_session_context() as session:
            # Query signals through the UserSignal join table
            user_signals = (
                session.query(Signal)
                .join(UserSignal, Signal.id == UserSignal.signal_id)
                .filter(UserSignal.user_sub == user_sub)
                .order_by(Signal.created_at.desc())
                .limit(limit)
                .all()
            )
            
            signals = []
            for signal in user_signals:
                payload = signal.payload or {}
                
                signal_data = {
                    "id": signal.id,
                    "symbol": signal.symbol,
                    "interval": signal.timeframe,
                    "signal": payload.get('signal', 'HOLD'),
                    "confidence": payload.get('confidence', 0),
                    "price": payload.get('price', 0),
                    "sentiment": payload.get('sentiment', 'neutral'),
                    "indicators": payload.get('indicators', {}),
                    "risk": payload.get('risk', {}),
                    "strategies": payload.get('strategies', {}),
                    "decision": payload.get('decision', 'REJECTED'),
                    "timing": payload.get('timing', {}),
                    "scored_headlines": payload.get('scored_headlines', []),
                    "created_at": signal.created_at.isoformat() if signal.created_at else datetime.utcnow().isoformat(),
                    "pdf_url": signal.pdf_url
                }
                signals.append(signal_data)
            
            print(f"✅ Retrieved {len(signals)} signals for user {user_sub}")
            return signals
            
    except Exception as e:
        print(f"❌ Error fetching user signals: {e}")
        import traceback
        traceback.print_exc()
        return []


def update_signal_pdf_url(signal_id, pdf_url):
    """
    Update the PDF URL for a signal after PDF generation.
    
    Args:
        signal_id (int): Signal ID
        pdf_url (str): S3 URL or path to the generated PDF
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with get_session_context() as session:
            signal = session.query(Signal).filter(Signal.id == int(signal_id)).first()
            
            if not signal:
                print(f"⚠️ Signal {signal_id} not found")
                return False
            
            signal.pdf_url = pdf_url
            session.commit()
            
            print(f"✅ Updated PDF URL for signal {signal_id}")
            return True
            
    except Exception as e:
        print(f"❌ Error updating PDF URL: {e}")
        import traceback
        traceback.print_exc()
        return False