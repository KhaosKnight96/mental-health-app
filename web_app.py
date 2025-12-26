import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & THEME LOCK ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# Custom CSS for high-contrast visibility and "App" aesthetics
st.markdown("""
<style>
    /* Force high-contrast background */
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    
    /* Portal Cards */
    .portal-card {
        background: #1E293B;
        padding: 2rem;
        border-radius: 20px;
        border: 1px solid #334155;
        text-align: center;
        transition: 0.3s;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    .portal-card:hover { border-color: #38BDF8; transform: translateY(-5px); }

    /* Text Overrides */
    h1, h2, h3, p, label, .stSelectbox label { color: #F8FAFC !important; }
    
    /* Button Aesthetics */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: 0.2s !important;
    }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGIN FLOW ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.write("##")
        st.markdown('<div class="portal-card">', unsafe_allow_html=True)
        st.title("🧠 Health Bridge")
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        
        if st.button("Enter Portal", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 3. DEDICATED ROLE SELECTION SCREEN ---
if st.session_state.auth["role"] is None:
    st.markdown(f"<h1 style='text-align:center;'>Welcome back, {st.session_state.auth['name']}</h1>", unsafe_allow_html=True)
    st.write("##")
    c1, c2, c3 = st.columns([1, 4, 1])
    with c2:
        sub1, sub2 = st.columns(2)
        with sub1:
            st.markdown('<div class="portal-card"><h2>👤 Patient</h2><p>Chat with Cooper & Zen Zone</p></div>', unsafe_allow_html=True)
            if st.button("Access Patient Portal", use_container_width=True):
                st.session_state.auth["role"] = "patient"; st.rerun()
        with sub2:
            st.markdown('<div class="portal-card"><h2>👩‍⚕️ Caregiver</h2><p>Health Analytics & Clara</p></div>', unsafe_allow_html=True)
            if st.button("Access Caregiver Command", use_container_width=True):
                st.session_state.auth["role"] = "caregiver"; st.rerun()
    st.stop()

# --- 4. SIDEBAR (Role Switcher, Zen Zone, Logout) ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"Logged in: **{cname}**")
    st.caption(f"Current View: {role.title()}")
    st.divider()

    # Dynamic Navigation
    if role == "patient":
        mode = st.radio("Navigation", ["Patient Dashboard"])
    else:
        mode = st.radio("Navigation", ["Caregiver Analytics", "Admin Oversight"])

    # Zen Zone Grouping
    st.write("##")
    with st.expander("🧩 Zen Zone (Games)", expanded=False):
        game_choice = st.selectbox("Select Activity", ["--- Choose ---", "Memory Match", "Snake", "Breathing Space"])
        if game_choice != "--- Choose ---":
            mode = game_choice

    st.spacer = st.container() # Push buttons to bottom
    st.write("##")
    if st.button("🔄 Switch Role", use_container_width=True):
        st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

# --- 5. PAGE CONTENT ---

if mode == "Patient Dashboard":
    st.title("👋 Patient Portal")
    # Insert Energy Slider and Cooper AI logic here

elif mode == "Caregiver Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    # Insert Clara AI and Graph logic here

elif mode == "Memory Match":
    st.title("🧩 Memory Match")
    # (Your 3D JavaScript logic from earlier code goes here)

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    # (Your Snake HTML logic from earlier code goes here)
