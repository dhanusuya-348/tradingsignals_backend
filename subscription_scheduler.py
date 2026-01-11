# subscription_scheduler.py
import schedule
import time
import threading
from subscription_utils import cleanup_expired_subscriptions

def run_cleanup_job():
    """Run the subscription cleanup job"""
    print("🧹 [SCHEDULER] Running subscription cleanup job...")
    count = cleanup_expired_subscriptions()
    print(f"🧹 [SCHEDULER] Cleanup completed. {count} subscriptions processed.")

def start_subscription_scheduler():
    """Start the subscription cleanup scheduler in a background thread"""
    # Schedule cleanup to run every hour
    schedule.every().hour.do(run_cleanup_job)
    
    # Also run once daily at 2 AM UTC for thorough cleanup
    schedule.every().day.at("02:00").do(run_cleanup_job)
    
    def scheduler_worker():
        print("🧹 [SCHEDULER] Subscription cleanup scheduler started")
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()
    
    print("✅ [SCHEDULER] Subscription cleanup scheduler initialized")

if __name__ == "__main__":
    # For testing
    run_cleanup_job()