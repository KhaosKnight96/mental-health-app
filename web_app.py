import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIG & LOGIN ---
st.set_page_config(page_title="AI Health Bridge", page_icon="🧠", layout="wide")

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
            st.error("Invalid credentials")
    st.stop()

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

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

# --- 4. CALLBACK FOR AUTO-CLEARING TEXT ---
def handle_patient_chat():
    user_text = st.session_state.patient_input
    if user_text:
        # Get AI response
        chat = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"Your name is Cooper. The patient's energy is {st.session_state.get('current_score', 5)}/10. Be supportive."},
                {"role": "user", "content": user_text}
            ],
            model="llama-3.3-70b-versatile"
        )
        # Store response and clear input
        st.session_state.patient_response = chat.choices[0].message.content
        st.session_state.patient_input = ""

# --- 5. NAVIGATION ---
role = st.sidebar.radio("Select Role:", ["Patient Portal", "Caregiver Coach"])

# --- 6. PATIENT PORTAL ---
if role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    
    # Mood Tracker
    st.write("### 📊 Live Energy Tracker")
    mood_score = st.select_slider("Slide to rate your energy:", options=range(1, 11), value=5)
    st.session_state.current_score = mood_score # Save for Cooper's context
    
    rgb, emo = get_live_color(mood_score)
    st.markdown(f"""
        <div style="display: flex; justify-content: center; align-items: center; margin: 10px auto;
            width: 140px; height: 140px; background-color: {rgb}; border-radius: 50%; 
            transition: background-color 0.4s ease; border: 5px solid white;">
            <span style="font-size: 70px;">{emo}</span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Cooper AI Assistant with Auto-Clear
    st.subheader("🤖 Chat with Cooper")
    st.text_input(
        "Message Cooper:", 
        key="patient_input", 
        on_change=handle_patient_chat, 
        placeholder="Type here and hit Enter..."
    )

    if "patient_response" in st.session_state:
        st.info(f"*Cooper:* {st.session_state.patient_response}")

    st.divider()

    # Save Entry
    if st.button("Save Entry Permanently", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Mood safely stored!")
        except Exception as e:
            st.error("Google Sheet Save failed. Please check your credentials.")

# --- 7. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            last_val = int(df.iloc[-1]['Energy'])
            c_rgb, c_emo = get_live_color(last_val)
            st.metric("Latest Patient Energy", f"{last_val}/10")
            st.line_chart(df.set_index("Date"))
        else:
            st.info("No entries found yet.")
    except:
        st.warning("Database connection error.")
