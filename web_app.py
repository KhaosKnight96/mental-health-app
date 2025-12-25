import streamlit as st
import pandas as pd
import datetime
from groq import Groq

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="AI Health Bridge", page_icon="🧠", layout="wide")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Secure Access")
        user_input = st.text_input("Username")
        pass_input = st.text_input("Password", type="password")
        if st.button("Unlock"):
            if user_input == "AppTest1" and pass_input == "TestPass1":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect username or password.")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. AI SETUP ---
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Missing GROQ_API_KEY in Streamlit Secrets.")
    st.stop()

if 'mood_history' not in st.session_state:
    st.session_state.mood_history = []

# --- 3. THE LIVE RGB ENGINE ---
def get_live_color(score):
    """Calculates a smooth RGB transition from Purple to Blue to Green"""
    # Normalize score (1-10) to a 0-1 range
    val = (score - 1) / 9.0
    
    if val < 0.5:
        # Fade from Purple (128, 0, 128) to Blue (0, 0, 255)
        r = int(128 * (1 - val * 2))
        g = 0
        b = int(128 + (127 * val * 2))
    else:
        # Fade from Blue (0, 0, 255) to Green (0, 255, 0)
        adj_val = (val - 0.5) * 2
        r = 0
        g = int(255 * adj_val)
        b = int(255 * (1 - adj_val))
    
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
    
    # Mood Tracker (Placed at top for visual impact)
    st.write("### 📊 Live Energy Tracker")
    mood_score = st.select_slider("Slide to change mood and color:", options=range(1, 11), value=5)
    
    current_rgb, current_emoji = get_live_color(mood_score)
    
    # The Live Updating Circle
    st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; margin: 10px auto;
            width: 160px; height: 160px; background-color: {current_rgb}; border-radius: 50%; 
            transition: background-color 0.3s ease-out; box-shadow: 0px 10px 30px {current_rgb}66;
            border: 6px solid white;">
            <span style="font-size: 80px;">{current_emoji}</span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("Save Entry", use_container_width=True):
        new_entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}
        st.session_state.mood_history.append(new_entry)
        st.success("Mood saved!")

    st.divider()
    
    # AI Assistant
    st.subheader("🤖 AI Health Assistant")
    user_msg = st.text_input("Talk to your AI...")
    if user_msg:
        with st.spinner("Thinking..."):
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": "You are a helpful health assistant."},
                          {"role": "user", "content": user_msg}],
                model="llama-3.3-70b-versatile")
            st.info(chat.choices[0].message.content)

# --- 6. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    if st.session_state.mood_history:
        last_score = st.session_state.mood_history[-1]['Energy']
        c_rgb, c_emoji = get_live_color(last_score)
        st.metric("Patient's Current Energy", f"{last_score}/10")
        st.markdown(f'<div style="width:50px; height:50px; background-color:{c_rgb}; border-radius:50%; border:2px solid white;"></div>', unsafe_allow_html=True)
        st.line_chart(pd.DataFrame(st.session_state.mood_history).set_index("Date"))
    else:
        st.info("No patient data logged yet.")
