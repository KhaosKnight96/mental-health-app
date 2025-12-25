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

def handle_chat(role_context):
    user_input_key = f"{role_context}_input"
    user_text = st.session_state[user_input_key]
    if user_text:
        st.session_state.chat_log.append({"role": "user", "content": user_text})
        energy_context = f"The patient's current energy is {st.session_state.get('current_score', 5)}/10."
        system_prompt = f"Your name is Cooper. You are a compassionate health assistant helping a {role_context}. {energy_context}"
        
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_log[-5:]],
            model="llama-3.3-70b-versatile"
        )
        st.session_state.chat_log.append({"role": "assistant", "content": chat_completion.choices[0].message.content})
        st.session_state[user_input_key] = ""

# --- 4. AUTHENTICATION & ROLE SELECTION ---

# Stage 1: Password Login
if not st.session_state.authenticated:
    st.title("🔐 Secure Access")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if u == "AppTest1" and p == "TestPass1":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

# Stage 2: Role Selection (After Login, Before App)
if st.session_state.user_role is None:
    st.title("🤝 Welcome back!")
    st.subheader("Please select your portal to continue:")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🙋‍♂️ I am the Patient", use_container_width=True, type="primary"):
            st.session_state.user_role = "Patient Portal"
            st.rerun()
    with col2:
        if st.button("👩‍⚕️ I am the Caregiver", use_container_width=True, type="primary"):
            st.session_state.user_role = "Caregiver Coach"
            st.rerun()
    st.stop()

# --- 5. MAIN APP CONTENT ---

# Sidebar for switching or logging out
with st.sidebar:
    st.title("AI Health Bridge")
    st.write(f"Logged in as: *{st.session_state.user_role}*")
    if st.button("Switch Role"):
        st.session_state.user_role = None
        st.rerun()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.rerun()

# --- PATIENT PORTAL ---
if st.session_state.user_role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    mood_score = st.select_slider("Rate your energy:", options=range(1, 11), value=5)
    st.session_state.current_score = mood_score
    rgb, emo = get_live_color(mood_score)
    st.markdown(f'<div style="margin:auto; width:130px; height:130px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:5px solid white;"><span style="font-size:70px;">{emo}</span></div>', unsafe_allow_html=True)
    
    st.divider()
    st.subheader("🤖 Chat with Cooper")
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])
    st.text_input("Message Cooper:", key="patient_input", on_change=handle_chat, args=("patient",))

    if st.button("Save Entry Permanently", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}])
            conn.update(data=pd.concat([df, new_row], ignore_index=True))
            st.success("Mood stored!")
        except:
            st.error("Save failed.")

# --- CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            last_val = int(df.iloc[-1]['Energy'])
            st.metric("Latest Energy Log", f"{last_val}/10")
            st.line_chart(df.set_index("Date"))
        else:
            st.info("No data entries found yet.")
    except:
        st.warning("Database connection pending.")

    st.divider()
    st.subheader("🤖 Caregiver Advisor (Cooper)")
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])
    st.text_input("Ask Cooper for advice:", key="caregiver_input", on_change=handle_chat, args=("caregiver",))
