from __future__ import annotations

import json
import re
from typing import Any

from .llm_provider import get_llm_client
from .rag import policy_text, retrieve_policy, top_policy
from .utils import extract_duration_hours, normalize_text

CROSS_LINGUAL_POLICY_PROMPT = (
    "You are a civic policy analyst. The policy context is in Bangla and the user complaint can be in Bangla or English. "
    "Extract the specific service deadline in hours or days from the Bangla text. "
    "Compare it to the user's reported duration and decide if there is a violation. "
    "Return compact JSON with: policy_deadline_hours, user_duration_hours, is_violation, reasoning."
)


def extract_policy_deadline_hours_from_bangla(policy_text_block: str) -> int | None:
    """Extract deadline duration in hours from Bangla/English policy text."""
    text = normalize_text(policy_text_block)

    # Examples matched: "48 hours", "৪৮ ঘণ্টা", "2 days", "২ দিন"
    day_match = re.search(r"(\d+)\s*(days?|day|দিন)", text)
    if day_match:
        return int(day_match.group(1)) * 24

    hour_match = re.search(r"(\d+)\s*(hours?|hour|ঘণ্টা|ঘন্টা)", text)
    if hour_match:
        return int(hour_match.group(1))

    return None


def run_policy_reasoning(
    category: str,
    user_text: str,
    wait_text: str,
    web_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Retrieve policy chunks and produce cross-lingual policy reasoning output."""
    chunks = retrieve_policy(category, user_text)
    best_chunk = top_policy(chunks)
    combined_policy = policy_text(chunks)

    policy_deadline_hours = extract_policy_deadline_hours_from_bangla(
        best_chunk.text if best_chunk else combined_policy
    )
    user_duration_hours = extract_duration_hours(wait_text)

    is_violation = False
    if policy_deadline_hours is not None and user_duration_hours is not None:
        is_violation = user_duration_hours > policy_deadline_hours

    llm = get_llm_client()
    reasoning = (
        f"Prompt used: {CROSS_LINGUAL_POLICY_PROMPT}\n"
        f"Extracted policy deadline: {policy_deadline_hours if policy_deadline_hours is not None else 'unknown'} hours. "
        f"User-reported duration: {user_duration_hours if user_duration_hours is not None else 'unknown'} hours. "
        f"Violation: {'yes' if is_violation else 'no'}"
    )

    if llm.enabled:
        prompt = (
            f"{CROSS_LINGUAL_POLICY_PROMPT}\n\n"
            f"Category: {category}\n"
            f"User complaint: {user_text}\n"
            f"User-reported duration: {wait_text}\n"
            f"Retrieved policy text:\n{combined_policy}\n\n"
            f"Brave web context JSON:\n{json.dumps(web_context or [], ensure_ascii=False)}\n\n"
            "Return a compact JSON object with keys: policy_deadline_hours, user_duration_hours, is_violation, reasoning."
        )
        llm_result = llm.json_completion(
            [
                {"role": "system", "content": "You are a careful civic policy reasoning engine."},
                {"role": "user", "content": prompt},
            ],
            fallback={
                "policy_deadline_hours": policy_deadline_hours,
                "user_duration_hours": user_duration_hours,
                "is_violation": is_violation,
                "reasoning": reasoning,
            },
        )
        policy_deadline_hours = llm_result.get("policy_deadline_hours", policy_deadline_hours)
        user_duration_hours = llm_result.get("user_duration_hours", user_duration_hours)
        is_violation = bool(llm_result.get("is_violation", is_violation))
        reasoning = llm_result.get("reasoning", reasoning)

    return {
        "retrieved_policy": combined_policy,
        "policy_deadline_hours": policy_deadline_hours,
        "user_duration_hours": user_duration_hours,
        "is_violation": is_violation,
        "reasoning": reasoning,
        "web_context": web_context or [],
    }
