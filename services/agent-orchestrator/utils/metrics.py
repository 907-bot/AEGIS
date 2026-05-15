from prometheus_client import Counter, Histogram

# ─── Investigation Metrics ───────────────────────────────────────────────────
INVESTIGATIONS_TOTAL = Counter(
    "aegis_investigations_total", 
    "Total investigations", 
    ["type", "status"]
)

INVESTIGATION_DURATION = Histogram(
    "aegis_investigation_duration_seconds", 
    "Investigation duration"
)

AGENT_ERRORS = Counter(
    "aegis_agent_errors_total", 
    "Agent errors", 
    ["agent"]
)
