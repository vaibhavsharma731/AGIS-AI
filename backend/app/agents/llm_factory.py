"""
backend/app/agents/llm_factory.py

One function that hands you the right AI model (LLM) to use.

Priority order:
  1. Whatever provider the caller asks for  (e.g. "groq", "nvidia")
  2. Google Gemini as a reliable fallback    (if the requested one fails)
  3. NVIDIA as the last-resort fallback      (if Gemini key is also missing)

Key fix: We wrap each model with a validator so that an EMPTY response
(no text, no tool calls) is treated as an error and triggers the next fallback,
rather than propagating the "model output must contain either output text or
tool calls" crash upstream.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage
from backend.app.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE VALIDATOR
# Raises ValueError on empty responses so .with_fallbacks() kicks in.
# ─────────────────────────────────────────────────────────────────────────────

def _validate_non_empty(message: AIMessage) -> AIMessage:
    """
    Checks that the LLM returned something useful.
    An empty response (no text content, no tool calls) causes the fallback chain
    to try the next provider instead of crashing with a cryptic error.
    """
    content = message.content
    if isinstance(content, str):
        has_text = bool(content.strip())
    elif isinstance(content, list):
        text_parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        has_text = bool("".join(text_parts).strip())
    else:
        has_text = bool(content)
    has_tools = bool(getattr(message, "tool_calls", None))

    if not has_text and not has_tools:
        raise ValueError(
            "LLM returned an empty response (no text, no tool calls). "
            "Triggering fallback to next provider."
        )
    return message


def _make_validated(llm):
    """Wraps an LLM so empty responses raise ValueError → triggers fallback."""
    return llm | RunnableLambda(_validate_non_empty)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def get_llm(provider: str = None, temperature: float = 0.1):
    """
    Returns a resilient LLM object equipped with automatic multi-provider fallbacks.

    If the primary provider hits high demand (503), rate limits (429), downtime,
    OR returns an empty response, it automatically falls back to the next provider.

    Fallback order (when preferred provider is 'groq'):
      Groq → NVIDIA → Google Gemini

    Each model is wrapped with a validator so empty responses also trigger fallback.
    """
    preferred = (provider or settings.LLM_PROVIDER).lower()

    candidates = []

    # ── Candidate: Groq ───────────────────────────────────────────────────────
    if settings.GROQ_API_KEY:
        try:
            raw_llm = ChatOpenAI(
                model=settings.GROQ_MODEL,
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                temperature=temperature,
            )
            candidates.append(("groq", _make_validated(raw_llm)))
        except Exception:
            pass

    # ── Candidate: NVIDIA NIM ─────────────────────────────────────────────────
    if settings.NVIDIA_API_KEY:
        try:
            raw_llm = ChatOpenAI(
                model=settings.NVIDIA_MODEL,
                api_key=settings.NVIDIA_API_KEY,
                base_url="https://integrate.api.nvidia.com/v1",
                temperature=temperature,
            )
            candidates.append(("nvidia", _make_validated(raw_llm)))
        except Exception:
            pass

    # ── Candidate: Google Gemini ──────────────────────────────────────────────
    if settings.GOOGLE_API_KEY:
        try:
            raw_llm = ChatGoogleGenerativeAI(
                model=settings.GOOGLE_MODEL,
                google_api_key=settings.GOOGLE_API_KEY,
                temperature=temperature,
                max_retries=1,
            )
            candidates.append(("google", _make_validated(raw_llm)))
        except Exception:
            pass

    if not candidates:
        # No configured keys found — return a bare model that will surface the
        # missing-key error clearly to the developer.
        return ChatOpenAI(
            model=settings.NVIDIA_MODEL,
            api_key=settings.NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=temperature,
        )

    # Sort so preferred provider is first, followed by remaining fallbacks
    ordered = [model for name, model in candidates if name == preferred]
    ordered += [model for name, model in candidates if name != preferred]

    primary = ordered[0]
    fallbacks = ordered[1:]

    if fallbacks:
        return primary.with_fallbacks(fallbacks, exceptions_to_handle=(Exception,))
    return primary
