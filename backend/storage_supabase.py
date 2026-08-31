"""Supabase (Postgres) storage backend.

Conversations live in one table, keyed by the same uuid the JSON backend uses as a
filename. Reached over PostgREST with httpx, which is already a dependency, so no
Postgres driver is needed.

Requires a service-role key: the table has RLS on with no policies, so the anon key
sees nothing. Keep the key server-side - it is never sent to the browser.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import httpx

from .config import SUPABASE_URL, SUPABASE_KEY

TABLE = "conversations"
TIMEOUT = 15.0


def _endpoint() -> str:
    return f"{SUPABASE_URL.rstrip('/')}/rest/v1/{TABLE}"


def _headers(**extra: str) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    headers.update(extra)
    return headers


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """Insert a new empty conversation and return it."""
    conversation = {
        "id": conversation_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "New Conversation",
        "messages": [],
    }

    response = httpx.post(
        _endpoint(),
        headers=_headers(Prefer="return=representation"),
        json=conversation,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    rows = response.json()
    return rows[0] if rows else conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load one conversation, or None if it does not exist."""
    response = httpx.get(
        _endpoint(),
        headers=_headers(),
        params={
            "id": f"eq.{conversation_id}",
            "select": "id,created_at,title,messages",
            "limit": "1",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    rows = response.json()
    return rows[0] if rows else None


def save_conversation(conversation: Dict[str, Any]):
    """Upsert a conversation."""
    response = httpx.post(
        _endpoint(),
        headers=_headers(Prefer="resolution=merge-duplicates,return=minimal"),
        json={
            "id": conversation["id"],
            "created_at": conversation["created_at"],
            "title": conversation.get("title", "New Conversation"),
            "messages": conversation.get("messages", []),
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()


def list_conversations() -> List[Dict[str, Any]]:
    """List conversation metadata, newest first.

    message_count is a generated column, so the message bodies stay in the database
    instead of being shipped over the wire just to be counted.
    """
    response = httpx.get(
        _endpoint(),
        headers=_headers(),
        params={
            "select": "id,created_at,title,message_count",
            "order": "created_at.desc",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    return response.json()
