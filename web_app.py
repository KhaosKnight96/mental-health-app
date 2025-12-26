import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & FORCED THEME ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# This CSS forces a dark, high-contrast theme to prevent "white-out"
st.markdown("""
<style>
    /* Force Background and Text Colors */
    .stApp {
        background-color: #0F172A !important;
        color: #F8FAFC !important;
    }
    
    /* High-Contrast Login Box */
    .login-box {
        background: rgba(30, 41, 59, 0.7);
        padding: 3rem;
        border-radius: 20px;
        border: 1px solid #334155;
        backdrop-filter: blur(10px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }
    
    /* Action Cards for Role Selection and Portals */
    .action-card {
        background: #1E293B;
        padding: 2rem;
        border-radius: 15px;
        border: 2px solid #334155;
        text-align: center;
        transition: transform 0.3s ease;
    }
    .action-card:hover {
        border-color: #38BDF8;
        transform: translateY(-5px);
    }

    /* Fix for standard Streamlit text visibility */
    h1, h2, h3, p, span, label {
        color: #F8FAFC !important;
    }
    
    /* Button Styling */
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None, "view": "login"}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

# Connections
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGIN PAGE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.write("##") 
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.title("🧠 Health Bridge")
        st.write("Secure Clinical Access")
        
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({
                    "logged_in": True, "cid": u_l, 
                    "name": m.iloc[0]['Fullname'], "view": "role_selection"
                })
                st.rerun()
            else:
                st.error("Invalid Credentials")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 3. POST-LOGIN ROLE SELECTION ---
if st.session_state.auth["view"] == "role_selection":
    st.write("##")
    st.markdown(f"<h1 style='text-align: center;'>Welcome, {st.session_state.auth['name']}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem;'>Which dashboard would you like to access today?</p>", unsafe_allow_html=True)
    st.write("##")
    
    c1, c2, c3, c4 = st.columns([0.5, 2, 2, 0.5])
    with c2:
        st.markdown('<div class="action-card"><h2>👤 Patient</h2><p>Chat with Cooper and log daily energy.</p></div>', unsafe_allow_html=True)
        if st.button("Enter Patient Portal", use_container_width=True):
            st.session_state.auth.update({"role": "patient", "view": "dashboard"})
            st.rerun()
    with c3:
        st.markdown('<div class="action-card"><h2>👩‍⚕️ Caregiver</h2><p>View Clara analytics and patient history.</p></div>', unsafe_allow_html=True)
        if st.button("Enter Caregiver Command", use_container_width=True):
            st.session_state.auth.update({"role": "caregiver", "view": "dashboard"})
            st.rerun()
    st.stop()

# --- 4. DASHBOARD & GAMES ---
role = st.session_state.auth["role"]

with st.sidebar:
    st.title("🏠 Health Bridge")
    st.write(f"User: **{st.session_state.auth['name']}**")
    st.caption(f"Mode: {role.capitalize()}")
    st.divider()
    
    # Simple nav based on role
    if role == "patient":
        mode = st.radio("Navigation", ["Patient Portal", "Memory Match", "Snake", "Breathing Space"])
    else:
        mode = st.radio("Navigation", ["Caregiver Command", "Admin Panel"])
        
    if st.button("Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- GAME LOGIC (3D Memory Match Example) ---
if mode == "Memory Match":
    st.title("🧩 Memory Match")
    st.write("Pairs will stay visible for 1 second if they don't match.")
    # Insert the 3D Javascript Logic here...
    
elif mode == "Patient Portal":
    st.title("👋 Cooper Support")
    # Insert Energy Slider and Chat Logic here...
