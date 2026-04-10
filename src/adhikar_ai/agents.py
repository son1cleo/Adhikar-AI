from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .contacts import find_contact, load_contacts
from .config import CONTACTS_FILE
from .database import insert_policy_violation
from .llm_provider import get_llm_client
from .search import enrich_complaint_context
from .supabase_client import supabase_store
from .rag_logic import run_policy_reasoning
from .utils import normalize_text


class CivicState(TypedDict, total=False):
    messages: list[dict[str, str]]
    issue_text: str
    location_text: str
    wait_text: str
    requester_name: str
    session_id: str
    user_id: str
    category: str
    location_data: dict[str, Any]
    web_context: list[dict[str, Any]]
    policy_deadline: int | None
    user_duration_hours: int | None
    is_violation: bool
    consistency_status: str
    severity_flag: str
    policy_vs_reality_gap_hours: int | None
    complaint_json: dict[str, Any]
    needs_user_input: bool
    missing_fields: list[str]
    assistant_reply: str
    email_subject: str
    email_draft: str


REQUIRED_LOCATION_TOKENS = [
    "ward",
    "ওয়ার্ড",
    "area",
    "neighborhood",
    "mirpur",
    "dhanmondi",
    "uttara",
    "mohammadpur",
    "banani",
    "gulshan",
]


