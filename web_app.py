import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="AI Health Bridge", page_icon="🧠", layout="wide")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Secure Access")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Unlock"):
            if u == "AppTest1" and p == "TestPass1":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect username or password.")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

# --- 3. THE LIVE RGB ENGINE ---
def get_live_color(score):
    val = (score - 1) / 9.0
    if val < 0.5:
        r, g, b = int(128 * (1 - val * 2)), 0, int(128 + (127 * val * 2))
    else:
        adj_val = (val - 0.5) * 2
        r, g, b = 0, int(255 * adj_val), int(255 * (1 - adj_val))
    emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😐", 6:"🙂", 7:"😊", 8:"😁", 9:"😆", 10:"🤩"}
    return f"rgb({r}, {g}, {b})", emojis.get(score, "😶")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("Navigation")
    role = st.sidebar.radio("Select your role:", ["Patient Portal", "Caregiver Coach"])
    st.divider()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. PATIENT PORTAL ---
if role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    
    # 1. Mood Tracker Section
    st.write("### 📊 Live Energy Tracker")
    mood_score = st.select_slider("Slide to rate your current energy level:", options=range(1, 11), value=5)
    
    current_rgb, current_emoji = get_live_color(mood_score)
    
    st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; margin: 10px auto;
            width: 150px; height: 150px; background-color: {current_rgb}; border-radius: 50%; 
            transition: background-color 0.4s ease; box-shadow: 0px 10px 30px {current_rgb}66;
            border: 6px solid white;">
            <span style="font-size: 80px;">{current_emoji}</span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # 2. COOPER AI ASSISTANT (Moved Above Save Button)
    st.subheader("🤖 Chat with Cooper")
    st.write("Cooper is here to support you. How are you feeling?")
    
    patient_msg = st.text_input("Message Cooper:", placeholder="Talk to Cooper...")
    
    if patient_msg:
        with st.spinner("Cooper is thinking..."):
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": f"Your name is Cooper. You are a compassionate health assistant. The patient currently feels like a {mood_score}/10 energy level. Provide short, empathetic support and always refer to yourself as Cooper if asked."},
                    {"role": "user", "content": patient_msg}
                ],
                model="llama-3.3-70b-versatile"
            )
            st.info(f"*Cooper:* {chat.choices[0].message.content}")

    st.divider()

    # 3. Save Button (Moved to Bottom)
    if st.button("Save Entry Permanently", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_data = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}])
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Mood safely stored in Google Sheets!")
        except Exception as e:
            st.error(f"Save failed: {e}")

# --- 6. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    df = conn.read(ttl="1m")
    
    if not df.empty:
        last_score = int(df.iloc[-1]['Energy'])
        c_rgb, c_emoji = get_live_color(last_score)
        
        st.metric("Patient's Latest Energy", f"{last_score}/10")
        st.markdown(f'''<div style="width:60px; height:60px; background-color:{c_rgb}; border-radius:50%; 
                    display:flex; justify-content:center; align-items:center; border:3px solid white;">
                    <span style="font-size:30px;">{c_emoji}</span></div>''', unsafe_allow_html=True)
        st.line_chart(df.set_index("Date"))
    else:
        st.info("No data available yet.")

    st.divider()
    st.subheader("🤖 Caregiver AI Advisor (Cooper)")
    care_msg = st.text_input("Ask Cooper for caregiving advice:")
    if care_msg:
        with st.spinner("Cooper is analyzing..."):
            chat = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Your name is Cooper. You are a caregiver coach helping someone look after a loved one."},
                    {"role": "user", "content": care_msg}
                ],
                model="llama-3.3-70b-versatile")
            st.success(f"*Cooper:* {chat.choices[0].message.content}")
