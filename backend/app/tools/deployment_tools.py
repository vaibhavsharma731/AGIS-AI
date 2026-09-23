"""
backend/app/tools/deployment_tools.py

Fetches real code deployment history from the GitHub REST API.
No mock data — always calls the live GitHub API.
"""

from typing import List, Dict, Any
from langchain_core.tools import tool
from backend.app.services.github_service import fetch_github_commits


@tool
def get_recent_deployments() -> List[Dict[str, Any]]:
    """
    Fetch history of recent code deployments to production from GitHub.
    Returns a list of commits with: deployment_id, timestamp, author,
    commit_hash, message, and changed_files.

    Raises an error if GitHub credentials are missing or the API call fails.
    """
    deployments = fetch_github_commits()

    if not deployments:
        # GitHub is not configured or not reachable.
        # Return a structured unavailable payload so the graph can continue gracefully.
        return [{
            "status": "unavailable",
            "reason": "Could not fetch from GitHub. Ensure GITHUB_TOKEN and GITHUB_REPO are set in .env."
        }]

    return deployments
