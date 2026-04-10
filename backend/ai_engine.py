"""AI Analytics Engine — Behavioral analysis, anomaly detection, predictions, and Voice AI."""
import threading
import time
import math
import os
import asyncio
import re
import subprocess
from collections import defaultdict, deque
from datetime import datetime

# Voice AI & LLM Imports
import ollama
from faster_whisper import WhisperModel
import edge_tts
import pygame


class AIAnalyticsEngine:
    """Intelligent analytics engine that derives insights from raw tracking data."""

    def __init__(self, memory=None):
        self.lock = threading.Lock()
        self.memory = memory
        self.camera_manager = None  # Set after CameraManager is created in app.py

        # --- Dwell Time Tracking ---
        self.person_enter_time = {}
        self.person_dwell_times = []
        self.active_dwell = {}

        # --- Loitering Detection ---
        self.person_positions = defaultdict(list)
        self.loitering_ids = set()

        # --- Occupancy Time Series ---
        self.occupancy_history = deque(maxlen=720)
        self.entry_timestamps = deque(maxlen=200)

        # --- Rush Hour / Pattern Analysis ---
        self.hourly_entries = defaultdict(int)
        self.minute_entries = defaultdict(int)

        # --- AI Event Log ---
        self.events = deque(maxlen=100)
        self.last_spike_alert = 0
        self.last_loiter_alert = {}

        # --- Prediction ---
        self.prediction_next_hour = 0
        self.trend = "stable"

        # --- System State ---
        self.system_status = "NORMAL"
        self.gpu_stats = {"utilization": 0, "memory_used": 0, "memory_total": 0}
        self.start_time = time.time()
        self._last_persist_time = time.time()

        # --- Voice AI Setup ---
        self.stt_model = None
        self._voice_lock = threading.Lock()
        
        # Initialize audio player gracefully (prevents crash on headless servers)
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize audio player (pygame.mixer): {e}")

        # --- Restore state from memory ---
        self._restore_state()

        self._log_event("INFO", "🧠 AI Analytics Engine initialized", "System started, learning patterns...")

    def _init_stt_model(self):
        """Initializes Faster-Whisper only when needed to save startup time."""
        if self.stt_model is None:
            print("⏳ Loading Faster-Whisper STT Model (large-v3)...")
            try:
                # Using full 'large-v3' for absolute maximum accuracy on RTX 5090
                self.stt_model = WhisperModel("large-v3", device="cuda", compute_type="float16")
                print("✅ STT Model Loaded successfully on GPU.")
            except Exception as e:
                print(f"⚠️ GPU load failed, falling back to CPU. Error: {e}")
                self.stt_model = WhisperModel("large-v3", device="cuda", compute_type="int8")
                print("✅ STT Model Loaded successfully on GPU (fallback).")

    def _get_gpu_stats(self):
        """Fetch real-time GPU metrics using nvidia-smi."""
        try:
            cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,nounits,noheader"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            util, used, total = map(int, result.stdout.strip().split(","))
            return {
                "utilization": util,
                "memory_used": used,
                "memory_total": total,
                "memory_percent": round((used / total) * 100, 1) if total > 0 else 0
            }
        except Exception:
            return {"utilization": 0, "memory_used": 0, "memory_total": 0, "memory_percent": 0}

    def _restore_state(self):
        """Restore persisted state from memory on startup."""
        if not self.memory:
            return
        try:
            saved = self.memory.load_all_state()
            if "hourly_entries" in saved:
                self.hourly_entries = defaultdict(int, {int(k): v for k, v in saved["hourly_entries"].items()})
            if "events" in saved:
                self.events = deque(saved["events"], maxlen=100)
            if "person_dwell_times" in saved:
                self.person_dwell_times = saved["person_dwell_times"]
            print("  💾 Restored AI engine state from memory")
        except Exception as e:
            print(f"  ⚠️ Could not restore state: {e}")

    def persist_state(self):
        """Save current state to memory (called periodically)."""
        if not self.memory:
            return
        try:
            with self.lock:
                self.memory.save_all_state({
                    "hourly_entries": dict(self.hourly_entries),
                    "events": list(self.events),
                    "person_dwell_times": self.person_dwell_times[-200:],
                })
        except Exception as e:
            print(f"  ⚠️ Could not persist state: {e}")

    def _log_event(self, severity, title, description):
        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "unix": time.time(),
            "severity": severity,
            "title": title,
            "description": description
        }
        with self.lock:
            self.events.appendleft(event)

    def update(self, detections, in_zone_a, in_zone_b, counted_in_ids, people_in_count, people_out_count, curr_time):
        occupancy = len(counted_in_ids)

        if len(self.occupancy_history) == 0 or (curr_time - (self.occupancy_history[-1][1] if self.occupancy_history else 0)) >= 5:
            self.occupancy_history.append((occupancy, curr_time))
            self._update_predictions(occupancy, curr_time)
            self._update_system_status(occupancy)

        # Persist state every 30 seconds
        if (curr_time - self._last_persist_time) > 30:
            self._last_persist_time = curr_time
            self.persist_state()

        if detections.tracker_id is not None:
            active_ids = set()
            for i, tracker_id_raw in enumerate(detections.tracker_id):
                tracker_id = int(tracker_id_raw)
                active_ids.add(tracker_id)
                is_in_b = in_zone_b[i] if i < len(in_zone_b) else False

                if is_in_b and tracker_id in counted_in_ids:
                    if tracker_id not in self.person_enter_time:
                        self.person_enter_time[tracker_id] = curr_time
                    self.active_dwell[tracker_id] = curr_time - self.person_enter_time[tracker_id]

                is_in_a = in_zone_a[i] if i < len(in_zone_a) else False
                if is_in_a:
                    x1, y1, x2, y2 = detections.xyxy[i].astype(int)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    positions = self.person_positions[tracker_id]
                    positions.append((cx, cy, curr_time))

                    while positions and (curr_time - positions[0][2]) > 60:
                        positions.pop(0)

                    if len(positions) > 5:
                        first = positions[0]
                        duration = curr_time - first[2]
                        xs = [p[0] for p in positions]
                        ys = [p[1] for p in positions]
                        movement = max(max(xs) - min(xs), max(ys) - min(ys))

                        if duration > 30 and movement < 80:
                            if tracker_id not in self.loitering_ids:
                                self.loitering_ids.add(tracker_id)
                                if tracker_id not in self.last_loiter_alert or (curr_time - self.last_loiter_alert[tracker_id]) > 60:
                                    self.last_loiter_alert[tracker_id] = curr_time
                                    self._log_event("WARNING", f"⚠️ Loitering Detected — Person #{tracker_id}",
                                                    f"Stationary in entry zone for {int(duration)}s with minimal movement ({int(movement)}px)")
                        else:
                            self.loitering_ids.discard(tracker_id)

            for tid in list(self.person_enter_time):
                if tid not in active_ids and tid not in counted_in_ids:
                    dwell = curr_time - self.person_enter_time[tid]
                    if dwell > 2:
                        self.person_dwell_times.append(dwell)
                    del self.person_enter_time[tid]
                    self.active_dwell.pop(tid, None)

    def log_entry(self, tracker_id, curr_time):
        tracker_id = int(tracker_id)
        self.entry_timestamps.append(curr_time)
        hour = datetime.fromtimestamp(curr_time).hour
        self.hourly_entries[hour] += 1
        minute_key = datetime.fromtimestamp(curr_time).strftime("%H:%M")[:4] + "0"
        self.minute_entries[minute_key] += 1

        recent = [t for t in self.entry_timestamps if (curr_time - t) <= 10]
        if len(recent) >= 3 and (curr_time - self.last_spike_alert) > 30:
            self.last_spike_alert = curr_time
            self._log_event("CRITICAL", "🚨 Occupancy Spike Detected",
                            f"{len(recent)} people entered in the last 10 seconds — possible rush event")

    def log_exit(self, tracker_id, reason="transition"):
        tracker_id = int(tracker_id)
        if tracker_id in self.person_enter_time:
            dwell = time.time() - self.person_enter_time[tracker_id]
            if dwell > 2:
                self.person_dwell_times.append(dwell)
            del self.person_enter_time[tracker_id]
            self.active_dwell.pop(tracker_id, None)

    def _update_predictions(self, current_occupancy, curr_time):
        if len(self.occupancy_history) < 6:
            self.prediction_next_hour = current_occupancy
            return

        values = [o[0] for o in list(self.occupancy_history)[-12:]]
        weights = list(range(1, len(values) + 1))
        wma = sum(v * w for v, w in zip(values, weights)) / sum(weights)

        if len(values) >= 6:
            first_half = sum(values[:len(values)//2]) / (len(values)//2)
            second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            diff = second_half - first_half
            if diff > 0.5:
                self.trend = "rising"
                self.prediction_next_hour = int(wma * 1.3)
            elif diff < -0.5:
                self.trend = "falling"
                self.prediction_next_hour = max(0, int(wma * 0.7))
            else:
                self.trend = "stable"
                self.prediction_next_hour = int(wma)

    def _update_system_status(self, occupancy):
        old_status = self.system_status
        if occupancy >= 10 or len(self.loitering_ids) > 0:
            self.system_status = "CRITICAL"
        elif occupancy >= 7 or self.trend == "rising":
            self.system_status = "ELEVATED"
        else:
            self.system_status = "NORMAL"

        if self.system_status != old_status:
            emoji = {"NORMAL": "✅", "ELEVATED": "🟡", "CRITICAL": "🔴"}[self.system_status]
            self._log_event("INFO", f"{emoji} System Status → {self.system_status}",
                            f"Occupancy: {occupancy}, Trend: {self.trend}, Loitering: {len(self.loitering_ids)}")

    def reset(self):
        """Reset all analytics history and state."""
        with self.lock:
            self.person_enter_time = {}
            self.person_dwell_times = []
            self.active_dwell = {}
            self.person_positions = defaultdict(list)
            self.loitering_ids = set()
            self.occupancy_history.clear()
            self.entry_timestamps.clear()
            self.hourly_entries = defaultdict(int)
            self.minute_entries = defaultdict(int)
            self.events.clear()
            self.last_spike_alert = 0
            self.last_loiter_alert = {}
            self.prediction_next_hour = 0
            self.trend = "stable"
            self.system_status = "NORMAL"
        self._log_event("INFO", "🧹 Analytics Reset", "All historical data and state has been cleared.")
        self.persist_state()

    def get_insights(self):
        with self.lock:
            all_dwells = self.person_dwell_times + list(self.active_dwell.values())
            avg_dwell = sum(all_dwells) / len(all_dwells) if all_dwells else 0
            max_dwell = max(all_dwells) if all_dwells else 0

            peak_hour = max(self.hourly_entries, key=self.hourly_entries.get) if self.hourly_entries else None
            peak_hour_str = f"{peak_hour}:00" if peak_hour is not None else "N/A"

            occ_trend = [o[0] for o in list(self.occupancy_history)[-20:]]

            uptime_sec = time.time() - self.start_time
            uptime_str = f"{int(uptime_sec // 3600)}h {int((uptime_sec % 3600) // 60)}m"

            gpu = self._get_gpu_stats()

            return {
                "system_status": self.system_status,
                "gpu": gpu,
                "trend": self.trend,
                "prediction_next_hour": self.prediction_next_hour,
                "avg_dwell_seconds": round(avg_dwell, 1),
                "max_dwell_seconds": round(max_dwell, 1),
                "active_dwell_count": len(self.active_dwell),
                "loitering_count": len(self.loitering_ids),
                "loitering_ids": list(self.loitering_ids),
                "peak_hour": peak_hour_str,
                "total_entries_session": sum(self.hourly_entries.values()),
                "occupancy_trend": occ_trend,
                "uptime": uptime_str,
                "events_count": len(self.events)
            }

    def get_events(self, limit=50):
        with self.lock:
            return list(self.events)[:limit]

    def get_heatmap_data(self):
        with self.lock:
            return {
                "hourly_entries": dict(self.hourly_entries),
                "minute_entries": dict(self.minute_entries),
                "total_dwell_samples": len(self.person_dwell_times),
                "avg_dwell": round(sum(self.person_dwell_times) / len(self.person_dwell_times), 1) if self.person_dwell_times else 0
            }

    # =========================================================================
    # --- FACILITY NAME NORMALIZER ---
    # =========================================================================

    def _normalize_facility_query(self, text):
        """Normalize all variations of facility/building names to canonical form.
        
        Handles: df3, df-3, df03, df-03, df 3, df 03, d.f.3, d f 3,
                 DF3, DF-3, DF03, DF-03, pdf, pdf free, bf 3, etc.
        All map to canonical 'DF-3'.
        """
        import re
        
        # --- Phonetic / STT misheard corrections ---
        phonetic_corrections = {
            r"\bpdf free\b": "DF-3",
            r"\bpdf 3\b": "DF-3",
            r"\bpdf3\b": "DF-3",
            r"\bpdf\b": "DF-3",
            r"\bbf[- ]?3\b": "DF-3",
            r"\bdf free\b": "DF-3",
            r"\btf[- ]?3\b": "DF-3",
            r"\bthe f[- ]?3\b": "DF-3",
        }
        for pattern, replacement in phonetic_corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # --- Canonical facility name normalization ---
        # Matches: df3, df-3, df03, df-03, df 3, df 03, d.f.3, d f 3, d-f-3, etc.
        # Captures the building number (with optional leading zero)
        def normalize_df(match):
            num = match.group(1).lstrip('0') or '0'  # strip leading zeros: 03 -> 3
            return f"DF-{num}"
        
        text = re.sub(
            r'\bd[\s.\-_]*f[\s.\-_]*0*(\d+)\b',
            normalize_df,
            text,
            flags=re.IGNORECASE
        )
        
        # --- General term corrections ---
        general_corrections = {
            r"\bincome\b": "in-count",
            r"\bin come\b": "in-count",
            r"\boutcome\b": "out-count",
            r"\bout come\b": "out-count",
        }
        for pattern, replacement in general_corrections.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    # =========================================================================
    # --- VOICE AI PIPELINE (STT -> LLM -> TTS) ---
    # =========================================================================

    def handle_query(self, query):
        """Processes a text query with a tightly-controlled, intelligent persona."""
        import re
        
        # 0. PRE-PROCESS QUERY (Normalize facility names + fix misheard terms)
        query_lower = self._normalize_facility_query(query.lower())
        
        # 1. IDENTIFY TARGET FACILITY (e.g., DF-3, DF-03, DF3)
        target_facility = None
        target_building_num = None
        
        # Extract numeric building ID (e.g., "3" from "DF3" or "DF-03")
        num_match = re.search(r'DF-?0*(\d+)', query_lower)
        if num_match:
            target_building_num = num_match.group(1)
            target_facility = f"DF-{target_building_num}" # Canonical search key
        
        # 2. GET ALL GLOBAL & SPECIFIC INSIGHTS
        insights = self.get_insights()
        
        area_breakdown = ""
        total_occupancy = 0
        total_in_count = 0
        total_out_count = 0
        
        # Facility-specific aggregation (Fuzzy)
        facility_stats = {"occupancy": 0, "in": 0, "out": 0, "cameras": [], "areas": []}
        
        # Collect area limits for context
        area_limits_info = ""
        if self.memory:
            try:
                area_limits = self.memory.get_area_limits()
                if area_limits:
                    for area_name, limit in area_limits.items():
                        if limit and limit > 0:
                            area_limits_info += f"- {area_name}: max capacity {limit} people.\n"
            except Exception:
                pass
        
        # READ LIVE STATS from camera processors (not stale SQLite)
        if self.camera_manager:
            try:
                all_stats = self.camera_manager.get_all_stats()
                # Group stats by area for a cleaner summary
                from collections import defaultdict
                area_data = defaultdict(lambda: {"occupancy": 0, "in": 0, "out": 0, "cameras": []})
                
                for cam_stats in all_stats:
                    cam_name = cam_stats.get("name", "Unknown")
                    cam_area = cam_stats.get("area", "Unknown")
                    cam_plant = cam_stats.get("plant", "Unknown")
                    cam_in = cam_stats.get("in", 0)
                    cam_out = cam_stats.get("out", 0)
                    occ = cam_stats.get("people_count", 0)
                    
                    total_in_count += cam_in
                    total_out_count += cam_out
                    total_occupancy += occ
                    
                    # Store in area grouping
                    area_data[cam_area]["occupancy"] += occ
                    area_data[cam_area]["in"] += cam_in
                    area_data[cam_area]["out"] += cam_out
                    area_data[cam_area]["cameras"].append(cam_name)
                    
                    # FUZZY MATCHING FOR FACILITY
                    is_match = False
                    if target_building_num:
                        patterns = [
                            f"DF-{target_building_num}", 
                            f"DF-0{target_building_num}", 
                            f"DF{target_building_num}",
                            f"DF {target_building_num}"
                        ]
                        # Check camera name, area name, AND plant name
                        if any(p.lower() in cam_name.lower() for p in patterns):
                            is_match = True
                        if any(p.lower() in cam_area.lower() for p in patterns):
                            is_match = True
                        if any(p.lower() in cam_plant.lower() for p in patterns):
                            is_match = True
                            
                    if is_match:
                        facility_stats["occupancy"] += occ
                        facility_stats["in"] += cam_in
                        facility_stats["out"] += cam_out
                        if cam_name not in facility_stats["cameras"]:
                            facility_stats["cameras"].append(cam_name)
                        if cam_area not in facility_stats["areas"]:
                            facility_stats["areas"].append(cam_area)
                
                for area_name, data in area_data.items():
                    cam_names = ", ".join(data["cameras"])
                    area_breakdown += (
                        f"- {area_name} (cameras: {cam_names}): "
                        f"{data['occupancy']} people inside "
                        f"(Entries: {data['in']}, Exits: {data['out']}).\n"
                    )
            except Exception as e:
                print(f"  ⚠️ AI live stats read error: {e}")
                area_breakdown = "- Area data unavailable."
        elif self.memory:
            # Fallback to SQLite if camera_manager not set
            try:
                cameras = self.memory.get_cameras(active_only=True)
                from collections import defaultdict
                area_data = defaultdict(lambda: {"occupancy": 0, "in": 0, "out": 0, "cameras": []})
                
                for cam in cameras:
                    cam_id = cam["id"]
                    cam_name = cam.get("name", "Unknown")
                    cam_area = cam.get("area", "Unknown")
                    cam_plant = cam.get("plant", "Unknown")
                    cam_in = self.memory.load_state(f"cam_{cam_id}_in", 0)
                    cam_out = self.memory.load_state(f"cam_{cam_id}_out", 0)
                    total_in_count += cam_in
                    total_out_count += cam_out
                    
                    # Ensure fallback matches instantaneous count goal (which is 0 when offline)
                    occ = 0
                    total_occupancy += occ
                    
                    area_data[cam_area]["occupancy"] += occ
                    area_data[cam_area]["in"] += cam_in
                    area_data[cam_area]["out"] += cam_out
                    area_data[cam_area]["cameras"].append(cam_name)

                    # FUZZY MATCHING
                    is_match = False
                    if target_building_num:
                        patterns = [f"DF-{target_building_num}", f"DF-0{target_building_num}", f"DF{target_building_num}"]
                        if any(p.lower() in cam_name.lower() for p in patterns) or \
                           any(p.lower() in cam_area.lower() for p in patterns) or \
                           any(p.lower() in cam_plant.lower() for p in patterns):
                            is_match = True
                            
                    if is_match:
                        facility_stats["occupancy"] += occ
                        facility_stats["in"] += cam_in
                        facility_stats["out"] += cam_out
                        facility_stats["cameras"].append(cam_name)
                
                for area_name, data in area_data.items():
                    cam_names = ", ".join(data["cameras"])
                    area_breakdown += (
                        f"- {area_name} (cameras: {cam_names}): "
                        f"{data['occupancy']} people inside "
                        f"(Entries: {data['in']}, Exits: {data['out']}).\n"
                    )
            except Exception:
                area_breakdown = "- Area data unavailable."

        # 3. ADD A DYNAMIC "LIVE ALERTS" CONTEXT BLOCK
        live_alerts = ""
        loitering_ids = list(insights.get('loitering_ids', []))
        if loitering_ids:
            live_alerts += f"- CRITICAL: Loitering detected for Person ID(s) {', '.join(map(str, loitering_ids))}.\n"
        if insights['trend'] == 'rising':
            live_alerts += f"- INFO: Occupancy is currently rising.\n"
        if not live_alerts:
            live_alerts = "- No critical alerts."

        # 4. BUILD THE FULL CONTEXT
        area_limits_section = area_limits_info if area_limits_info else "- No capacity limits configured."
        
        target_facility_info = ""
        if target_facility and facility_stats["cameras"]:
            area_names = ", ".join(facility_stats["areas"])
            target_facility_info = f"""
            [VERIFIED BUILDING STATISTICS (PRIMARY SOURCE)]
            Target Identifiers: {target_facility}, {target_facility.replace('-', '-0')}
            Detected Areas: {area_names}
            - Combined Occupancy (Active Now): {facility_stats['occupancy']} people
            - Total Entries Today: {facility_stats['in']}
            - Total Exits Today: {facility_stats['out']}
            - Verification: Summed across {len(facility_stats['cameras'])} cameras: {", ".join(facility_stats["cameras"])}
            """

        context = f"""
        {target_facility_info}
        
        [GLOBAL SYSTEM METRICS]
        Overall Status: {insights['system_status']}
        Total People Currently Inside (all areas combined): {total_occupancy}
        Total Entries Today (In-Count): {total_in_count}
        Total Exits Today (Out-Count): {total_out_count}
        
        [AREA BREAKDOWN]
        {area_breakdown}
        [AREA CAPACITY LIMITS]
        {area_limits_section}
        
        [LIVE ALERTS]
        {live_alerts}
        """

        # 5. CHAT HISTORY
        history_messages = []
        if self.memory:
            chat_history = self.memory.get_chat_history(limit=2)
            for msg in chat_history:
                history_messages.append({'role': msg['role'], 'content': msg['content']})

        # 6. THE NEW, TIGHTLY-CONTROLLED PROMPT
        # 6. THE NEW, TIGHTLY-CONTROLLED PROMPT
        prompt = f"""You are 'Sentinel', a professional security AI assistant.

**CRITICAL RULES:**
1. Reply ONLY in concise, professional English.
2. Address the user respectfully as 'Sir'.
3. Base your answer ONLY on the [CURRENT LIVE DATA]. Do NOT invent data.
4. When asked about a specific building's occupancy (e.g. DF3, DF-03), YOU MUST ONLY use the "Combined Occupancy (Active Now)" from the [VERIFIED BUILDING STATISTICS] block exactly as provided. DO NOT add numbers together. DO NOT mention individual areas like "Spinning Area 3".
5. IGNORE individual area breakdowns if a [VERIFIED BUILDING STATISTICS] block exists.
6. NEVER use financial terms, money, or dollar signs ($).
7. Format your response EXACTLY like this template: "Sir, [Number] people are currently inside [Facility/Area Name]." (Replace [Number] with the Combined Occupancy).
8. Do NOT say "X out of Y" unless Y is specifically labeled as a capacity limit in [AREA CAPACITY LIMITS].
9. If you mention entries or exits, clarify them as "Total entries today" or "Total exits today".

[CURRENT LIVE DATA]
{context}

User Query: {query_lower}
English Response:"""

        try:
            # The system message reinforces the core rule.
            messages = [{'role': 'system', 'content': "You are Sentinel, a professional security AI. Speak only in concise English. Be respectful (use Sir). Never output financial data or dollar amounts."}]
            messages.extend(history_messages)
            messages.append({'role': 'user', 'content': prompt})
            
            # Using Llama 3.1
            response = ollama.chat(model='llama3.1', messages=messages)
            response_text = response['message']['content'].strip()

            # =================================================================
            # 🛡️ BULLETPROOF POST-PROCESSING (Prevents hallucinations/brackets)
            # =================================================================
            
            # 1. Physically remove anything inside parentheses () or brackets []
            response_text = re.sub(r'\(.*?\)|\[.*?\]', '', response_text)
            
            # 2. Remove quotation marks and financial symbols if the LLM hallucinates them
            response_text = response_text.replace('"', '').replace("'", "").replace("$", "")
            
            # 3. Clean up any accidental double spaces left by the regex removal
            response_text = " ".join(response_text.split())

            if self.memory:
                self.memory.save_chat('user', query)
                self.memory.save_chat('assistant', response_text)

            return response_text
        except Exception as e:
            print(f"Ollama Error: {e}")
            return f"Sir, there is a system error, but currently {insights['active_dwell_count']} people are inside."

    def process_voice_command(self, audio_file_path):
        """End-to-End Voice Pipeline with VAD, Phonetic Correction, and Playback"""
        with self._voice_lock:
            self._init_stt_model()
            print("🎙️ Transcribing audio...")
            
            # 1. ENGLISH CONTEXT PROMPT
            english_context = "Sir, check the in-count and out-count for the main entrance. Identify any loitering events."
            
            # 2. RUN WHISPER WITH VAD & LANGUAGE LOCK (English)
            segments, _ = self.stt_model.transcribe(
                audio_file_path, 
                beam_size=5,         # Maximum accuracy for RTX 5090
                language="en",       # Force English
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                initial_prompt=english_context
            )
            
            user_text = "".join([segment.text for segment in segments]).strip()
            
            if not user_text:
                return {"user_text": "", "response_text": "I am sorry, I could not hear you.", "audio_path": None}
            
            # 3. PHONETIC POST-PROCESSOR (uses shared normalizer)
            corrected_text = self._normalize_facility_query(user_text.lower())
            
            print(f"🗣️ Raw STT: {user_text}")
            print(f"🛠️ Corrected STT: {corrected_text}")

            # 4. GET LLM RESPONSE
            print("🧠 Generating AI Response (Llama 3.1)...")
            response_text = self.handle_query(corrected_text)
            print(f"🤖 AI: {response_text}")

            # 5. TEXT-TO-SPEECH & PLAYBACK
            output_audio_path = os.path.join(os.path.dirname(__file__), "response.wav")
            print("🔊 Generating Speech...")
            
            try:
                tts_voice = "en-US-AvaNeural" 
                
                async def generate_audio():
                    communicate = edge_tts.Communicate(response_text, tts_voice)
                    await communicate.save(output_audio_path)
                
                asyncio.run(generate_audio())
                
                # Play audio using pygame
                pygame.mixer.music.load(output_audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            except Exception as e:
                print(f"⚠️ Audio Playback Error: {e}")

            return {
                "user_text": corrected_text,
                "response_text": response_text,
                "audio_path": output_audio_path
            }




























































