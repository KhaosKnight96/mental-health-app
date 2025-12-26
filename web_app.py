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
        st.session_state.chat_log.append({"role": "user", "user_type": "Patient", "content": user_text})
        system_prompt = "Your name is Cooper. You are a compassionate, warm health assistant talking to a Patient. Keep them encouraged and listen to their concerns."
        
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}] + 
                     [{"role": "user" if m["user_type"] == "Patient" else "assistant", "content": m["content"]} for m in st.session_state.chat_log[-6:]],
            model="llama-3.3-70b-versatile"
        )
        st.session_state.chat_log.append({"role": "assistant", "user_type": "Cooper", "content": completion.choices[0].message.content})
        st.session_state.patient_input = ""

def handle_caregiver_chat(energy_df):
    user_text = st.session_state.caregiver_input
    if user_text:
        # Create context from Cooper's chat and Energy data
        patient_context = "\n".join([f"{m['user_type']}: {m['content']}" for m in st.session_state.chat_log][-15:])
        energy_context = energy_df.tail(7).to_string() if not energy_df.empty else "No logs yet."
        
        system_prompt = f"""Your name is Clara. You are a Health Analyst for a Caregiver.
        CONTEXT FROM PATIENT CHAT WITH COOPER:
        {patient_context}
        
        CONTEXT FROM ENERGY LOGS:
        {energy_context}
        
        Goal: Analyze the patient's mood and logs. Advise the caregiver on trends or red flags."""
        
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
            model="llama-3.3-70b-versatile"
        )
        st.session_state.clara_history.append({"role": "user", "content": user_text})
        st.session_state.clara_history.append({"role": "assistant", "content": completion.choices[0].message.content})
        st.session_state.caregiver_input = ""

# --- 4. AUTH ---
if not st.session_state.authenticated:
    st.title("🔐 Secure Access")
    u = st.text_input("Username").strip().lower()
    p = st.text_input("Password", type="password").strip().lower()
    if st.button("Unlock"):
        if u == "admin" and p == "admin1":
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

if st.session_state.user_role is None:
    st.title("🤝 Welcome!")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🙋‍♂️ Patient Portal", use_container_width=True):
            st.session_state.user_role = "Patient"; st.rerun()
    with c2:
        if st.button("👩‍⚕️ Caregiver Command", use_container_width=True):
            st.session_state.user_role = "Caregiver"; st.rerun()
    st.stop()

# --- 5. PORTAL CONTENT ---
with st.sidebar:
    st.write(f"Logged in as: **{st.session_state.user_role}**")
    if st.button("Switch Role"):
        st.session_state.user_role = None; st.rerun()
    if st.button("Log Out"):
        st.session_state.authenticated = False; st.session_state.user_role = None; st.rerun()

if st.session_state.user_role == "Patient":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy Level", options=range(1,11), value=5)
    st.session_state.current_score = score
    rgb, emo = get_live_color(score)
    st.markdown(f'<div style="margin:20px auto; width:100px; height:100px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:3px solid white;"><span style="font-size:50px;">{emo}</span></div>', unsafe_allow_html=True)
    
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["user_type"] == "Patient" else "assistant"):
            st.write(m["content"])
    st.text_input("Talk to Cooper:", key="patient_input", on_change=handle_patient_chat)
    
    if st.button("Save Mood"):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score}])
            conn.update(data=pd.concat([df, new_row], ignore_index=True))
            st.success("Mood Saved!")
        except Exception as e: st.error(f"Save Failed: {e}")

else:
    st.title("👩‍⚕️ Clara Analyst")
    df = pd.DataFrame()
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            st.line_chart(df.set_index("Date"))
    except: st.warning("Connecting to data...")

    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    st.text_input("Ask Clara for analysis:", key="caregiver_input", on_change=handle_caregiver_chat, args=(df,))
