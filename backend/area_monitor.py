"""Area Monitor — Tracks occupancy per area and raises alerts
when people count drops below configured limits for 1+ hour.
Sends email alerts when thresholds are breached."""
import threading
import time
from collections import defaultdict
from datetime import datetime

import config
from backend.email_alerts import email_alerter


class AreaMonitor:
    """Monitors area-level occupancy trends and generates alerts."""

    def __init__(self, ai_engine=None, memory=None):
        self.ai_engine = ai_engine
        self.memory = memory
        self._lock = threading.Lock()

        # area -> latest people_count
        self._current_counts = defaultdict(int)

        # area -> peak count seen in the current session
        self._peak_counts = defaultdict(int)

        # area -> timestamp when count dropped below limit
        self._below_limit_start = {}

        # area -> configured people limit
        self._area_limits = {}

        # area -> list of alert dicts
        self.alerts = []

        # Load area limits from DB
        self._load_limits()

        # Background thread
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def _load_limits(self):
        """Load area limits from database."""
        if not self.memory:
            return
        try:
            limits = self.memory.get_area_limits()
            with self._lock:
                self._area_limits = limits
            print(f"  📋 Area limits loaded: {limits}")
        except Exception as e:
            print(f"  ⚠️ Could not load area limits: {e}")

    def reload_limits(self):
        """Reload area limits from database (called after API update)."""
        self._load_limits()

    def set_area_limit(self, area, limit):
        """Update limit in memory and in-memory cache."""
        with self._lock:
            self._area_limits[area] = limit
            # Reset drop tracking for this area
            self._below_limit_start.pop(area, None)

    def update_area(self, area, people_count):
        """Called periodically by the camera manager to report area counts."""
        with self._lock:
            self._current_counts[area] = people_count

            # Update peak
            if people_count > self._peak_counts[area]:
                self._peak_counts[area] = people_count

            # Check against configured limit
            area_limit = self._area_limits.get(area, 0)
            if area_limit > 0 and people_count < area_limit:
                # Count is below limit — start or continue timer
                if area not in self._below_limit_start:
                    self._below_limit_start[area] = time.time()
            else:
                # Count recovered or no limit set — cancel timer
                self._below_limit_start.pop(area, None)

    def _monitor_loop(self):
        """Background loop that checks for sustained drops below area limits."""
        alert_window_sec = config.MISSING_ALERT_WINDOW_MINUTES * 60

        while not self._stop.is_set():
            time.sleep(30)  # Check every 30 seconds

            with self._lock:
                now = time.time()
                areas_to_clear = []

                for area, start_time in self._below_limit_start.items():
                    elapsed = now - start_time
                    if elapsed >= alert_window_sec:
                        current = self._current_counts.get(area, 0)
                        area_limit = self._area_limits.get(area, 0)
                        missing = area_limit - current

                        if missing <= 0:
                            areas_to_clear.append(area)
                            continue

                        duration_min = int(elapsed / 60)

                        alert = {
                            "area": area,
                            "type": "MISSING_WORKERS",
                            "timestamp": datetime.now().isoformat(),
                            "message": (
                                f"⚠️ Area '{area}': {missing} worker(s) missing. "
                                f"Expected {area_limit}, currently {current}. "
                                f"Below limit for {duration_min}+ minutes."
                            ),
                            "expected_count": area_limit,
                            "current_count": current,
                            "missing_count": missing,
                            "duration_minutes": duration_min,
                        }
                        self.alerts.append(alert)
                        print(f"  🚨 ALERT: {alert['message']}")

                        # Log to AI engine
                        if self.ai_engine:
                            self.ai_engine._log_event(
                                "WARNING",
                                f"⚠️ Missing Workers — {area}",
                                alert["message"]
                            )

                        # Send email alert
                        email_alerter.send_missing_workers_alert(
                            area, current, area_limit, duration_min
                        )

                        areas_to_clear.append(area)

                # Reset timers for areas that triggered
                for area in areas_to_clear:
                    self._below_limit_start.pop(area, None)

    def get_alerts(self, limit=50):
        """Return recent alerts."""
        with self._lock:
            return self.alerts[-limit:]

    def get_status(self):
        """Return current monitoring status for all areas."""
        with self._lock:
            status = {}
            now = time.time()
            all_areas = set(
                list(self._current_counts.keys()) +
                list(self._peak_counts.keys()) +
                list(self._area_limits.keys())
            )
            for area in all_areas:
                drop_elapsed = None
                if area in self._below_limit_start:
                    drop_elapsed = int((now - self._below_limit_start[area]) / 60)

                area_limit = self._area_limits.get(area, 0)
                current = self._current_counts.get(area, 0)

                status[area] = {
                    "current_count": current,
                    "peak_count": self._peak_counts.get(area, 0),
                    "people_limit": area_limit,
                    "below_limit": area_limit > 0 and current < area_limit,
                    "below_limit_minutes": drop_elapsed,
                    "alert_threshold_minutes": config.MISSING_ALERT_WINDOW_MINUTES,
                }
            return status

    def stop(self):
        """Stop the monitor thread."""
        self._stop.set()
