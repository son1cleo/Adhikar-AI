from __future__ import annotations

import pandas as pd
import streamlit as st

from .analytics import build_heatmap_frame, category_summary
from .agent import run_civic_assistant
from .models import ComplaintInput


st.set_page_config(page_title="Adhikar AI", page_icon="Civic Intelligence", layout="wide")

st.title("Adhikar AI")
st.caption("Civic intelligence for complaint routing, policy grounding, and advocacy drafting.")

with st.sidebar:
    st.header("Complaint Intake")
    requester_name = st.text_input("Your name", value="Citizen")
    issue_text = st.text_area("Describe the issue", value="Huge garbage pile in Mirpur Ward 7 for 3 days.", height=120)
    location = st.text_input("Location (Ward / neighborhood)", value="Mirpur Ward 7")
    wait_text = st.text_input("How long has it waited?", value="3 days")
    submitted = st.button("Generate complaint")


left, right = st.columns([1.15, 0.85], gap="large")

if submitted:
    complaint = ComplaintInput(
        issue_text=issue_text,
        location=location,
        wait_text=wait_text,
        requester_name=requester_name,
    )
    result = run_civic_assistant(complaint)

    with left:
        st.subheader("Result")
        if result.validation_error:
            st.error(result.validation_error)
        st.metric("Detected category", result.category)
        st.write(f"Recipient: {result.recipient_name}")
        if result.recipient_email:
            st.write(f"Email: {result.recipient_email}")
        if result.recipient_phone:
            st.write(f"Phone: {result.recipient_phone}")
        st.markdown("### Policy vs. Reality")
        st.write(result.policy_vs_reality)
        st.markdown("### Retrieved policy")
        st.code(result.retrieved_policy or "No policy text found.", language="text")
        st.markdown("### Draft complaint email")
        st.code(result.complaint_email, language="text")

with right:
    st.subheader("Policy Gap Analytics")
    summary = category_summary()
    if summary:
        st.bar_chart(pd.Series(summary), height=220)
    else:
        st.info("No complaints logged yet.")

    heatmap = build_heatmap_frame()
    if not heatmap.empty:
        st.dataframe(heatmap, use_container_width=True)
        try:
            import pydeck as pdk

            layer = pdk.Layer(
                "HeatmapLayer",
                data=heatmap,
                get_position="[longitude, latitude]",
                get_weight="count",
                radiusPixels=50,
            )
            view_state = pdk.ViewState(
                latitude=float(heatmap["latitude"].mean()),
                longitude=float(heatmap["longitude"].mean()),
                zoom=11,
            )
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))
        except Exception:
            st.map(heatmap[["latitude", "longitude"]])
    else:
        st.info("Heatmap will appear once complaints are logged with matching ward coordinates.")
