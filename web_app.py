import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="AI Health Bridge", page_icon="🧠", layout="wide")

# Initialize Session States
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "clara_history" not in st.session_state:
    st.session_state.clara_history = []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. HELPER FUNCTIONS ---
def get_live_color(score):
    val = (score - 1) / 9.0
    if val < 0.5:
        r, g, b = int(128 * (1 - val * 2)), 0, int(128 + (127 * val * 2))
    else:
        adj_val = (val - 0.5) * 2
        r, g, b = 0, int(255 * adj_val), int(255 * (1 - adj_val))
    emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😐", 6:"🙂", 7:"😊", 8:"😁", 9:"😆", 10:"🤩"}
    return f"rgb({r}, {g}, {b})", emojis.get(score, "😶")

def handle_patient_chat():
    user_text = st.session_state.patient_input
    if user_text:
        # Save user message
        st.session_state.chat_log.append({"role": "user", "user_type": "Patient", "content": user_text})
        
        # Format messages for API
        msgs = [{"role": "system", "content": "Your name is Cooper. You are a warm, compassionate health assistant. Focus on empathy and support."}]
        for m in st.session_state.chat_log[-6:]:
            role = "user" if m["user_type"] == "Patient" else "assistant"
            msgs.append({"role": role, "content": m["content"]})
        
        completion = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        
        # Save Cooper's response
        st.session_state.chat_log.append({"role": "assistant", "user_type": "Cooper", "content": completion.choices[0].message.content})
        st.session_state.patient_input = ""

def handle_caregiver_chat(energy_df):
    user_text = st.session_state.caregiver_input
    if user_text:
        # Create context from Cooper's chat and Energy data
        patient_history = "\n".join([f"{m['user_type']}: {m['content']}" for m in st.session_state.chat_log if m['user_type'] in ['Patient', 'Cooper']][-15:])
        energy_data = energy_df.tail(7).to_string() if not energy_df.empty else "No logs recorded."
        
        clara_prompt = f"""Your name is Clara. You are a Health Data Analyst for a caregiver. 
        You have access to the patient's conversations with their assistant Cooper and their energy logs.
        
        PATIENT CONTEXT:
        {patient_history}
        
        ENERGY LOGS (Last 7 entries):
        {energy_data}
        
        Your goal: Help the caregiver understand trends, identify concerns, and suggest support strategies."""

        msgs = [{"role": "system", "content": clara_prompt}]
        for m in st.session_state.clara_history[-6:]:
            msgs.append({"role": m["role"], "content": m["content"]})
        msgs.append({"role": "user", "content": user_text})
        
        completion = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        
        st.session_state.clara_history.append({"role": "user", "content": user_text})
        st.session_state.clara_history.append({"role": "assistant", "content": completion.choices[0].message.content})
        st.session_state.caregiver_input = ""

# --- 4. LOGIN & ROLE SELECTION ---
if not st.session_state.authenticated:
    st.title("🔐 Secure Access")
    u = st.text_input("Username").strip().lower()
    p = st.text_input("Password", type="password").strip().lower()
    if st.button("Unlock"):
        if u == "admin" and p == "admin1":
            st.session_state.authenticated = True
            st.rerun()
        else: st.error("Invalid credentials.")
    st.stop()

if st.session_state.user_role is None:
    st.title("🤝 Welcome back")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🙋‍♂️ Patient Portal", use_container_width=True):
            st.session_state.user_role = "Patient"; st.rerun()
    with c2:
        if st.button("👩‍⚕️ Caregiver Command", use_container_width=True):
            st.session_state.user_role = "Caregiver"; st.rerun()
    st.stop()

# --- 5. APP CONTENT ---
with st.sidebar:
    st.write(f"Active Role: **{st.session_state.user_role}**")
    if st.button("Switch Role"):
        st.session_state.user_role = None; st.rerun()
    if st.button("Log Out"):
        st.session_state.authenticated = False; st.session_state.user_role = None; st.rerun()

if st.session_state.user_role == "Patient":
    st.title("👋 Cooper's Corner")
    score = st.select_slider("How is your energy?", options=range(1,11), value=5)
    st.session_state.current_score = score
    rgb, emo = get_live_color(score)
    st.markdown(f'<div style="margin:10px auto; width:80px; height:80px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:3px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.2);"><span style="font-size:40px;">{emo}</span></div>', unsafe_allow_html=True)
    
    st.divider()
    for m in st.session_state.chat_log:
        if m['user_type'] in ['Patient', 'Cooper']:
            with st.chat_message("user" if m["user_type"] == "Patient" else "assistant"):
                st.write(m["content"])
    
    st.text_input("Talk to Cooper:", key="patient_input", on_change=handle_patient_chat)
    
    if st.button("Save Daily Log", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score}])
            conn.update(data=pd.concat([df, new_row], ignore_index=True))
            st.success("Entry saved to Google Sheets!")
        except Exception as e: st.error(f"Save failed: {e}")

else:
    st.title("👩‍⚕️ Clara: Caregiver Analyst")
    df = pd.DataFrame()
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            st.line_chart(df.set_index("Date"))
            st.metric("Latest Energy Score", f"{df.iloc[-1]['Energy']}/10")
    except: st.warning("Connecting to logs...")

    st.divider()
    st.subheader("Insight Chat")
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    
    st.text_input("Ask Clara to analyze trends:", key="caregiver_input", on_change=handle_caregiver_chat, args=(df,))
