"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, TITLE_MODEL, HISTORY_MESSAGES


def build_history(messages: List[Dict[str, Any]], limit: int = None) -> List[Dict[str, str]]:
    """
    Turn stored conversation messages into chat turns the models can be given.

    The assistant's turn is the chairman's synthesis - that is the answer the user
    actually saw, so it is what the conversation should continue from. Stage 1 and
    Stage 2 material is deliberately left out: replaying every member's draft and
    every peer review would balloon the prompt without adding much the synthesis
    does not already carry.
    """
    if limit is None:
        limit = HISTORY_MESSAGES
    if limit <= 0:
        return []

    history = []
    for message in messages:
        if message.get("role") == "user":
            history.append({"role": "user", "content": message.get("content", "")})
        elif message.get("role") == "assistant":
            answer = (message.get("stage3") or {}).get("response", "")
            if answer:
                history.append({"role": "assistant", "content": answer})

    # Keep the most recent turns, and never lead with an assistant turn.
    history = history[-limit:]
    while history and history[0]["role"] == "assistant":
        history.pop(0)
    return history


def _describe_history(history: List[Dict[str, str]]) -> str:
    """Render prior turns for the prompts that are a single instruction block."""
    if not history:
        return ""
    lines = []
    for turn in history:
        who = "User" if turn["role"] == "user" else "Council"
        lines.append(f"{who}: {turn['content']}")
    return (
        "Earlier in this conversation:\n\n" + "\n\n".join(lines) + "\n\n---\n\n"
    )


async def stage1_collect_responses(
    user_query: str,
    history: List[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (results, errors). Results are dicts with 'model' and 'response';
        errors describe the members that failed, so the UI can say which seat is
        empty and why rather than just showing a shorter tab strip.
    """
    # Prior turns first, so a follow-up question resolves against what was said.
    messages = (history or []) + [{"role": "user", "content": user_query}]

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    errors = []
    for model, response in responses.items():
        if "error" in response:
            errors.append({**response["error"], "stage": "stage1"})
            continue
        stage1_results.append({
            "model": model,
            "response": response.get('content', '')
        })

    return stage1_results, errors


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    history: List[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping, errors)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

{_describe_history(history)}Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    errors = []
    for model, response in responses.items():
        if "error" in response:
            errors.append({**response["error"], "stage": "stage2"})
            continue
        full_text = response.get('content', '')
        parsed = parse_ranking_from_text(full_text)
        stage2_results.append({
            "model": model,
            "ranking": full_text,
            "parsed_ranking": parsed
        })

    return stage2_results, label_to_model, errors


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    history: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

{_describe_history(history)}Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if "error" in response:
        # The chairman writes the answer the user actually reads, so its failure is
        # reported in place of the synthesis rather than hidden behind a generic line.
        error = {**response["error"], "stage": "stage3"}
        return {
            "model": CHAIRMAN_MODEL,
            "response": "",
            "error": error
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use a small, cheap model for title generation (see TITLE_MODEL in config)
    response = await query_model(TITLE_MODEL, messages, timeout=30.0)

    if "error" in response:
        # A failed title is cosmetic - the council round is unaffected.
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str,
    history: List[Dict[str, str]] = None,
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 1: Collect individual responses
    stage1_results, stage1_errors = await stage1_collect_responses(user_query, history)

    # If no models responded successfully, hand back why each one failed
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "",
            "error": {
                "model": "council",
                "kind": "all_failed",
                "status": None,
                "message": "Every council member failed to respond.",
                "hint": "No member answered - the errors below say why.",
                "stage": "stage1",
            },
        }, {"errors": stage1_errors}

    # Stage 2: Collect rankings
    stage2_results, label_to_model, stage2_errors = await stage2_collect_rankings(
        user_query, stage1_results, history
    )

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        history,
    )

    errors = stage1_errors + stage2_errors
    if "error" in stage3_result:
        errors.append(stage3_result["error"])

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "errors": errors,
        "council_size": len(COUNCIL_MODELS),
        "history_turns": len(history or []),
    }

    return stage1_results, stage2_results, stage3_result, metadata
