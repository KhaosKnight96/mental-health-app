
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

# --- 3. DYNAMIC MOOD VISUALIZER ---
def get_mood_emoji(score):
    if score <= 2: return "🟣 😫", "Purple (Very Low)"
    elif score <= 4: return "🔵 🙁", "Blue (Low)"
    elif score <= 6: return "🟡 😐", "Yellow (Neutral)"
    elif score <= 8: return "🟢 🙂", "Green (Good)"
    else: return "🌟 😁", "Bright Green (Excellent!)"

# --- 4. SIDEBAR ---
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

    # Animated Mood Tracker
    st.write("### 📊 Daily Energy Tracker")
    mood_score = st.select_slider("Slide to rate your energy:", options=range(1, 11), value=5)
    
    emoji, label = get_mood_emoji(mood_score)
    st.markdown(f"<h1 style='text-align: center; font-size: 70px;'>{emoji}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center;'><b>Current Status: {label}</b></p>", unsafe_allow_html=True)

    if st.button("Save Entry", use_container_width=True):
        new_entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}
        st.session_state.mood_history.append(new_entry)
        st.success("Mood saved!")

    if st.session_state.mood_history:
        st.line_chart(pd.DataFrame(st.session_state.mood_history).set_index("Date"))

# --- 6. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    
    # Data View
    if st.session_state.mood_history:
        last_score = st.session_state.mood_history[-1]['Energy']
        emoji, _ = get_mood_emoji(last_score)
        st.metric("Latest Patient Mood", f"{last_score}/10", emoji)
        st.line_chart(pd.DataFrame(st.session_state.mood_history).set_index("Date"))
    else:
        st.info("No patient data available yet.")

    st.divider()

    # Caregiver AI Assistant
    st.subheader("🤖 Caregiver AI Advisor")
    care_msg = st.text_input("Ask for advice on caregiving or trend analysis:")
    if care_msg:
        # Give AI context of patient history if it exists
        history_context = str(st.session_state.mood_history[-5:]) if st.session_state.mood_history else "No history yet."
        with st.spinner("Analyzing..."):
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": f"You are a caregiver coach. Patient history: {history_context}"},
                          {"role": "user", "content": care_msg}],
                model="llama-3.3-70b-versatile")
            st.success(chat.choices[0].message.content)
