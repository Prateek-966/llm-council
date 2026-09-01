"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Convenience aliases so you can write "deepseek" instead of the full slug.
# Any OpenRouter model id works too, alias or not - see https://openrouter.ai/models
# Slugs current as of August 2026; labs retire them fast, so re-check if a member goes quiet.
MODEL_ALIASES = {
    # Frontier / closed
    "gpt": "openai/gpt-5.6-sol",
    "claude": "anthropic/claude-opus-5",
    "claude-sonnet": "anthropic/claude-sonnet-5",
    "gemini": "google/gemini-3.7-flash",
    "gemini-pro": "google/gemini-3.1-pro-preview",
    "grok": "x-ai/grok-4.6",
    # Open weights
    "deepseek": "deepseek/deepseek-v4-flash-0731",
    "deepseek-pro": "deepseek/deepseek-v4-pro-0813",
    "qwen": "qwen/qwen3.7-max",
    "kimi": "moonshotai/kimi-k3",
}


def _resolve(name: str) -> str:
    """Map an alias to its OpenRouter model id, passing through unknown names."""
    return MODEL_ALIASES.get(name.strip().lower(), name.strip())


def _from_env(var: str, default):
    """Read a comma-separated model list from the environment."""
    raw = os.getenv(var)
    if not raw:
        return default
    return [_resolve(part) for part in raw.split(",") if part.strip()]


# Council members - list of OpenRouter model identifiers.
# Override without editing this file:  COUNCIL_MODELS=gpt,claude,deepseek,qwen,kimi
COUNCIL_MODELS = _from_env("COUNCIL_MODELS", [
    "openai/gpt-5.6-sol",
    "anthropic/claude-opus-5",
    "google/gemini-3.7-flash",
    "x-ai/grok-4.6",
    "deepseek/deepseek-v4-flash-0731",
    "qwen/qwen3.7-max",
    "moonshotai/kimi-k3",
])

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = _resolve(os.getenv("CHAIRMAN_MODEL", "anthropic/claude-opus-5"))

# Small, cheap model used only to name conversations
TITLE_MODEL = _resolve(os.getenv("TITLE_MODEL", "google/gemini-3.7-flash"))

# Chat-completions endpoint. Any OpenAI-compatible server works here, so pointing this at a
# local runtime (Ollama: http://localhost:11434/v1/chat/completions) runs the whole council
# offline for free. The API key is unused by most local servers - leave it blank.
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
)

# Conversation memory: how many prior messages (user + assistant, so 6 is three
# exchanges) are replayed to the models. Every prior turn is re-sent on every
# request of every stage, so this multiplies cost - 0 disables memory entirely.
HISTORY_MESSAGES = int(os.getenv("HISTORY_MESSAGES", "6"))

# Data directory for conversation storage (JSON backend)
DATA_DIR = "data/conversations"

# Supabase storage. Set both to persist conversations in Postgres instead of local
# JSON files - required on hosts with an ephemeral disk, such as Render's free tier.
# SUPABASE_KEY must be the service-role key: the table has RLS enabled with no
# policies, so it is unreadable with the anon key. Backend-only, never exposed.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
