"""OpenRouter API client for making LLM requests."""

import asyncio
import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


# Maps an HTTP status to a short kind plus a hint the UI can show the operator.
# The kinds are stable strings the frontend groups on; the hints name the exact
# setting to fix, since every one of these is a configuration problem.
_STATUS_HINTS = {
    400: ("bad_request", "The provider rejected the request as malformed."),
    401: ("auth", "OpenRouter rejected the API key. Check OPENROUTER_API_KEY."),
    402: ("credit", "Out of credit, or this key's spend limit is reached. Top up or raise the key limit."),
    403: ("forbidden", "This key is not allowed to use this model."),
    404: ("model_not_found", "No such model. The id may be misspelled or the model retired - check openrouter.ai/models."),
    408: ("timeout", "The provider timed out."),
    429: ("rate_limit", "Rate limited. Free models allow 20 requests/minute and 1000/day."),
    500: ("provider_error", "The provider failed on its side. Retrying often works."),
    502: ("provider_error", "The provider was unreachable. Retrying often works."),
    503: ("provider_error", "The provider is overloaded. Retrying often works."),
}


def _error(model: str, kind: str, message: str, hint: str, status: Optional[int] = None) -> Dict[str, Any]:
    """Build the error envelope that flows through to the UI."""
    return {
        "error": {
            "model": model,
            "kind": kind,
            "status": status,
            "message": message,
            "hint": hint,
        }
    }


def _from_status(model: str, status: int, body: str) -> Dict[str, Any]:
    """Turn an HTTP failure into an error envelope."""
    kind, hint = _STATUS_HINTS.get(status, ("http_error", "The provider returned an unexpected status."))
    return _error(model, kind, _provider_message(body) or f"HTTP {status}", hint, status)


def _provider_message(body: str) -> str:
    """Pull the human-readable message out of an OpenRouter error body."""
    import json

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return (body or "").strip()[:300]

    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("message", "")).strip()[:300]
    if isinstance(error, str):
        return error.strip()[:300]
    return ""


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Dict[str, Any]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        On success, a dict with 'content' and optional 'reasoning_details'.
        On failure, a dict with an 'error' key describing what went wrong, so the
        caller can report which member dropped out and why instead of silently
        continuing with a smaller council.
    """
    headers = {"Content-Type": "application/json"}

    # Local OpenAI-compatible servers (Ollama, LM Studio) take no key, and httpx rejects
    # a bare "Bearer " header, so only send it when a key is actually configured.
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )

            if response.status_code >= 400:
                print(f"Error querying model {model}: HTTP {response.status_code} {response.text[:200]}")
                return _from_status(model, response.status_code, response.text)

            data = response.json()

            # OpenRouter can report a provider failure in a 200 body.
            if isinstance(data.get("error"), (dict, str)):
                message = _provider_message(response.text) or "The provider reported an error."
                print(f"Error querying model {model}: {message}")
                return _error(model, "provider_error", message,
                              "The provider accepted the request then failed. Retrying often works.")

            choices = data.get("choices") or []
            if not choices:
                print(f"Error querying model {model}: empty response")
                return _error(model, "empty_response", "The provider returned no choices.",
                              "The model replied with nothing. Retrying often works.")

            message = choices[0].get("message", {})

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except httpx.TimeoutException:
        print(f"Error querying model {model}: timed out after {timeout}s")
        return _error(model, "timeout", f"No response within {timeout:.0f}s.",
                      "The model took too long. Reasoning models on a busy provider can exceed the timeout.")
    except httpx.RequestError as e:
        print(f"Error querying model {model}: {e}")
        return _error(model, "network", str(e)[:300],
                      "Could not reach the provider. Check OPENROUTER_API_URL and the server's network access.")
    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return _error(model, "unknown", str(e)[:300], "Unexpected failure while querying this model.")


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Dict[str, Any]]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to its response dict, which carries either
        'content' or 'error'.
    """
    # Create tasks for all models
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return {model: response for model, response in zip(models, responses)}
