"""Email Alert Module — sends SMTP emails when area headcount drops below limits."""
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import config


class EmailAlerter:
    """Thread-safe email alerter with per-area cooldowns."""

    def __init__(self):
        self._lock = threading.Lock()
        # area -> last email sent timestamp
        self._last_sent = {}

    def send_missing_workers_alert(self, area, current_count, expected_limit, duration_minutes):
        """Send email alert for missing workers in an area.
        
        Respects cooldown: won't re-send for the same area within ALERT_COOLDOWN_MINUTES.
        """
        with self._lock:
            now = time.time()
            last = self._last_sent.get(area, 0)
            cooldown_sec = config.ALERT_COOLDOWN_MINUTES * 60

            if (now - last) < cooldown_sec:
                return False  # Still in cooldown

            # Build email
            missing = expected_limit - current_count
            subject = f"⚠️ ALERT: {missing} worker(s) missing in {area}"
            body = f"""
Headcount Alert — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Area: {area}
Expected workers: {expected_limit}
Current count: {current_count}
Missing: {missing} worker(s)
Duration below limit: {duration_minutes} minutes

This alert was triggered because the headcount in "{area}" has been 
below the configured limit of {expected_limit} for {duration_minutes} minutes.

— Headcount AI Command Center
"""

            success = self._send_email(subject, body.strip())
            if success:
                self._last_sent[area] = now
                print(f"  📧 Alert email sent for area '{area}': {missing} missing")
            return success

    def _send_email(self, subject, body):
        """Send email via SMTP. Returns True on success."""
        if not config.SMTP_USER or not config.ALERT_RECIPIENTS:
            print("  ⚠️ Email alert skipped: SMTP_USER or ALERT_RECIPIENTS not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = config.SMTP_USER
            msg['To'] = ', '.join(config.ALERT_RECIPIENTS)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                server.starttls()
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(msg)

            return True
        except Exception as e:
            print(f"  ❌ Email send failed: {e}")
            return False


# Singleton instance
email_alerter = EmailAlerter()
