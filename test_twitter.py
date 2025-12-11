# test_twitter.py
# Quick local test for Twitter service

import os
import sys

# Load .env variables
try:
    from load_env import load_env_file
    load_env_file()
    print("✅ Loaded .env variables\n")
except ImportError:
    print("⚠️  load_env.py not found, using system environment\n")

# Import Twitter service
try:
    from twitter_service import TwitterService
    print("✅ Imported TwitterService\n")
except Exception as e:
    print(f"❌ Failed to import TwitterService: {e}")
    sys.exit(1)

# Initialize service
try:
    twitter_service = TwitterService()
    print("✅ TwitterService initialized\n")
except Exception as e:
    print(f"❌ Failed to initialize TwitterService: {e}")
    sys.exit(1)

# Test 1: Connection
print("=" * 60)
print("TEST 1: Testing Connection")
print("=" * 60)
try:
    result = twitter_service.test_connection()
    if result:
        print("✅ CONNECTION SUCCESSFUL!\n")
    else:
        print("❌ Connection failed\n")
except Exception as e:
    print(f"❌ Error: {e}\n")

# Test 2: Post a signal
print("=" * 60)
print("TEST 2: Posting a Test Signal")
print("=" * 60)
try:
    tweet_id = twitter_service.post_signal_performance(
        symbol="BTC",
        entry_price=45000.50,
        exit_price=46500.75,
        return_percent=3.33,
        profit_usd=150.25,
        result="SUCCESS",
        duration_minutes=45
    )
    
    if tweet_id:
        print(f"✅ TWEET POSTED SUCCESSFULLY!")
        print(f"   Tweet ID: {tweet_id}")
        print(f"   URL: https://x.com/@dollaraptor/status/{tweet_id}\n")
    else:
        print("❌ Failed to post tweet\n")
except Exception as e:
    print(f"❌ Error: {e}\n")
    import traceback
    traceback.print_exc()

# Test 3: Post daily summary
print("=" * 60)
print("TEST 3: Posting Daily Summary")
print("=" * 60)
try:
    tweet_id = twitter_service.post_daily_performance_summary(
        total_signals=5,
        wins=4,
        losses=1,
        win_rate=80.0,
        total_profit=250.50,
        avg_return=2.15
    )
    
    if tweet_id:
        print(f"✅ DAILY SUMMARY POSTED!")
        print(f"   Tweet ID: {tweet_id}")
        print(f"   URL: https://x.com/@dollaraptor/status/{tweet_id}\n")
    else:
        print("❌ Failed to post daily summary\n")
except Exception as e:
    print(f"❌ Error: {e}\n")
    import traceback
    traceback.print_exc()

# Test 4: Post custom message
print("=" * 60)
print("TEST 4: Posting Custom Message")
print("=" * 60)
try:
    tweet_id = twitter_service.post_custom_message(
        "🚀 DollaRaptor is now live! Automated crypto trading signals coming to X.com #Trading #Crypto"
    )
    
    if tweet_id:
        print(f"✅ CUSTOM MESSAGE POSTED!")
        print(f"   Tweet ID: {tweet_id}")
        print(f"   URL: https://x.com/@dollaraptor/status/{tweet_id}\n")
    else:
        print("❌ Failed to post custom message\n")
except Exception as e:
    print(f"❌ Error: {e}\n")
    import traceback
    traceback.print_exc()

print("=" * 60)
print("ALL TESTS COMPLETED!")
print("=" * 60)
print("\nIf all tests passed, your Twitter integration is working! 🎉")
print("Check your X.com account for the posted tweets.")