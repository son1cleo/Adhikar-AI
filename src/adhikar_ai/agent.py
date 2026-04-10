from __future__ import annotations

from .agents import run_civic_agents
from .models import ComplaintInput, ComplaintResult


def run_civic_assistant(complaint: ComplaintInput) -> ComplaintResult:
    """Backward-compatible wrapper that now delegates to the multi-agent graph."""
    state = run_civic_agents(
        issue_text=complaint.issue_text,
        location_text=complaint.location,
        wait_text=complaint.wait_text,
        requester_name=complaint.requester_name,
    )

    complaint_json = state.get("complaint_json", {})
    location_data = complaint_json.get("location_data", {})

    validation_error = ""
    if state.get("needs_user_input"):
        validation_error = state.get("messages", [{}])[-1].get("content", "Missing required information.")

    deadline = complaint_json.get("policy_deadline_hours")
    user_wait = complaint_json.get("user_duration_hours")
    if deadline is not None and user_wait is not None:
        if user_wait > deadline:
            gap_text = f"The user has waited {user_wait} hours, which exceeds the promised {deadline}-hour window."
        else:
            gap_text = f"The user has waited {user_wait} hours, which is within the promised {deadline}-hour window."
    else:
        gap_text = "Policy and reality could not be compared because one time value was missing."

    complaint_email = (
        f"Subject: Civic Complaint ({complaint_json.get('category', 'General')})\n\n"
        f"Issue: {complaint_json.get('issue_text', '')}\n"
        f"Location: {complaint_json.get('location', '')}\n"
        f"Policy comparison: {complaint_json.get('comparison', '')}\n"
        f"Recommended action: {complaint_json.get('recommended_action', '')}"
    )

    return ComplaintResult(
        category=complaint_json.get("category", "Waste"),
        validation_error=validation_error,
        recipient_name=location_data.get("recipient_name", "Ward Councillor"),
        recipient_email=location_data.get("recipient_email", ""),
        recipient_phone=location_data.get("recipient_phone", ""),
        deadline_hours=deadline,
        user_wait_hours=user_wait,
        retrieved_policy=complaint_json.get("retrieved_policy", ""),
        policy_vs_reality=gap_text,
        complaint_email=complaint_email,
    )
