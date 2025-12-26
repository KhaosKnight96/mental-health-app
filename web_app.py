import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Health Bridge Private", page_icon="🤝", layout="wide")

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "couple_id": None, "name": None}
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "clara_history" not in st.session_state:
    st.session_state.clara_history = []

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 3. LOGIN LOGIC ---
if not st.session_state.auth["logged_in"]:
    st.title("🔐 Secure Household Login")
    st.info("Enter your Couple ID and Password to access your private dashboard.")
    
    u_input = st.text_input("Couple ID (Username)").strip()
    p_input = st.text_input("Password", type="password").strip()
    
    if st.button("Enter Dashboard", use_container_width=True):
        try:
            users_df = conn.read(worksheet="Users", ttl=0)
            # Ensure column names match exactly: Username, Password, FullName
            match = users_df[(users_df['Username'].astype(str) == u_input) & (users_df['Password'].astype(str) == p_input)]
            
            if not match.empty:
                st.session_state.auth = {
                    "logged_in": True, 
                    "couple_id": u_input, 
                    "name": match.iloc[0]['FullName']
                }
                st.rerun()
            else:
                st.error("Invalid Couple ID or Password.")
        except Exception as e:
            st.error(f"Connection Error: Ensure your Google Sheet has a tab named 'Users' with columns: Username, Password, FullName.")
    st.stop()

# --- 4. SHARED CONTEXT ---
couple_id = st.session_state.auth["couple_id"]
couple_name = st.session_state.auth["name"]

# --- 5. AI HANDLERS ---
def handle_patient_chat():
    user_text = st.session_state.patient_input
    if user_text:
        st.session_state.chat_log.append({"role": "user", "user_type": "Patient", "content": user_text})
        msgs = [{"role": "system", "content": f"Your name is Cooper. You are a warm assistant for {couple_name}."}]
        for m in st.session_state.chat_log[-6:]:
            role = "user" if m.get("user_type") == "Patient" else "assistant"
            msgs.append({"role": role, "content": m["content"]})
        
        completion = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.chat_log.append({"role": "assistant", "user_type": "Cooper", "content": completion.choices[0].message.content})
        st.session_state.patient_input = ""

def handle_caregiver_chat(energy_df):
    user_text = st.session_state.caregiver_input
    if user_text:
        p_chat = "\n".join([f"{m.get('user_type', 'User')}: {m['content']}" for m in st.session_log if 'user_type' in m][-10:])
        e_data = energy_df.tail(7).to_string()
        prompt = f"System: You are Clara, a health analyst for {couple_name}. Analyze this context:\nChats: {p_chat}\nLogs: {e_data}"
        
        msgs = [{"role": "system", "content": prompt}]
        for m in st.session_state.clara_history[-4:]:
            msgs.append(m)
        msgs.append({"role": "user", "content": user_text})
        
        completion = client.chat.completions.create(messages=msgs, model="llama-3.3-70b-versatile")
        st.session_state.clara_history.append({"role": "user", "content": user_text})
        st.session_state.clara_history.append({"role": "assistant", "content": completion.choices[0].message.content})
        st.session_state.caregiver_input = ""

# --- 6. SIDEBAR ---
with st.sidebar:
    st.title("🏠 Household")
    st.subheader(couple_name)
    role_choice = st.radio("Go to:", ["🙋‍♂️ Patient Portal", "👩‍⚕️ Caregiver Command"])
    if st.button("Log Out"):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 7. PORTAL LOGIC ---
if "Patient" in role_choice:
    st.title("👋 Cooper Support")
    score = st.select_slider("How is your energy?", options=range(1,11), value=5)
    
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m.get("user_type") == "Patient" else "assistant"):
            st.write(m["content"])
    st.text_input("Message Cooper...", key="patient_input", on_change=handle_patient_chat)

    if st.button("Save Daily Status"):
        try:
            all_data = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": couple_id}])
            conn.update(worksheet="Sheet1", data=pd
