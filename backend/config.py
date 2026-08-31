"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Convenience aliases so you can write "deepseek" instead of the full slug.
# Any OpenRouter model id works too, alias or not - see https://openrouter.ai/models
MODEL_ALIASES = {
    # Frontier / closed
    "gpt": "openai/gpt-5.1",
    "gemini": "google/gemini-3-pro-preview",
    "claude": "anthropic/claude-sonnet-4.5",
    "grok": "x-ai/grok-4",
    # Open weights (Chinese labs)
    "deepseek": "deepseek/deepseek-v4-pro",
    "deepseek-flash": "deepseek/deepseek-v4-flash",
    "qwen": "qwen/qwen3.7-max",
    "kimi": "moonshotai/kimi-k3",
    "glm": "z-ai/glm-4.6",
    "minimax": "minimax/minimax-m2",
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
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
    "deepseek/deepseek-v4-pro",
    "qwen/qwen3.7-max",
    "moonshotai/kimi-k3",
])

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = _resolve(os.getenv("CHAIRMAN_MODEL", "google/gemini-3-pro-preview"))

# Small, cheap model used only to name conversations
TITLE_MODEL = _resolve(os.getenv("TITLE_MODEL", "google/gemini-2.5-flash"))

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
