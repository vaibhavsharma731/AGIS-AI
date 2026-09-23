"""
backend/app/config.py

Loads all settings from the .env file (or environment variables).
Think of this as the central control panel for the whole application.
"""

import os
from dotenv import load_dotenv

# Step 1: Read the .env file so all os.getenv() calls below can find the values
load_dotenv()


class Settings:
    """
    One place to read every setting the app needs.
    Values come from the .env file. If a value is missing, the default (second argument) is used.
    """

    # ── Which AI provider to use by default ───────────────────────────────────
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "nvidia").lower()

    # ── API Keys for each AI provider ─────────────────────────────────────────
    NVIDIA_API_KEY: str  = os.getenv("NVIDIA_API_KEY", "")
    GOOGLE_API_KEY: str  = os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY:   str  = os.getenv("GROQ_API_KEY",   "")

    # ── Which specific model to use per provider ───────────────────────────────
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL_NAME", "deepseek-ai/deepseek-v4.1-flash")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL_NAME", "gemini-3.6-flash")
    GROQ_MODEL:   str = os.getenv("GROQ_MODEL_NAME",   "openai/gpt-oss-120b")

    # ── RAG / Knowledge Base paths ─────────────────────────────────────────────
    # Resolves to: <project-root>/backend/knowledge/
    KNOWLEDGE_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "knowledge")
    )
    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "backend/knowledge/faiss_index")

    # ── GitHub integration ─────────────────────────────────────────────────────
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO:  str = os.getenv("GITHUB_REPO",  "")   # Format: "owner/repo-name"

    # ── AWS / CloudWatch integration ───────────────────────────────────────────
    AWS_ACCESS_KEY_ID:     str = os.getenv("AWS_ACCESS_KEY_ID",     "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION:            str = os.getenv("AWS_REGION",            "us-east-1")
    CLOUDWATCH_LOG_GROUP:  str = os.getenv("CLOUDWATCH_LOG_GROUP",  "/aws/apps/aegis-ai")
    CLOUDWATCH_LOG_STREAM: str = os.getenv("CLOUDWATCH_LOG_STREAM", "")

    # ── Docker / local execution ───────────────────────────────────────────────
    DOCKER_CONTAINER_NAME: str = os.getenv("DOCKER_CONTAINER_NAME", "payment-backend-worker")

    # ── FastAPI server binding ─────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


    def update_integrations(
        self,
        aws_key:      str = None,
        aws_secret:   str = None,
        aws_region:   str = None,
        cw_group:     str = None,
        github_token: str = None,
        github_repo:  str = None,
    ):
        """
        Updates integration credentials at runtime AND saves them to the .env file
        so they persist the next time the app restarts.

        Only the values you pass in will be changed; the rest are left alone.
        """

        # Step 1: Collect every value the caller wants to change into a dict
        #         so we can process them all in one place.
        changes = {}

        if aws_key is not None:
            self.AWS_ACCESS_KEY_ID = aws_key.strip()
            changes["AWS_ACCESS_KEY_ID"] = self.AWS_ACCESS_KEY_ID

        if aws_secret is not None:
            self.AWS_SECRET_ACCESS_KEY = aws_secret.strip()
            changes["AWS_SECRET_ACCESS_KEY"] = self.AWS_SECRET_ACCESS_KEY

        if aws_region is not None:
            self.AWS_REGION = aws_region.strip()
            changes["AWS_REGION"] = self.AWS_REGION

        if cw_group is not None:
            self.CLOUDWATCH_LOG_GROUP = cw_group.strip()
            changes["CLOUDWATCH_LOG_GROUP"] = self.CLOUDWATCH_LOG_GROUP

        if github_token is not None:
            self.GITHUB_TOKEN = github_token.strip()
            changes["GITHUB_TOKEN"] = self.GITHUB_TOKEN

        if github_repo is not None:
            self.GITHUB_REPO = github_repo.strip()
            changes["GITHUB_REPO"] = self.GITHUB_REPO

        # Step 2: Write the changes back to the .env file on disk
        env_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        )

        try:
            updated_lines = []          # All lines we will write back to .env
            already_updated = set()     # Track which keys we've already handled

            # ── Pass 1: Walk through the existing .env file line by line ──────
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()

                        # Check if this line is a real KEY=VALUE line (not a comment or blank)
                        is_key_value = "=" in stripped and not stripped.startswith("#")

                        if is_key_value:
                            # Extract just the key (the part before the first "=")
                            key = stripped.split("=", 1)[0].strip()

                            if key in changes:
                                # This key needs to be updated → write the new value
                                updated_lines.append(f"{key}={changes[key]}\n")
                                already_updated.add(key)
                                continue  # Skip the old line

                        # Not a key we changed → keep the line exactly as it was
                        updated_lines.append(line)

            # ── Pass 2: If any changed key didn't exist in the file yet, add it ──
            for key, value in changes.items():
                if key not in already_updated:
                    updated_lines.append(f"{key}={value}\n")

            # ── Step 3: Write everything back to disk ──────────────────────────
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

        except Exception as e:
            print(f"[Config] Could not save settings to .env file: {e}")


# Create a single global instance used everywhere in the app:
#   from backend.app.config import settings
settings = Settings()
