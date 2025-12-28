import streamlit as st
from groq import Groq

# --- 1. THE SCRUBBED KEY ---
# I am using a manual replace to strip any possible invisible characters
RAW_KEY = "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"
CLEAN_KEY = "".join(RAW_KEY.split()) # Removes ALL types of whitespace/newlines

# --- 2. INITIALIZE CLIENT ---
try:
    client = Groq(api_key=CLEAN_KEY)
except Exception as e:
    st.error(f"Initialization Error: {e}")

st.title("🛡️ Connection Recovery Mode")

# --- 3. THE TESTER ---
if st.button("Final Connection Attempt"):
    try:
        # We try the most basic model (8B) to ensure it's not a tier-access issue
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": "Hi"}],
            model="llama3-8b-8192", 
        )
        st.success("✅ IT WORKS! Response: " + chat_completion.choices[0].message.content)
    except Exception as e:
        st.error(f"❌ STILL INVALID: {e}")
        st.info("If this fails, please go to https://console.groq.com/keys, DELETE your current key, and create a BRAND NEW one. Then paste that new key here.")

# --- 4. CHAT INTERFACE (The Master Build Logic) ---
if "msgs" not in st.session_state: st.session_state.msgs = []

for m in st.session_state.msgs:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("Testing..."):
    st.session_state.msgs.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    
    try:
        # Using llama3-8b-8192 for maximum compatibility
        res = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
        ).choices[0].message.content
        
        st.session_state.msgs.append({"role": "assistant", "content": res})
        with st.chat_message("assistant"): st.markdown(res)
    except Exception as e:
        st.error(f"Chat failed: {e}")
