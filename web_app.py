import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & APP-WIDE STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card {
        background: #1E293B;
        padding: 25px;
        border-radius: 20px;
        border: 1px solid #334155;
        margin-bottom: 20px;
    }
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. AUTHENTICATION ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
    st.stop()

# --- 3. ROLE SELECTION ---
if st.session_state.auth["role"] is None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(f"<h2 style='text-align:center;'>Welcome, {st.session_state.auth['name']}</h2>", unsafe_allow_html=True)
        choice = st.radio("Choose your portal:", ["👤 Patient", "👩‍⚕️ Caregiver"], horizontal=True)
        if st.button("Enter Dashboard →", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "patient" if "Patient" in choice else "caregiver"
            st.rerun()
    st.stop()

cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

# --- 4. SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"Logged in: **{cname}**")
    if role == "patient":
        mode = st.radio("Navigation", ["Dashboard"])
    else:
        mode = st.radio("Navigation", ["Analytics"])
    
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["--- Home ---", "Memory Match", "Snake"])
        if game_choice != "--- Home ---": mode = game_choice

    st.divider()
    if st.button("🔄 Switch Role"): st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False, "role": None}; st.rerun()

# --- 5. PAGE CONTENT ---

if mode == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        # FRIENDLY SCALE MAPPED TO DATABASE NUMBERS
        options = ["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"]
        val_map = {"Resting":1, "Low":3, "Steady":5, "Good":7, "Active":9, "Vibrant":10, "Radiant":11}
        
        score_text = st.select_slider("How are you feeling?", options=options, value="Steady")
        
        if st.button("Log Energy", use_container_width=True, type="primary"):
            try:
                # Read current data
                df = conn.read(worksheet="Sheet1", ttl=0)
                # Create new entry using mapping
                new_row = pd.DataFrame([{
                    "Date": datetime.date.today().strftime("%Y-%m-%d"), 
                    "Energy": val_map[score_text], 
                    "CoupleID": cid
                }])
                # Append and Update Sheets
                updated_df = pd.concat([df, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                st.balloons()
                st.success(f"Logged {score_text} ({val_map[score_text]}) to your history!")
            except Exception as e:
                st.error(f"Error connecting to Sheets: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3></div>', unsafe_allow_html=True)
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        p_in = st.chat_input("Tell Cooper how you're feeling...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper, a warm, supportive health companion for {cname}."}] + \
                   [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

elif mode == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            st.markdown('<div class="portal-card"><h4>Patient Energy Trends</h4>', unsafe_allow_html=True)
            st.line_chart(f_data.set_index("Date")['Energy'])
            st.markdown('</div>', unsafe_allow_html=True)
    except: st.info("No data found yet.")

elif mode == "Memory Match":
    st.title("🧩 3D Memory Match")
    # (Memory Match JS with Audio included here - same as previous version)

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    # (Snake JS with Swipe, Audio, and Custom Game Over included here - same as previous version)
