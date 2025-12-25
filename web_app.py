import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Health Bridge", page_icon="🧠", layout="wide")

# --- LOGIN ---
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

# --- CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- COLOR ENGINE ---
def get_live_color(score):
    val = (score - 1) / 9.0
    if val < 0.5:
        r, g, b = int(128 * (1 - val * 2)), 0, int(128 + (127 * val * 2))
    else:
        adj_val = (val - 0.5) * 2
        r, g, b = 0, int(255 * adj_val), int(255 * (1 - adj_val))
    emojis = {1:"😫", 2:"😖", 3:"🙁", 4:"☹️", 5:"😐", 6:"🙂", 7:"😊", 8:"😁", 9:"😆", 10:"🤩"}
    return f"rgb({r}, {g}, {b})", emojis.get(score, "😶")

# --- NAVIGATION ---
role = st.sidebar.radio("Role:", ["Patient Portal", "Caregiver Coach"])

if role == "Patient Portal":
    st.title("👋 Patient Portal")
    score = st.select_slider("Energy Level:", options=range(1, 11), value=5)
    rgb, emo = get_live_color(score)
    
    st.markdown(f'<div style="margin:auto; width:120px; height:120px; background-color:{rgb}; border-radius:50%; display:flex; justify-content:center; align-items:center; border:5px solid white; box-shadow: 0 10px 20px {rgb}66;"><span style="font-size:60px;">{emo}</span></div>', unsafe_allow_html=True)
    
    if st.button("Save Entry", use_container_width=True):
        df = conn.read(ttl=0)
        new_data = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score}])
        updated_df = pd.concat([df, new_data], ignore_index=True)
        conn.update(data=updated_df)
        st.success("Saved to Google Sheets!")

else:
    st.title("👩‍⚕️ Caregiver Coach")
    df = conn.read(ttl="1m")
    if not df.empty:
        last_score = int(df.iloc[-1]['Energy'])
        st.metric("Patient Energy", f"{last_score}/10")
        st.line_chart(df.set_index("Date"))
    else:
        st.info("No data yet.")
    
    # AI Assistant for Caregiver
    msg = st.text_input("Ask AI for advice:")
    if msg:
        chat = client.chat.completions.create(messages=[{"role":"user","content":msg}], model="llama-3.3-70b-versatile")
        st.write(chat.choices[0].message.content)
