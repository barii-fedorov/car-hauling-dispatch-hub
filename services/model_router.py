"""
Model Router & AI Quota Manager for Car Hauling Dispatch Hub
Features:
1. Programmatic Request Difficulty Rating (0 to 3).
2. Dynamic Model Selection based on complexity & live RPM quotas.
3. 429 Circuit Breaker with automatic failover (Gemini 3 Flash -> 2.5 Flash -> 1.5 Flash -> Algorithmic).
4. Live Prometheus Metrics Exporter (HTTP :8000) for Grafana dashboards.
"""

import os
import re
import time
import json
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import deque

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Available Gemini Model Hierarchy
MODELS = {
    "gemini-3-flash-preview": {
        "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={GEMINI_API_KEY}",
        "max_rpm": 15,
        "role": "High reasoning / broker intelligence / multi-stop logistics"
    },
    "gemini-2.5-flash": {
        "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        "max_rpm": 30,
        "role": "Fast tactical dispatch / fuel geocoding / claim customization"
    },
    "gemini-1.5-flash": {
        "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        "max_rpm": 30,
        "role": "High-throughput fallback"
    }
}

class ModelMetricsTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.request_timestamps = {m: deque() for m in MODELS}
        self.requests_total = {m: {"200": 0, "429": 0, "err": 0} for m in MODELS}
        self.cooldown_until = {m: 0.0 for m in MODELS}
        self.difficulty_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        self.model_switches_total = 0

    def record_difficulty(self, level: int):
        with self.lock:
            self.difficulty_counts[level] = self.difficulty_counts.get(level, 0) + 1

    def get_active_rpm(self, model: str) -> float:
        now = time.time()
        with self.lock:
            q = self.request_timestamps.get(model, deque())
            # Evict timestamps older than 60s
            while q and (now - q[0]) > 60.0:
                q.popleft()
            return float(len(q))

    def is_model_available(self, model: str) -> bool:
        now = time.time()
        with self.lock:
            if now < self.cooldown_until.get(model, 0.0):
                return False
            q = self.request_timestamps.get(model, deque())
            while q and (now - q[0]) > 60.0:
                q.popleft()
            max_rpm = MODELS.get(model, {}).get("max_rpm", 15)
            # Circuit breaker: reserve 15% headroom
            return len(q) < (max_rpm * 0.85)

    def record_request_start(self, model: str):
        now = time.time()
        with self.lock:
            if model in self.request_timestamps:
                self.request_timestamps[model].append(now)

    def record_result(self, model: str, status_code: int):
        with self.lock:
            if model not in self.requests_total:
                return
            if status_code == 200:
                self.requests_total[model]["200"] += 1
            elif status_code == 429:
                self.requests_total[model]["429"] += 1
                # Put model on 30s cooldown
                self.cooldown_until[model] = time.time() + 30.0
            else:
                self.requests_total[model]["err"] += 1

    def record_switch(self):
        with self.lock:
            self.model_switches_total += 1

    def generate_prometheus_metrics(self) -> str:
        lines = []
        lines.append("# HELP gemini_requests_total Total Gemini API requests by model and status")
        lines.append("# TYPE gemini_requests_total counter")
        for m, stats in self.requests_total.items():
            for code, cnt in stats.items():
                lines.append(f'gemini_requests_total{{model="{m}",status="{code}"}} {cnt}')

        lines.append("\n# HELP gemini_active_rpm Current requests per minute in sliding 60s window")
        lines.append("# TYPE gemini_active_rpm gauge")
        for m in MODELS:
            rpm = self.get_active_rpm(m)
            lines.append(f'gemini_active_rpm{{model="{m}"}} {rpm:.1f}')

        lines.append("\n# HELP gemini_request_difficulty_total Total requests by difficulty level")
        lines.append("# TYPE gemini_request_difficulty_total counter")
        diff_names = {0: "0_deterministic", 1: "1_routine", 2: "2_tactical", 3: "3_complex_dispute"}
        for lvl, cnt in self.difficulty_counts.items():
            name = diff_names.get(lvl, str(lvl))
            lines.append(f'gemini_request_difficulty_total{{level="{name}"}} {cnt}')

        lines.append("\n# HELP gemini_model_switches_total Total dynamic model fallbacks triggered")
        lines.append("# TYPE gemini_model_switches_total counter")
        lines.append(f"gemini_model_switches_total {self.model_switches_total}")

        return "\n".join(lines) + "\n"

# Global tracker instance
metrics_tracker = ModelMetricsTracker()

