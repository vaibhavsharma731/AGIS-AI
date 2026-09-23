"""
backend/app/services/github_service.py

Service for retrieving real git commit history, PRs, and deployment actions from the GitHub REST API.
"""

import json
import logging
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

from backend.app.config import settings

logger = logging.getLogger(__name__)

def _normalize_repo(repo_str: str) -> str:
    if not repo_str:
        return ""
    repo = repo_str.strip().rstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    for prefix in ["https://github.com/", "http://github.com/", "github.com/"]:
        if repo.startswith(prefix):
            repo = repo[len(prefix):]
    return repo.strip("/")

def test_github_connection(repo: str = "", token: str = "") -> Dict[str, Any]:
    """Tests connectivity to GitHub API for the specified repository and token."""
    target_repo = _normalize_repo(repo or settings.GITHUB_REPO)
    auth_token = token or settings.GITHUB_TOKEN

    if not target_repo:
        return {"success": False, "message": "GitHub repository (owner/repo) is required."}

    url = f"https://api.github.com/repos/{target_repo}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AegisAI-Incident-Responder/1.0"
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "success": True,
                    "repo": data.get("full_name"),
                    "private": data.get("private", False),
                    "default_branch": data.get("default_branch", "main"),
                    "stars": data.get("stargazers_count", 0),
                    "message": f"Successfully connected to GitHub repo '{data.get('full_name')}'"
                }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"success": False, "message": f"Repository '{target_repo}' not found. If it is private, ensure GITHUB_TOKEN has repo access."}
        elif e.code == 401:
            return {"success": False, "message": "Unauthorized: Invalid GITHUB_TOKEN."}
        else:
            return {"success": False, "message": f"GitHub API error {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to connect to GitHub: {str(e)}"}

def fetch_github_commits(repo: str = "", token: str = "", limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches recent commits from the GitHub REST API for a given repository (e.g., "owner/repo").
    Returns formatted list of deployment/commit dictionaries, or None if credentials/repo are missing or request fails.
    """
    target_repo = _normalize_repo(repo or settings.GITHUB_REPO)
    auth_token = token or settings.GITHUB_TOKEN

    if not target_repo:
        logger.warning("[GitHub Service] GITHUB_REPO is not configured.")
        return None

    url = f"https://api.github.com/repos/{target_repo}/commits?per_page={limit}"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "AegisAI-Incident-Responder/1.0"
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                raw_commits = json.loads(response.read().decode("utf-8"))
                deployments = []
                for idx, item in enumerate(raw_commits):
                    commit_data = item.get("commit", {})
                    author_info = commit_data.get("author", {})
                    sha = item.get("sha", "")[:7]
                    
                    # Optional: Fetch detailed changed files for the latest commit
                    changed_files = []
                    if idx == 0 and sha:
                        changed_files = _fetch_commit_changed_files(target_repo, item.get("sha", ""), headers)

                    deployments.append({
                        "deployment_id": f"DEP-GH-{sha.upper()}",
                        "timestamp": author_info.get("date", ""),
                        "author": author_info.get("name", "GitHub User"),
                        "commit_hash": sha,
                        "message": commit_data.get("message", "").split("\n")[0],
                        "changed_files": changed_files
                    })
                logger.info(f"[GitHub Service] Successfully fetched {len(deployments)} commits from {target_repo}.")
                return deployments
    except urllib.error.HTTPError as e:
        logger.error(f"[GitHub Service] HTTP Error fetching commits from {target_repo}: {e.code} {e.reason}")
    except Exception as e:
        logger.error(f"[GitHub Service] Failed to connect to GitHub API: {e}")

    return None

def _fetch_commit_changed_files(repo: str, commit_sha: str, headers: dict) -> List[str]:
    """Helper to fetch filenames modified in a specific commit."""
    try:
        url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                detail = json.loads(response.read().decode("utf-8"))
                files = detail.get("files", [])
                return [f.get("filename", "") for f in files if f.get("filename")]
    except Exception:
        pass
    return []

def trigger_github_workflow(workflow_filename: str = "deploy.yml", ref: str = "main") -> bool:
    """
    Triggers a GitHub Workflow dispatch event to trigger a automated rollback or deploy.
    """
    target_repo = settings.GITHUB_REPO
    auth_token = settings.GITHUB_TOKEN

    if not target_repo or not auth_token:
        logger.warning("[GitHub Service] GITHUB_REPO or GITHUB_TOKEN missing for workflow dispatch.")
        return False

    url = f"https://api.github.com/repos/{target_repo}/actions/workflows/{workflow_filename}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {auth_token}",
        "User-Agent": "AegisAI-Incident-Responder/1.0"
    }
    payload = json.dumps({"ref": ref}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in [204, 201, 200]:
                logger.info(f"[GitHub Service] Workflow '{workflow_filename}' dispatched successfully.")
                return True
    except Exception as e:
        logger.error(f"[GitHub Service] Failed to dispatch workflow '{workflow_filename}': {e}")
    return False
