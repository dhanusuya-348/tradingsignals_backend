#!/usr/bin/env python3
"""
Test script to verify signal_worker.py imports and functionality
Place this in your project root and run: python test_signal_worker.py
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from .env file
try:
    from load_env import load_env_file
    load_env_file()
    print("✅ Environment variables loaded from .env")
except ImportError:
    print("⚠️ load_env.py not found, using system environment variables")

def test_imports():
    """Test if all imports work"""
    print("🔍 Testing imports...")
    
    try:
        from models import get_session, Watchlist, Signal, UserSignal
        print("✅ Models imported successfully")
    except ImportError as e:
        print(f"❌ Models import error: {e}")
        return False
    
    try:
        from algo.runner import generate_live_signal_api
        print("✅ Algorithm runner imported successfully")
    except ImportError as e:
        print(f"❌ Algorithm runner import error: {e}")
        return False
    
    try:
        from aws_helpers import send_to_sqs_instant, send_to_sqs_pdf
        print("✅ AWS helpers imported successfully")
    except ImportError as e:
        print(f"❌ AWS helpers import error: {e}")
        return False
    
    return True

def test_algorithm():
    """Test if algorithm can run"""
    print("\n🔍 Testing algorithm...")
    
    try:
        from algo.runner import generate_live_signal_api
        
        # Test with ETH
        print("📊 Testing ETH algorithm...")
        result = generate_live_signal_api('ETH', '1h')
        
        if result:
            print(f"✅ Algorithm result: {result}")
            print(f"   Signal: {result.get('signal', 'N/A')}")
            print(f"   Confidence: {result.get('confidence', 'N/A')}%")
            return True
        else:
            print("❌ Algorithm returned None")
            return False
            
    except Exception as e:
        print(f"❌ Algorithm test error: {e}")
        import traceback
        print(f"🔧 Stack trace: {traceback.format_exc()}")
        return False

def test_database():
    """Test database connection"""
    print("\n🔍 Testing database connection...")
    
    try:
        from models import get_session, Watchlist
        
        session = get_session()
        
        # Test query
        watchlist_count = session.query(Watchlist).count()
        print(f"✅ Database connected. Found {watchlist_count} watchlist entries")
        
        # Get symbols
        symbols = session.query(Watchlist.symbol).distinct().all()
        symbol_list = [s[0] for s in symbols]
        print(f"📋 Unique symbols: {symbol_list}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test error: {e}")
        return False

def run_signal_worker_once():
    """Run signal worker process once (for testing)"""
    print("\n🔍 Testing signal worker process...")
    
    try:
        from signal_worker import process_watchlist
        
        print("🚀 Running signal worker process once...")
        process_watchlist()
        print("✅ Signal worker process completed")
        return True
        
    except Exception as e:
        print(f"❌ Signal worker process error: {e}")
        import traceback
        print(f"🔧 Stack trace: {traceback.format_exc()}")
        return False

def main():
    print("🚀 Signal Worker Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Algorithm Test", test_algorithm), 
        ("Database Test", test_database),
        ("Signal Worker Test", run_signal_worker_once)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*50)
    print("📊 TEST RESULTS:")
    print("="*50)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Your signal worker should work properly.")
        print("💡 To run continuously: python signal_worker.py")
    else:
        print("\n⚠️ Some tests failed. Fix the issues before deploying.")
        print("💡 Check the error messages above for troubleshooting.")

if __name__ == "__main__":
    main()