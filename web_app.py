import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. CONFIG & KEY ---
st.set_page_config(page_title="Health Bridge", layout="wide")
MY_KEY = "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"

# --- 2. SESSION STATE ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": "Guest"}
if "cooper_chats" not in st.session_state: st.session_state.cooper_chats = []

# --- 3. THE FAIL-SAFE CHAT FUNCTION ---
def chat_with_ai(prompt):
    try:
        # We initialize inside the function to ensure a fresh connection every time
        client = Groq(api_key=MY_KEY.strip())
        
        # We use a shorter history to prevent "Token Limit" errors
        context = [{"role": "system", "content": "You are Cooper, a helpful health assistant."}]
        context.extend(st.session_state.cooper_chats[-3:])
        context.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=context,
            timeout=10.0 # Don't let it hang forever
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"🚨 CONNECTION ERROR: {str(e)}"

# --- 4. UI ---
st.title("🤖 Cooper's Corner")

# --- 5. CONNECTION DIAGNOSTIC (Check this if it fails) ---
with st.expander("🛠️ Debug Connection"):
    if st.button("Test Groq Connection"):
        test_client = Groq(api_key=MY_KEY.strip())
        try:
            test_client.models.list()
            st.success("Connection Successful! Your key is active.")
        except Exception as e:
            st.error(f"Connection Failed: {e}")

# --- 6. CHAT INTERFACE ---
# Display messages from session state
for msg in st.session_state.cooper_chats:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle Input
if prompt := st.chat_input("Say something to Cooper..."):
    # 1. Show user message immediately
    st.session_state.cooper_chats.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Generate and show AI message immediately
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = chat_with_ai(prompt)
            st.markdown(response)
    
    # 3. Save to history (This happens AFTER display so it can't be "interrupted")
    st.session_state.cooper_chats.append({"role": "assistant", "content": response})
