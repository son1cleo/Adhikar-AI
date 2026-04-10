from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adhikar_ai.agents import run_civic_agents
from adhikar_ai.contacts import load_contacts
from adhikar_ai.config import CONTACTS_FILE
from adhikar_ai.database import insert_email_log, list_policy_violations, ward_violation_counts
from adhikar_ai.email_service import EmailComposer, EmailSender
from adhikar_ai.supabase_client import supabase_store


st.set_page_config(page_title="Adhikar AI", page_icon="Civic", layout="wide")

st.title("Adhikar AI")
st.caption("RAG multi-agent civic assistant for Dhaka residents")


def ensure_identity() -> None:
    with st.sidebar:
        st.header("Login")
        if "user_name" not in st.session_state:
            st.session_state.user_name = ""
        if "user_email" not in st.session_state:
            st.session_state.user_email = ""
        if "user_id" not in st.session_state:
            st.session_state.user_id = ""
        if "session_id" not in st.session_state:
            st.session_state.session_id = ""
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
        if "email_draft" not in st.session_state:
            st.session_state.email_draft = ""
        if "email_subject" not in st.session_state:
            st.session_state.email_subject = ""
        if "last_complaint_json" not in st.session_state:
            st.session_state.last_complaint_json = {}

        with st.form("identity_form", clear_on_submit=False):
            name = st.text_input("Name", value=st.session_state.user_name)
            email = st.text_input("Email", value=st.session_state.user_email)
            submitted = st.form_submit_button("Continue")

        if submitted and name.strip() and email.strip():
            st.session_state.user_name = name.strip()
            st.session_state.user_email = email.strip()
            if supabase_store.enabled:
                user = supabase_store.upsert_user(st.session_state.user_name, st.session_state.user_email)
                if user is not None:
                    st.session_state.user_id = user.id
                    session_id = supabase_store.create_session(user.id)
                    if session_id:
                        st.session_state.session_id = session_id
                        history = supabase_store.fetch_messages(session_id)
                        st.session_state.chat_history = [
                            {"role": row.get("role", "assistant"), "content": row.get("content", "")} for row in history
                        ]
            if not st.session_state.user_id:
                st.session_state.user_id = f"local-{st.session_state.user_email}"
            if not st.session_state.session_id:
                st.session_state.session_id = f"local-session-{st.session_state.user_email}"
            st.success("Login ready. No password or email verification is required.")


ensure_identity()

if not st.session_state.user_email:
    st.info("Enter your name and email in the sidebar to start. The system stores sessions without password or verification.")
    st.stop()


def persist_message(role: str, content: str) -> None:
    st.session_state.chat_history.append({"role": role, "content": content})
    if supabase_store.enabled and st.session_state.session_id:
        supabase_store.insert_message(st.session_state.session_id, role, content)


portal_tab, dashboard_tab = st.tabs(["Citizen Portal", "Intelligence Dashboard"])

