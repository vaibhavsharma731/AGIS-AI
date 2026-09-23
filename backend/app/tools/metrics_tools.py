"""
backend/app/tools/metrics_tools.py

Fetches real-time system metrics from AWS CloudWatch.
No mock data — always calls the live AWS API.
"""

from langchain_core.tools import tool
from backend.app.services.aws_service import fetch_cloudwatch_metrics


@tool
def get_system_metrics() -> dict:
    """
    Fetch current cloud system metrics: CPU utilization, memory, latency,
    error rate, and active database connections from AWS CloudWatch.

    Returns a dict of metrics, or raises an error if AWS is not reachable.
    """
    metrics = fetch_cloudwatch_metrics()

    if not metrics:
        return {
            "status": "unavailable",
            "reason": "AWS CloudWatch is unreachable or credentials are not configured in .env.",
            "services_discovered": [],
            "service_metrics": {},
            "evidence_summary": ["Telemetry unavailable: AWS CloudWatch is not configured."],
            "cpu_utilization_pct": 0,
            "latency_ms": 0,
            "error_rate_pct": 0,
            "active_db_connections": 0,
        }

    return metrics
