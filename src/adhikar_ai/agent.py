from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from langgraph.graph import END, START, StateGraph

from .analytics import log_complaint
from .contacts import find_contact, load_contacts
from .config import CONTACTS_FILE
from .models import AgentState, ComplaintInput, ComplaintResult
from .rag import policy_text, retrieve_policy, top_policy
from .utils import extract_duration_hours, extract_policy_deadline_hours, normalize_text


CLASSIFICATION_PROMPT = (
    'Categorize the user\'s Dhaka-based civic issue into: Waste, Road, Electrical, or Water. '
    'Output only the category name.'
)


def validate_location(location: str) -> str | None:
    if not location or not location.strip():
        return "Location is required. Please provide a Ward or neighborhood."
    return None


def classify_issue(issue_text: str) -> str:
    normalized = normalize_text(issue_text)
    mappings = {
        "Waste": ["garbage", "waste", "moyla", "আবর্জনা", "ময়লা", "trash"],
        "Road": ["road", "street", "pothole", "রাস্তা", "গর্ত", "footpath"],
        "Electrical": ["electric", "light", "বিদ্যুৎ", "power", "line"],
        "Water": ["water", "pani", "পানি", "drain", "sewer"],
    }
    for category, keywords in mappings.items():
        if any(keyword in normalized for keyword in keywords):
            return category
    return "Waste"


def draft_complaint_email(
    complaint: ComplaintInput,
    category: str,
    retrieved_policy_text: str,
    deadline_hours: int | None,
    user_wait_hours: int | None,
    recipient_name: str,
) -> str:
    deadline_phrase = f"{deadline_hours} hours" if deadline_hours else "the charter deadline"
    wait_phrase = f"{user_wait_hours} hours" if user_wait_hours else complaint.wait_text
    violation_line = (
        f"The Charter promises a response within {deadline_phrase}, but this issue has waited {wait_phrase}."
        if deadline_hours and user_wait_hours is not None
        else "The charter sets a formal service expectation that has not been met."
    )

    return (
        f"Subject: Urgent {category.lower()} complaint for {complaint.location}\n\n"
        f"Dear {recipient_name},\n\n"
        f"I am writing to report a {category.lower()} issue at {complaint.location}. {violation_line}\n\n"
        f"Policy reference:\n{retrieved_policy_text}\n\n"
        "Policy vs. Reality:\n"
        f"- Policy: {deadline_phrase}\n"
        f"- Reality: {wait_phrase}\n"
        f"- Gap: The issue remains unresolved beyond the expected service window.\n\n"
        "Please arrange immediate inspection and remedial action.\n\n"
        f"Regards,\n{complaint.requester_name}\n{complaint.location}"
    )


def build_workflow():
    graph = StateGraph(AgentState)

    def validate_node(state: AgentState) -> AgentState:
        validation_error = validate_location(state.get("location", ""))
        return {**state, "validation_error": validation_error or ""}

    def classify_node(state: AgentState) -> AgentState:
        return {**state, "category": classify_issue(state.get("issue_text", ""))}

    def retrieve_node(state: AgentState) -> AgentState:
        category = state.get("category", "Waste")
        issue_text = state.get("issue_text", "")
        chunks = retrieve_policy(category, issue_text)
        best_chunk = top_policy(chunks)
        retrieved = policy_text(chunks)
        deadline_hours = extract_policy_deadline_hours(best_chunk.text if best_chunk else retrieved)
        user_wait_hours = extract_duration_hours(state.get("wait_text", ""))
        contact = find_contact(state.get("location", ""), load_contacts(CONTACTS_FILE))
        return {
            **state,
            "retrieved_policy": retrieved,
            "deadline_hours": deadline_hours or 0,
            "user_wait_hours": user_wait_hours or 0,
            "recipient_name": contact.councillor if contact else "Ward Councillor",
            "recipient_email": contact.email if contact else "",
            "recipient_phone": contact.phone if contact else "",
        }

    def draft_node(state: AgentState) -> AgentState:
        complaint = ComplaintInput(
            issue_text=state.get("issue_text", ""),
            location=state.get("location", ""),
            wait_text=state.get("wait_text", ""),
            requester_name=state.get("requester_name", "Citizen"),
        )
        email = draft_complaint_email(
            complaint=complaint,
            category=state.get("category", "Waste"),
            retrieved_policy_text=state.get("retrieved_policy", ""),
            deadline_hours=state.get("deadline_hours") or None,
            user_wait_hours=state.get("user_wait_hours") or None,
            recipient_name=state.get("recipient_name", "Ward Councillor"),
        )
        gap = _policy_gap_text(state.get("deadline_hours"), state.get("user_wait_hours"))
        return {**state, "complaint_email": email, "policy_vs_reality": gap}

    graph.add_node("validate", validate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("draft", draft_node)

    graph.add_edge(START, "validate")

    def route_after_validate(state: AgentState) -> str:
        return END if state.get("validation_error") else "classify"

    graph.add_conditional_edges("validate", route_after_validate, {END: END, "classify": "classify"})
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", END)
    return graph.compile()


def _policy_gap_text(deadline_hours: int | None, user_wait_hours: int | None) -> str:
    if deadline_hours is None or user_wait_hours is None:
        return "Policy and reality could not be compared because one time value was missing."
    if user_wait_hours > deadline_hours:
        return f"The user has waited {user_wait_hours} hours, which exceeds the promised {deadline_hours}-hour window."
    return f"The user has waited {user_wait_hours} hours, which is within the promised {deadline_hours}-hour window."


def run_civic_assistant(complaint: ComplaintInput) -> ComplaintResult:
    workflow = build_workflow()
    state = workflow.invoke(
        {
            "issue_text": complaint.issue_text,
            "location": complaint.location,
            "wait_text": complaint.wait_text,
            "requester_name": complaint.requester_name,
        }
    )

    result = ComplaintResult(
        category=state.get("category", "Waste"),
        validation_error=state.get("validation_error", ""),
        recipient_name=state.get("recipient_name", "Ward Councillor"),
        recipient_email=state.get("recipient_email", ""),
        recipient_phone=state.get("recipient_phone", ""),
        deadline_hours=state.get("deadline_hours") or None,
        user_wait_hours=state.get("user_wait_hours") or None,
        retrieved_policy=state.get("retrieved_policy", ""),
        policy_vs_reality=state.get("policy_vs_reality", ""),
        complaint_email=state.get("complaint_email", ""),
    )

    if not result.validation_error:
        log_complaint(
            {
                "location": complaint.location,
                "category": result.category,
                "recipient_name": result.recipient_name,
                "deadline_hours": result.deadline_hours,
                "user_wait_hours": result.user_wait_hours,
            }
        )
    return result
