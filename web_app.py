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
# Note: Ensure your Secrets are saved in the Streamlit Dashboard
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Connection Error. Please check your Secrets tab.")

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
    user_text = st.session_state.get(user_input_key)
    if user_text:
        # Add User message to log
        st.session_state.chat_log.append({"role": "user", "content": user_text})
        
        # Prepare AI context
        energy_context = f"The patient's current energy is {st.session_state.get('current_score', 5)}/10."
        system_prompt = f"Your name is Cooper. You are a compassionate health assistant helping a {role_context}. {energy_context}"
        
        # Call Groq (includes history context)
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}] + 
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_log[-5:]],
            model="llama-3.3-70b-versatile"
        )
        # Store response
        st.session_state.chat_log.append({"role": "assistant", "content": chat_completion.choices[0].message.content})
        # Reset input box
        st.session_state[user_input_key] = ""

# --- 4. AUTHENTICATION ---
if not st.session_state.authenticated:
    st.title("🔐 Secure Access")
    
    # We use a unique key to prevent browser autocomplete issues
    u = st.text_input("Username", key="login_user").strip().lower()
    p = st.text_input("Password", type="password", key="login_pass").strip().lower()
    
    if st.button("Unlock App"):
        # SIMPLEST POSSIBLE CHECK: everything lowercase
        if u == "admin" and p == "admin1":
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(f"Try again. Hint: admin / admin1")
    st.stop()
# Stage 2: Role Selection
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

# --- 5. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🧠 AI Health Bridge")
    st.write(f"Logged in as: **{st.session_state.user_role}**")
    st.divider()
    if st.button("Switch Role"):
        st.session_state.user_role = None
        st.rerun()
    if st.button("Clear Chat History"):
        st.session_state.chat_log = []
        st.rerun()
    st.divider()
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.rerun()

# --- 6. PORTAL LOGIC ---
if st.session_state.user_role == "Patient Portal":
    st.title("👋 Patient Support Portal")
    mood_score = st.select_slider("How is your energy right now?", options=range(1, 11), value=5)
    st.session_state.current_score = mood_score
    
    rgb, emo = get_live_color(mood_score)
    st.markdown(f'<div style="margin:20px auto; width:130px; height:130px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:5px solid white; box-shadow: 0 4px 10px rgba(0,0,0,0.3);"><span style="font-size:70px;">{emo}</span></div>', unsafe_allow_html=True)
    
    st.divider()
    
    # Cooper Chat
    st.subheader("🤖 Chat with Cooper")
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])
    st.text_input("Message Cooper:", key="patient_input", on_change=handle_chat, args=("patient",), placeholder="Type here and press Enter...")

    st.divider()
    if st.button("Save Entry Permanently", use_container_width=True):
        try:
            df = conn.read(ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": mood_score}])
            conn.update(data=pd.concat([df, new_row], ignore_index=True))
            st.success("Mood stored safely in the logs!")
        except Exception as e:
            st.error(f"Save failed: {e}")

else:
    st.title("👩‍⚕️ Caregiver Command Center")
    try:
        df = conn.read(ttl="1m")
        if not df.empty:
            last_val = int(df.iloc[-1]['Energy'])
            st.metric("Latest Recorded Energy", f"{last_val}/10")
            st.line_chart(df.set_index("Date"))
            with st.expander("View Historical Data"):
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No data entries found yet.")
    except:
        st.warning("Connecting to database...")

    st.divider()
    
    # Caregiver Advisor
    st.subheader("🤖 Caregiver Advisor (Cooper)")
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])
    st.text_input("Ask Cooper for advice:", key="caregiver_input", on_change=handle_chat, args=("caregiver",), placeholder="Ask about trends or support tips...")


