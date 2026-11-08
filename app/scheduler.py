"""
SmartHire Background Task Scheduler.
Runs recurring background tasks such as the daily recruiter application summary email.
"""
import time
import threading
import logging
from datetime import datetime, timezone

logger = logging.getLogger("smarthire.scheduler")

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _scheduler_loop(app, daily_target_hour=18):
    """
    Background worker loop.
    Checks every 60 seconds whether the daily target hour (default 18:00 / 6 PM)
    has been reached and runs the daily digest once per day.
    """
    last_run_date = None
    logger.info(f"[SmartHire Scheduler] Background scheduler initialized. Daily summaries scheduled at {daily_target_hour:02d}:00.")

    while True:
        try:
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")

            # Check if it's the target hour and we haven't run today yet
            if now.hour == daily_target_hour and last_run_date != today_str:
                logger.info(f"[SmartHire Scheduler] Triggering daily summary job for {today_str}...")
                with app.app_context():
                    from app.mailer import send_all_recruiter_daily_summaries
                    results = send_all_recruiter_daily_summaries(since_hours=24)
                    logger.info(f"[SmartHire Scheduler] Completed daily summary run. Sent to {len(results)} recruiters.")
                last_run_date = today_str

            # Sleep 60 seconds between checks
            time.sleep(60)
        except Exception as e:
            logger.error(f"[SmartHire Scheduler] Error in scheduler loop: {e}")
            time.sleep(60)


def init_scheduler(app, daily_target_hour=18):
    """Start the scheduler background daemon thread if not already running."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

        thread = threading.Thread(
            target=_scheduler_loop,
            args=(app, daily_target_hour),
            daemon=True,
            name="SmartHire-DailyDigest-Scheduler"
        )
        thread.start()
        logger.info("[SmartHire Scheduler] Background daemon thread started successfully.")
