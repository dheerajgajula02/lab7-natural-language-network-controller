#!/usr/bin/env python3
"""Objective 4 frontend: speak an intent, confirm by voice, watch it apply.

Run with: streamlit run voice_app.py
"""

import streamlit as st

from demo_natural_language import translate_intent
from intent_controller import (
    apply_policy,
    diagnose_failure,
    get_flows,
    roast_intent,
    validate_policy,
)
from voice_controller import capture_voice_intent

st.set_page_config(page_title="Lab 7 voice controller", page_icon="🎙️")
st.title("🎙️ Lab 7 voice intent controller")
st.caption("Speak → review the draft → say yes to apply. Nothing touches the switch until you confirm.")

if st.button("↺ New intent"):
    st.session_state.clear()
    st.rerun()


def flow_table(flows):
    """Compact rows for display: priority, match summary, action."""
    rows = []
    for flow in flows:
        match = flow.get("match", {})
        actions = flow.get("actions", [])
        rows.append({
            "priority": flow.get("priority"),
            "match": ", ".join(f"{key}={value}" for key, value in sorted(match.items())),
            "action": "DROP" if not actions else " → ".join(map(str, actions)),
        })
    return rows


st.subheader("1 · Speak your intent")
clip = st.audio_input("Press the mic and speak in a full sentence")
if clip:
    st.audio(clip)
    with st.spinner("Transcribing..."):
        transcript = capture_voice_intent(audio_bytes=clip.getvalue())
    st.session_state["transcript"] = transcript
    st.markdown(f"### 🗣️ You said:\n> ## {transcript}")
    try:
        st.session_state["policy"] = translate_intent(transcript)
    except ValueError as error:
        st.session_state["policy"] = None
        st.error(f"Request failed: {error}")
        with st.spinner("Asking the LLM why..."):
            reason = diagnose_failure(transcript, error)
            roast = roast_intent(transcript)
        if reason:
            st.warning(f"Likely reason: {reason}")
        if roast:
            st.markdown(f"### 🔥 {roast}")

policy = st.session_state.get("policy")
if policy:
    st.subheader("2 · Review the draft")
    st.json(policy)
    verdict = validate_policy(policy)
    (st.success if verdict.startswith("OK") else st.error)(verdict)
    if verdict.startswith("OK"):
        st.subheader("3 · Confirm by voice")
        confirm = st.audio_input("Say yes to apply, anything else to discard")
        if confirm:
            with st.spinner("Transcribing..."):
                answer = capture_voice_intent(audio_bytes=confirm.getvalue())
            st.markdown(f"### 👂 Confirmation heard:\n> ## {answer}")
            words = [word.strip(".,!?") for word in answer.lower().split()]
            if "yes" in words:
                with st.spinner("Installing flows..."):
                    apply_policy(policy)
                    lab = [flow for flow in get_flows() if flow.get("priority", 0) >= 90]
                st.success(f"✅ Rule is active: {len(lab)} lab flows on s1.")
                st.subheader("Active lab flows")
                st.table(flow_table(lab))
            else:
                st.warning("Policy discarded; nothing was installed.")