def _contains_location(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return any(token in normalized for token in REQUIRED_LOCATION_TOKENS)


def _contains_duration(text: str) -> bool:
    normalized = normalize_text(text)
    duration_tokens = ["day", "days", "hour", "hours", "দিন", "ঘণ্টা", "ঘন্টা"]
    has_number = any(ch.isdigit() for ch in normalized)
    return has_number and any(token in normalized for token in duration_tokens)


def _classify_issue(issue_text: str) -> str:
    normalized = normalize_text(issue_text)
    mapping = {
        "Waste": ["garbage", "waste", "moyla", "আবর্জনা", "ময়লা", "trash"],
        "Road": ["road", "street", "pothole", "রাস্তা", "গর্ত", "footpath"],
        "Electrical": ["electric", "light", "বিদ্যুৎ", "power", "line"],
        "Water": ["water", "pani", "পানি", "drain", "sewer"],
    }
    for category, keywords in mapping.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "Waste"


def _classify_with_llm(issue_text: str) -> str:
    llm = get_llm_client()
    if not llm.enabled:
        return _classify_issue(issue_text)

    result = llm.json_completion(
        [
            {"role": "system", "content": "Classify Dhaka civic issues into Waste, Road, Electrical, or Water."},
            {
                "role": "user",
                "content": (
                    "Return JSON with key category only. "
                    f"Issue text: {issue_text}"
                ),
            },
        ],
        fallback={"category": _classify_issue(issue_text)},
    )
    category = result.get("category", _classify_issue(issue_text))
    return category if category in {"Waste", "Road", "Electrical", "Water"} else _classify_issue(issue_text)


def _validation_node(state: CivicState) -> CivicState:
    issue_text = state.get("issue_text", "")
    location_text = state.get("location_text", "")
    wait_text = state.get("wait_text", "")

    missing_fields: list[str] = []
    if not _contains_location(location_text):
        missing_fields.append("location")
    if not _contains_duration(wait_text):
        missing_fields.append("duration")

    messages = list(state.get("messages", []))
    if missing_fields:
        prompt_parts = []
        if "location" in missing_fields:
            prompt_parts.append("your neighborhood or ward")
        if "duration" in missing_fields:
            prompt_parts.append("how long the issue has persisted")
        ask_text = "Please provide " + " and ".join(prompt_parts) + " so I can continue."
        messages.append({"role": "assistant", "content": ask_text})

    return {
        **state,
        "issue_text": issue_text,
        "location_text": location_text,
        "wait_text": wait_text,
        "needs_user_input": bool(missing_fields),
        "missing_fields": missing_fields,
        "messages": messages,
    }


def _router_after_validation(state: CivicState) -> str:
    if state.get("needs_user_input"):
        return END
    return "classification"


def _classification_node(state: CivicState) -> CivicState:
    category = _classify_with_llm(state.get("issue_text", ""))
    return {**state, "category": category}


def _context_enrichment_node(state: CivicState) -> CivicState:
    location_text = state.get("location_text", "")
    category = state.get("category", "Waste")
    web_context = enrich_complaint_context(category, location_text)
    return {**state, "web_context": web_context}


def _rag_policy_search_node(state: CivicState) -> CivicState:
    reasoning = run_policy_reasoning(
        category=state.get("category", "Waste"),
        user_text=state.get("issue_text", ""),
        wait_text=state.get("wait_text", ""),
        web_context=state.get("web_context", []),
    )
    return {
        **state,
        "policy_deadline": reasoning.get("policy_deadline_hours"),
        "user_duration_hours": reasoning.get("user_duration_hours"),
        "is_violation": bool(reasoning.get("is_violation")),
        "retrieved_policy": reasoning.get("retrieved_policy", ""),
        "reasoning": reasoning.get("reasoning", ""),
        "web_context": reasoning.get("web_context", []),
    }


def _violation_analysis_node(state: CivicState) -> CivicState:
    location_text = state.get("location_text", "")
    contact = find_contact(location_text, load_contacts(CONTACTS_FILE))
    location_data = {
        "ward": contact.ward if contact else location_text,
        "neighborhood": contact.neighborhood if contact else location_text,
        "latitude": contact.latitude if contact else 0.0,
        "longitude": contact.longitude if contact else 0.0,
        "recipient_name": contact.councillor if contact else "Ward Councillor",
        "recipient_email": contact.email if contact else "",
        "recipient_phone": contact.phone if contact else "",
    }

    deadline = state.get("policy_deadline")
    waited = state.get("user_duration_hours")
    gap = None if deadline is None or waited is None else deadline - waited
    if deadline is None or waited is None:
        consistency_status = "unknown"
    elif waited > deadline:
        consistency_status = "inconsistent"
    else:
        consistency_status = "consistent"

    severity_flag = "low"
    if gap is not None and gap < 0:
        severity_flag = "critical" if abs(gap) >= 48 else "high"
    elif gap is not None and gap <= 24:
        severity_flag = "medium"

    return {
        **state,
        "location_data": location_data,
        "policy_vs_reality_gap_hours": gap,
        "consistency_status": consistency_status,
        "severity_flag": severity_flag,
    }


def _action_generator_node(state: CivicState) -> CivicState:
    deadline = state.get("policy_deadline")
    waited = state.get("user_duration_hours")
    is_violation = bool(state.get("is_violation"))
    location_data = state.get("location_data", {})

    comparison = "Policy comparison unavailable."
    if deadline is not None and waited is not None:
        comparison = (
            f"The issue has exceeded the policy deadline by {waited - deadline} hours."
            if waited > deadline
            else f"The issue is within policy deadline by {deadline - waited} hours."
        )

    complaint_json = {
        "requester_name": state.get("requester_name", "Citizen"),
        "session_id": state.get("session_id", ""),
        "user_id": state.get("user_id", ""),
        "issue_text": state.get("issue_text", ""),
        "category": state.get("category", "Waste"),
        "location": state.get("location_text", ""),
        "location_data": location_data,
        "policy_deadline_hours": deadline,
        "user_duration_hours": waited,
        "policy_vs_reality_gap_hours": state.get("policy_vs_reality_gap_hours"),
        "is_violation": is_violation,
        "consistency_status": state.get("consistency_status", "unknown"),
        "severity_flag": state.get("severity_flag", "low"),
        "comparison": comparison,
        "retrieved_policy": state.get("retrieved_policy", ""),
        "web_context": state.get("web_context", []),
        "recommended_action": "File a formal complaint to ward authority and request immediate service action.",
    }

    llm = get_llm_client()
    assistant_reply = (
        f"Your issue has been classified as {complaint_json['category']}. {comparison} "
        f"Contact {location_data.get('recipient_name', 'Ward Councillor')} at {location_data.get('recipient_email', '')}."
    )
    email_subject = f"Civic complaint for {complaint_json['location']}"
    email_draft = (
        f"Dear {location_data.get('recipient_name', 'Authority')},\n\n"
        f"I am reporting a {complaint_json['category'].lower()} issue at {complaint_json['location']}.\n"
        f"{comparison}\n\n"
        f"Policy excerpt:\n{state.get('retrieved_policy', '')}\n\n"
        f"Please investigate and resolve the issue promptly.\n\n"
        f"Regards,\n{complaint_json['requester_name']}"
    )
    if llm.enabled:
        draft_result = llm.chat(
            [
                {"role": "system", "content": "Draft concise civic guidance and an email to authority."},
                {
                    "role": "user",
                    "content": (
                        f"Create a short citizen-facing reply and a complaint email draft.\n"
                        f"Complaint JSON: {complaint_json}"
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=900,
        )
        if draft_result.text:
            assistant_reply = draft_result.text

    next_state = {
        **state,
        "complaint_json": complaint_json,
        "assistant_reply": assistant_reply,
        "email_subject": email_subject,
        "email_draft": email_draft,
    }
    return _analytics_agent_node(next_state)


def _analytics_agent_node(state: CivicState) -> CivicState:
    complaint_json = state.get("complaint_json", {})
    if complaint_json:
        insert_policy_violation(
            {
                "category": complaint_json.get("category", "Unknown"),
                "location": complaint_json.get("location", ""),
                "ward": complaint_json.get("location_data", {}).get("ward"),
                "neighborhood": complaint_json.get("location_data", {}).get("neighborhood"),
                "area_code": complaint_json.get("location_data", {}).get("ward") or complaint_json.get("location_data", {}).get("neighborhood"),
                "consistency_status": complaint_json.get("consistency_status"),
                "severity_flag": complaint_json.get("severity_flag"),
                "policy_deadline_hours": complaint_json.get("policy_deadline_hours"),
                "user_duration_hours": complaint_json.get("user_duration_hours"),
                "policy_vs_reality_gap_hours": complaint_json.get("policy_vs_reality_gap_hours"),
                "is_violation": complaint_json.get("is_violation", False),
                "session_id": state.get("session_id"),
                "user_id": state.get("user_id"),
                "recipient_name": complaint_json.get("location_data", {}).get("recipient_name"),
                "recipient_email": complaint_json.get("location_data", {}).get("recipient_email"),
                "complaint_json": complaint_json,
            }
        )
        if supabase_store.enabled:
            supabase_store.insert_policy_violation(
                {
                    "category": complaint_json.get("category", "Unknown"),
                    "location": complaint_json.get("location", ""),
                    "ward": complaint_json.get("location_data", {}).get("ward"),
                    "neighborhood": complaint_json.get("location_data", {}).get("neighborhood"),
                    "area_code": complaint_json.get("location_data", {}).get("ward") or complaint_json.get("location_data", {}).get("neighborhood"),
                    "consistency_status": complaint_json.get("consistency_status"),
                    "severity_flag": complaint_json.get("severity_flag"),
                    "policy_deadline_hours": complaint_json.get("policy_deadline_hours"),
                    "user_duration_hours": complaint_json.get("user_duration_hours"),
                    "policy_vs_reality_gap_hours": complaint_json.get("policy_vs_reality_gap_hours"),
                    "is_violation": complaint_json.get("is_violation", False),
                    "session_id": state.get("session_id"),
                    "user_id": state.get("user_id"),
                    "complaint_json": complaint_json,
                }
            )
    return state


def build_civic_graph():
    graph = StateGraph(CivicState)

    graph.add_node("Validation", _validation_node)
    graph.add_node("Classification", _classification_node)
    graph.add_node("Context_Enrichment", _context_enrichment_node)
    graph.add_node("RAG_Policy_Search", _rag_policy_search_node)
    graph.add_node("Violation_Analysis", _violation_analysis_node)
    graph.add_node("Action_Generator", _action_generator_node)

    graph.add_edge(START, "Validation")
    graph.add_conditional_edges(
        "Validation",
        _router_after_validation,
        {
            END: END,
            "classification": "Classification",
        },
    )
    graph.add_edge("Classification", "Context_Enrichment")
    graph.add_edge("Context_Enrichment", "RAG_Policy_Search")
    graph.add_edge("RAG_Policy_Search", "Violation_Analysis")
    graph.add_edge("Violation_Analysis", "Action_Generator")
    graph.add_edge("Action_Generator", END)

    return graph.compile()


def run_civic_agents(
    issue_text: str,
    location_text: str,
    wait_text: str,
    requester_name: str = "Citizen",
    session_id: str = "",
    user_id: str = "",
) -> CivicState:
    graph = build_civic_graph()
    initial_state: CivicState = {
        "messages": [{"role": "user", "content": issue_text}],
        "issue_text": issue_text,
        "location_text": location_text,
        "wait_text": wait_text,
        "requester_name": requester_name,
        "session_id": session_id,
        "user_id": user_id,
        "category": "Waste",
        "location_data": {},
        "policy_deadline": None,
        "is_violation": False,
        "complaint_json": {},
    }
    return graph.invoke(initial_state)