with portal_tab:
    st.subheader("Citizen Portal")
    st.write(f"Signed in as **{st.session_state.user_name}** ({st.session_state.user_email})")

    issue_text = st.text_area("Issue", value="Huge garbage pile in Mirpur Ward 7", height=120)
    location_text = st.text_input("Location / Ward / neighborhood", value="Mirpur Ward 7")
    wait_text = st.text_input("How long has it persisted?", value="3 days")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_message = st.chat_input("Ask for help, or paste the complaint details again")
    if user_message:
        combined_issue = user_message if issue_text.strip() == "" else f"{issue_text}\n\n{user_message}"
        persist_message("user", user_message)

        state = run_civic_agents(
            issue_text=combined_issue,
            location_text=location_text,
            wait_text=wait_text,
            requester_name=st.session_state.user_name,
            session_id=st.session_state.session_id,
            user_id=st.session_state.user_id,
        )

        if state.get("needs_user_input"):
            prompt = state.get("messages", [{"content": "Please share missing details."}])[-1]["content"]
            persist_message("assistant", prompt)
        else:
            complaint_json = state.get("complaint_json", {})
            st.session_state.last_complaint_json = complaint_json
            reply = state.get("assistant_reply") or (
                f"Your issue was classified as {complaint_json.get('category', 'Unknown')}. "
                f"Status: {complaint_json.get('consistency_status', 'unknown')}."
            )
            persist_message("assistant", reply)
            persist_message("assistant", "Structured output:\n```json\n" + json.dumps(complaint_json, ensure_ascii=False, indent=2) + "\n```")
            st.session_state.email_subject = state.get("email_subject", "")
            st.session_state.email_draft = state.get("email_draft", "")
            st.session_state.last_complaint_json = complaint_json

    complaint_json = st.session_state.last_complaint_json or {}
    if complaint_json:
        st.markdown("### Result")
        st.metric("Category", complaint_json.get("category", "Unknown"))
        st.write(f"Consistency: {complaint_json.get('consistency_status', 'unknown')}")
        st.write(f"Severity: {complaint_json.get('severity_flag', 'low')}")
        st.write(f"Policy deadline hours: {complaint_json.get('policy_deadline_hours')}")
        st.write(f"User duration hours: {complaint_json.get('user_duration_hours')}")
        st.write(f"Ward: {complaint_json.get('location_data', {}).get('ward', '')}")

        st.markdown("### Policy vs Reality")
        st.write(complaint_json.get("comparison", ""))
        st.markdown("### Retrieved policy")
        st.code(complaint_json.get("retrieved_policy", "No policy text found."), language="text")
        if complaint_json.get("web_context"):
            st.markdown("### Brave context")
            st.json(complaint_json.get("web_context"))

        recipient_email = complaint_json.get("location_data", {}).get("recipient_email", "")
        recipient_name = complaint_json.get("location_data", {}).get("recipient_name", "Authority")
        composer = EmailComposer()
        email_message = composer.compose(complaint_json, recipient_email, recipient_name)

        st.markdown("### Email Draft")
        draft_text = st.text_area(
            "Edit before sending",
            value=st.session_state.email_draft or email_message.get_content(),
            height=300,
            key="editable_email_draft",
        )
        if st.button("Send to Authority"):
            sender = EmailSender()
            message = composer.compose(complaint_json, recipient_email, recipient_name)
            message.set_content(draft_text)
            success, status = sender.send(message)
            insert_email_log(
                {
                    "session_id": st.session_state.session_id,
                    "user_id": st.session_state.user_id,
                    "recipient_email": recipient_email,
                    "recipient_name": recipient_name,
                    "status": "sent" if success else "failed",
                    "complaint_json": complaint_json,
                }
            )
            if success:
                st.success(status)
            else:
                st.warning(status)

with dashboard_tab:
    st.subheader("Intelligence Dashboard")

    violations = list_policy_violations()
    violations_df = pd.DataFrame(violations)
    if not violations_df.empty:
        filter_options = ["All"] + sorted(violations_df["consistency_status"].fillna("unknown").unique().tolist())
        selected_filter = st.selectbox("Filter by consistency", filter_options)
        if selected_filter != "All":
            violations_df = violations_df[violations_df["consistency_status"].fillna("unknown") == selected_filter]

        ward_counts = ward_violation_counts()
        if ward_counts:
            counts_df = pd.DataFrame(ward_counts)
            st.bar_chart(counts_df.set_index("ward")["total_violations"])

        st.markdown("### Recent policy violations")
        display_columns = [
            col
            for col in [
                "created_at",
                "category",
                "location",
                "ward",
                "consistency_status",
                "severity_flag",
                "policy_deadline_hours",
                "user_duration_hours",
            ]
            if col in violations_df.columns
        ]
        st.dataframe(violations_df[display_columns], use_container_width=True)

        contacts = load_contacts(CONTACTS_FILE)
        if contacts:
            contacts_df = pd.DataFrame([contact.__dict__ for contact in contacts])
            merged = violations_df.merge(contacts_df, on="ward", how="left")
            merged = merged.dropna(subset=["latitude", "longitude"])
            if not merged.empty:
                st.markdown("### Ward map")
                st.map(merged[["latitude", "longitude"]])
            else:
                st.info("No coordinates available for the selected violations.")
    else:
        st.info("No policy violations logged yet.")
