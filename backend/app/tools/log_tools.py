"""
backend/app/tools/log_tools.py

Fetches real application error logs from AWS CloudWatch Logs.
No mock data — always calls the live AWS API.
"""

from typing import List
from langchain_core.tools import tool
from backend.app.services.aws_service import fetch_cloudwatch_logs


@tool
def get_recent_error_logs(keyword_filter: str = "") -> List[str]:
    """
    Search recent application logs for ERROR, CRITICAL, or WARNING lines.

    Parameters
    ----------
    keyword_filter : Optional keyword to narrow results (e.g. 'database', 'timeout', 'memory').
                     If empty, fetches all ERROR-level log events.

    Returns a list of matching log lines, or raises an error if AWS is not reachable.
    """
    # Use the keyword as the CloudWatch filter pattern, or default to "ERROR"
    filter_pattern = keyword_filter if keyword_filter else "ERROR"

    logs = fetch_cloudwatch_logs(filter_pattern=filter_pattern)

    if logs is None:
        # Query itself failed / AWS unreachable
        return [{
            "status": "unavailable",
            "reason": "Could not reach AWS CloudWatch Logs. Ensure CLOUDWATCH_LOG_GROUP is set in .env."
        }]

    if not logs:
        # Query succeeded, genuinely zero matching log events — this is a healthy signal
        return [{
            "status": "available",
            "reason": "No matching log events found in CloudWatch for the given filter pattern."
        }]

    return logs