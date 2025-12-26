import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Health Bridge Private", layout="wide")

# Initialize Session States
for key in ["auth", "chat_log", "clara_history"]:
    if key not in st.session_state:
        if key == "auth": st.session_state.auth = {"logged_in": False, "couple_id": None, "name": None}
        else: st.session_state[key] = []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LOGIN LOGIC ---
if not st.session_state.auth["logged_in"]:
    st.title("🔐 Secure Household Login")
    u_input = st.text_input("Couple ID (Username)").strip()
    p_input = st.text_input("Password", type="password").strip()
    
    if st.button("Enter Dashboard", use_container_width=True):
        try:
            users_df = conn.read(worksheet="Users", ttl=0)
            match = users_df[(users_df['Username'].astype(str) == u_input) & (users_df['Password'].astype(str) == p_input)]
            if not match.empty:
                st.session_state.auth = {"logged_in": True, "couple_id": u_input, "name": match.iloc[0]['FullName']}
                st.rerun()
            else: st.error("Invalid credentials.")
        except Exception as e:
            st.error("Check your 'Users' tab: Username, Password, FullName")
    st.stop()

couple_id = st.session_state.auth["couple_id"]
couple_name = st.session_state.auth["name"]

# --- 4. AI HANDLERS ---
def handle_patient_chat():
    user_text = st.session_state.patient_input
    if user_text:
        st.session_state.chat_log.append({"role": "user", "user_type": "Patient", "content": user_text})
        msgs = [{"role": "system", "content": f"Your name is Cooper. Assistant for {couple_name}."}]
        for m in st.session_state.chat_log[-6:]:
            msgs.append({"role": "user" if m.get("user_type") == "Patient" else "assistant", "content": m["content"]})
        comp = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.chat_log.append({"role": "assistant", "user_type": "Cooper", "content": comp.choices[0].message.content})
        st.session_state.patient_input = ""

def handle_caregiver_chat(energy_df):
    user_text = st.session_state.caregiver_input
    if user_text:
        p_chat = "\n".join([f"{m.get('user_type', 'User')}: {m['content']}" for m in st.session_state.chat_log][-10:])
        e_data = energy_df.tail(7).to_string()
        prompt = f"System: You are Clara for {couple_name}. Context:\nChats: {p_chat}\nLogs: {e_data}"
        msgs = [{"role": "system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": user_text}]
        comp = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.clara_history.append({"role": "user", "content": user_text})
        st.session_state.clara_history.append({"role": "assistant", "content": comp.choices[0].message.content})
        st.session_state.caregiver_input = ""

# --- 5. SIDEBAR ---
with st.sidebar:
    st.subheader(f"🏠 {couple_name}")
    role_choice = st.radio("Portal:", ["Patient Portal", "Caregiver Command"])
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 6. PORTALS ---
if role_choice == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy Level", options=range(1,11), value=5)
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m.get("user_type")=="Patient" else "assistant"): st.write(m["content"])
    st.text_input("Message Cooper...", key="patient_input", on_change=handle_patient_chat)
    if st.button("Save Daily Status"):
        try:
            all_d = conn.read(worksheet="Sheet1", ttl=0)
            new_r = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": couple_id}])
            conn.update(worksheet="Sheet1", data=pd.concat([all_d, new_r], ignore_index=True))
            st.success("Saved!")
        except Exception as e: st.error(f"Error: {e}")
else:
    st.title("👩‍⚕️ Caregiver Command")
    filtered_data = pd.DataFrame()
    try:
        all_d =
