"""Conversation storage.

Two interchangeable backends behind one API: JSON files on local disk (the default,
and what upstream does), or Supabase when SUPABASE_URL and SUPABASE_KEY are set.
Hosts with an ephemeral filesystem - Render's free tier among them - lose JSON files
on every restart, which is what the Supabase backend is for.
"""

from typing import List, Dict, Any, Optional

from .config import SUPABASE_URL, SUPABASE_KEY

if SUPABASE_URL and SUPABASE_KEY:
    from . import storage_supabase as _backend
else:
    from . import storage_json as _backend

BACKEND_NAME = "supabase" if (SUPABASE_URL and SUPABASE_KEY) else "json"

# Primitives, whichever backend is active.
create_conversation = _backend.create_conversation
get_conversation = _backend.get_conversation
save_conversation = _backend.save_conversation
list_conversations = _backend.list_conversations


def _load(conversation_id: str) -> Dict[str, Any]:
    """Fetch a conversation or raise if it is missing."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    return conversation


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = _load(conversation_id)

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
    """
    conversation = _load(conversation_id)

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = _load(conversation_id)
    conversation["title"] = title
    save_conversation(conversation)
