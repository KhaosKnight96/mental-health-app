
You sent
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

# --- 3. DYNAMIC COLOR & EMOJI ENGINE ---
def get_mood_visuals(score):
    # Hex colors: Purple (1) -> Blue (3-4) -> Yellow (5-6) -> Green (9-10)
    colors = {
        1: "#800080", 2: "#9932CC",  # Purples
        3: "#0000FF", 4: "#1E90FF",  # Blues
        5: "#FFD700", 6: "#FFFF00",  # Yellows
        7: "#ADFF2F", 8: "#7FFF00",  # Light Greens
        9: "#32CD32", 10: "#008000"  # Deep Greens
    }
    emojis = {
        1: "😫", 2: "😖", 3: "🙁", 4: "☹️", 5: "😐", 
        6: "🙂", 7: "😊", 8: "😁", 9: "😆", 10: "🤩"
    }
    return colors.get(score, "#FFFFFF"), emojis.get(score, "😶")

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("Navigation")
    role = st.radio("Select your role:", ["Patient Portal", "Caregiver Coach"])
    st.divider()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# --- 5. PATIENT PORTAL ---
if role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    
    # AI Assistant
    st.subheader("🤖 AI Health Assistant")
    user_msg = st.text_input("How can I help you today?")
    if user_msg:
        with st.spinner("Thinking..."):
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": "You are a compassionate health assistant."},
                          {"role": "user", "content": user_msg}],
                model="llama-3.3-70b-versatile")
            st.info(chat.choices[0].message.content)

    st.divider()

    # Color-Changing Mood Tracker
    st.write("### 📊 Daily Energy Tracker")
    mood_score = st.select_slider("Slide to rate your energy level:", options=range(1, 11), value=5)
    
    # Get dynamic color and emoji
    color_hex, emoji_icon = get_mood_visuals(mood_score)
    
    # Display the color-changing circle
    st.markdown(f"""
        <div style="
            display: flex; 
            justify-content: center; 
            align-items: center; 
            margin: 20px auto;
            width: 140px; 
            height: 140px; 
            background-color: {color_hex}; 
            border-radius: 50%; 
            transition: background-color 0.6s ease;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
            border: 5px solid white;">
            <span style="font-size: 70px;">{emoji_icon}</span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("Save Entry", use_container_width=True):
        new_entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}
        st.session_state.mood_history.append(new_entry)
        st.success(f"Mood saved! Status: {emoji_icon}")

    if st.session_state.mood_history:
        st.line_chart(pd.DataFrame(st.session_state.mood_history).set_index("Date"))

# --- 6. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    
    # Shared Data View
    if st.session_state.mood_history:
        last_score
