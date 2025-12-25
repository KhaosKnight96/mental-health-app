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

# --- 2. CONNECTIONS & STATE ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Initialize Chat History if it doesn't exist
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []

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

# --- 4. COOPER AI LOGIC ---
def handle_chat(role_context):
    """Universal chat handler for Patient and Caregiver"""
    user_input_key = f"{role_context}_input"
    user_text = st.session_state[user_input_key]
    
    if user_text:
        # Add User message to log
        st.session_state.chat_log.append({"role": "user", "user_type": role_context, "content": user_text})
        
        # Prepare AI context
        energy_context = f"The patient's current energy is {st.session_state.get('current_score', 5)}/10."
        system_prompt = f"Your name is Cooper. You are a compassionate health assistant helping a {role_context}. {energy_context}"
        
        # Call Groq
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            model="llama-3.3-70b-versatile"
        )
        
        # Add AI response to log
        ai_resp = chat_completion.choices[0].message.content
        st.session_state.chat_log.append({"role": "assistant", "content": ai_resp})
        
        # Clear the input box
        st.session_state[user_input_key] = ""

# --- 5. NAVIGATION ---
role = st.sidebar.radio("Select Role:", ["Patient Portal", "Caregiver Coach"])

# --- 6. PATIENT PORTAL ---
if role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    
    mood_score = st.select_slider("Rate your energy:", options=range(1, 11), value=5)
    st.session_state.current_score = mood_score
    
    rgb, emo = get_live_color(mood_score)
    st.markdown(f"""
        <div style="margin:auto; width:130px; height:130px; background-color:{rgb}; border-radius:50%; 
        display:flex; justify-content:center; align-items:center; border:5px solid white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
            <span style="font-size:70px;">{emo}</span>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Cooper Chat Section
    st.subheader("🤖 Chat with Cooper")
    
    # Display History
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    st.text_input("Message Cooper:", key="patient_input", on_change=handle_chat, args=("patient",), placeholder="Ask Cooper anything...")

    # Save Entry
    if st.button("Save Entry Permanently", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Mood safely stored!")
        except:
            st.error("Save failed. Check sheet permissions.")

# --- 7. CAREGIVER COACH ---
else:
    st.title("👩‍⚕️ Caregiver Command Center")
    
    # Data Visualization
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            last_val = int(df.iloc[-1]['Energy'])
            st.metric("Patient's Latest Energy", f"{last_val}/10")
            st.line_chart(df.set_index("Date"))
        else:
            st.info("No data entries found yet.")
    except:
        st.warning("Google Sheets connection pending.")

    st.divider()
    
    # Cooper Chat Section (Caregiver Side)
    st.subheader("🤖 Caregiver Advisor (Cooper)")
    
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    st.text_input("Ask Cooper for advice:", key="caregiver_input", on_change=handle_chat, args=("caregiver",), placeholder="How can I support them today?")
