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
    colors = {
        1: "#800080", 2: "#9932CC", 3: "#0000FF", 4: "#1E90FF",
        5: "#FFD700", 6: "#FFFF00", 7: "#ADFF2F", 8: "#7FFF00",
        9: "#32CD32", 10: "#008000"
    }
    emojis = {
        1: "😫", 2: "😖", 3: "🙁", 4: "☹️", 5: "😐", 
        6: "🙂", 7: "😊", 8: "😁", 9: "😆", 10: "🤩"
    }
    return colors.get(score, "#FFFFFF"), emojis.get(score, "😶")

# --- 4. SIDEBAR NAVIGATION ---
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
    st.write("### 📊 Daily Energy Tracker")
    mood_score = st.select_slider("Slide to rate your energy level:", options=range(1, 11), value=5)
    
    color_hex, emoji_icon = get_mood_visuals(mood_score)
    
    st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; margin: 20px auto;
            width: 140px; height: 140px; background-color: {color_hex}; border-radius: 50%; 
            transition: background-color 0.6s ease; box-shadow: 0px 4px 15px rgba(0,0,0,0.3);
            border: 5px solid white;">
            <span style="font-size: 70px;">{emoji_icon}</span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("Save Entry", use_container_width=True):
        new_entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}
        st.session_state.mood_history.append(new_entry)
        st.success(f"Mood saved!")

    if st.session_state.mood_history:
        df = pd.DataFrame(st.session_state.mood_history)
        st.line_chart(df.set_index("Date"))

# --- 6. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    
    if st.session_state.mood_history:
        last_score = st.session_state.mood_history[-1]['Energy']
        c_color, c_emoji = get_mood_visuals(last_score)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.metric("Latest Mood Score", f"{last_score}/10")
            st.markdown(f"""
                <div style="width:80px; height:80px; background-color:{c_color}; 
                border-radius:50%; display:flex; justify-content:center; align-items:center; border:3px solid #eee;">
                <span style="font-size:40px;">{c_emoji}</span></div>
            """, unsafe_allow_html=True)
        with col2:
            st.write("### Trend Line")
            st.line_chart(pd.DataFrame(st.session_state.mood_history).set_index("Date"))
    else:
        st.info("No patient data available yet.")

    st.divider()
    st.subheader("🤖 Caregiver AI Advisor")
    care_msg = st.text_input("Ask for advice or trend analysis:")
    if care_msg:
        history_context = str(st.session_state.mood_history[-5:]) if st.session_state.mood_history else "No history yet."
        with st.spinner("Analyzing..."):
            chat = client.chat.completions.create(
                messages=[{"role": "system", "content": f"You are a caregiver coach. Recent history: {history_context}"},
                          {"role": "user", "content": care_msg}],
                model="llama-3.3-70b-versatile")
            st.success(chat.choices[0].message.content)