# ==========================================
# 1. Programmatic Request Difficulty Rating
# ==========================================
def rate_request_difficulty(prompt: str, context_type: str = "general") -> tuple[int, str]:
    """
    Rates incoming user query complexity from 0 to 3:
    Level 0: Deterministic / Instant lookup (overhang, claim template, help, regex) -> 0 LLM tokens
    Level 1: Routine facts & geocoding (diesel station search, short single question) -> Gemini 2.5 Flash
    Level 2: Tactical Car Hauler Reasoning (broker compliance check, repair shop radius, multi-state limits) -> Gemini 3 Flash / 2.5 Flash
    Level 3: Complex Legal / Dispute (broker rate con dispute, damages, broker scam investigation) -> Gemini 3 Flash / Pro
    """
    text_lower = prompt.lower()
    words = text_lower.split()

    # Level 0 Check: Commands & Deterministic Lookups
    if any(cmd in text_lower for cmd in ["/overhang", "/claim", "/detention", "/tonu", "/inop", "/help", "свесы", "клеймы", "шаблоны"]):
        return 0, "Deterministic lookup (zero LLM tokens needed)"

    # Level 3 Check: High-stakes disputes, damage, legal threats
    dispute_indicators = [
        "не платит", "отказывается платить", "подал клейм", "повреждение", "поцарапали крышу",
        "суд", "юрист", "дабл брокер", "scam", "hold", "stolen", "lawsuit", "dispute",
        "short pay", "deduction", "claims department", "полиция", "dot inspection oos"
    ]
    if any(k in text_lower for k in dispute_indicators) or (len(words) > 120 and "брокер" in text_lower):
        return 3, "High-stakes dispute / legal negotiation / broker claim"

    # Level 2 Check: Broker dossiers, repair matching, complex logistics
    tactical_indicators = [
        "mc #", "mc#", "проверить брокера", "пробей mc", "бонд", "факторинг", "quickpay",
        "ремонт", "лопнул шланг", "сварка", "гидравлика", "электрика", "стингер", "boydstun",
        "cottrell", "kpra", "bridge formula", "развесовка"
    ]
    if context_type in ["broker", "repair"] or any(k in text_lower for k in tactical_indicators):
        return 2, "Tactical car hauling operations / broker verification"

    # Default: Level 1 Routine
    return 1, "Routine navigation / fuel / short inquiry"

# ==========================================
# 2. Dynamic Model Selector with Quota Check
# ==========================================
def select_model_for_request(difficulty: int) -> str:
    """
    Selects the best available model based on difficulty and live RPM headroom.
    Automatically steps down if higher model is 429-cooldown or near limit.
    """
    if difficulty == 0:
        return "algorithmic"

    # Hierarchy preference by difficulty
    if difficulty >= 2:
        preferences = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash"]
    else:
        preferences = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-1.5-flash"]

    for m in preferences:
        if metrics_tracker.is_model_available(m):
            return m

    # If all preview/flash models are rate-limited, fallback to high-throughput 1.5-flash
    metrics_tracker.record_switch()
    return "gemini-1.5-flash"

# ==========================================
# 3. Execution with Automatic Retry & Failover
# ==========================================
def query_model_with_failover(prompt: str, system_prompt: str = None, context_type: str = "general") -> tuple[str, str]:
    """
    Executes prompt using dynamic model router.
    Returns (response_text, model_used).
    """
    difficulty, reason = rate_request_difficulty(prompt, context_type=context_type)
    metrics_tracker.record_difficulty(difficulty)

    if difficulty == 0:
        return None, "algorithmic"

    chosen_model = select_model_for_request(difficulty)
    candidate_models = [chosen_model]
    for m in ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-1.5-flash"]:
        if m not in candidate_models:
            candidate_models.append(m)

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 2048
        }
    }
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    for model_name in candidate_models:
        model_cfg = MODELS.get(model_name)
        if not model_cfg or not GEMINI_API_KEY:
            continue

        metrics_tracker.record_request_start(model_name)
        try:
            req = urllib.request.Request(model_cfg["url"], data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=18) as resp:
                data = json.loads(resp.read().decode())
                metrics_tracker.record_result(model_name, 200)
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip(), model_name
        except urllib.error.HTTPError as e:
            metrics_tracker.record_result(model_name, e.code)
            print(f"[WARN] ModelRouter: {model_name} returned HTTP {e.code}, failing over...")
            metrics_tracker.record_switch()
            if e.code == 429:
                time.sleep(1.0) # brief backoff before trying next model
                continue
        except Exception as e:
            metrics_tracker.record_result(model_name, 500)
            print(f"[WARN] ModelRouter error on {model_name}: {e}")
            metrics_tracker.record_switch()
            continue

    return None, "fallback_exhausted"

# ==========================================
# 4. Prometheus Metrics HTTP Exporter
# ==========================================
class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ["/metrics", "/metrics/"]:
            content = metrics_tracker.generate_prometheus_metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass # Suppress noisy server logs

def start_metrics_server(port: int = 8000):
    """
    Runs Prometheus metrics HTTP server in background daemon thread.
    """
    def run_server():
        try:
            server = HTTPServer(("0.0.0.0", port), MetricsHandler)
            print(f"[METRICS] Model Router Prometheus metrics server listening on port {port}/metrics")
            server.serve_forever()
        except Exception as e:
            print(f"[WARN] Metrics server could not bind to port {port}: {e}")

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
