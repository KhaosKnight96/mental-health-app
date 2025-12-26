import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & CSS FIX ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# This CSS forces high visibility and restores the sidebar look
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: white; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: white !important; }
    
    /* Action Card Style */
    .action-card {
        background: #1E293B;
        padding: 25px;
        border-radius: 15px;
        border: 2px solid #38BDF8;
        text-align: center;
        margin-bottom: 20px;
    }
    
    /* Login Box */
    .login-box {
        background: #1E293B;
        padding: 40px;
        border-radius: 20px;
        border: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

# --- 2. AUTHENTICATION ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.title("🧠 Health Bridge Login")
        u = st.text_input("Couple ID")
        p = st.text_input("Password", type="password")
        if st.button("Enter Portal", use_container_width=True, type="primary"):
            # Note: Ensure your 'Users' sheet has Username, Password, Fullname columns
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                udf = conn.read(worksheet="Users", ttl=0)
                udf.columns = [str(c).strip().title() for c in udf.columns]
                m = udf[(udf['Username'].astype(str)==u) & (udf['Password'].astype(str)==p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "cid": u, "name": m.iloc[0]['Fullname']})
                    st.rerun()
                else: st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Connection Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 3. ROLE SELECTION (POST-LOGIN) ---
if st.session_state.auth["role"] is None:
    st.title(f"Welcome, {st.session_state.auth['name']}")
    st.write("Please select your role for this session:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="action-card"><h2>👤 Patient</h2><p>Access Cooper & Zen Zone</p></div>', unsafe_allow_html=True)
        if st.button("I am the Patient", use_container_width=True):
            st.session_state.auth["role"] = "patient"
            st.rerun()
    with col2:
        st.markdown('<div class="action-card"><h2>👩‍⚕️ Caregiver</h2><p>Access Clara & Analytics</p></div>', unsafe_allow_html=True)
        if st.button("I am the Caregiver", use_container_width=True):
            st.session_state.auth["role"] = "caregiver"
            st.rerun()
    st.stop()

# --- 4. NAVIGATION & SIDEBAR (RESTORED ZEN ZONE) ---
role = st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"User: **{st.session_state.auth['name']}**")
    st.caption(f"Role: {role.title()}")
    st.divider()

    # Define Menu based on Role
    if role == "patient":
        main_menu = ["Patient Dashboard"]
        zen_zone = ["Memory Match", "Breathing Space", "Snake"]
    else:
        main_menu = ["Caregiver Command", "Admin Panel"]
        zen_zone = ["Breathing Space"] # Caregivers might just want a break!

    mode = st.radio("Main Menu", main_menu)
    st.write("##")
    st.subheader("🧩 Zen Zone")
    game_choice = st.selectbox("Choose a Game", ["--- Select ---"] + zen_zone)
    
    if game_choice != "--- Select ---":
        mode = game_choice

    st.divider()
    if st.button("Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

# --- 5. PAGE CONTENT ---

if mode == "Patient Dashboard":
    st.title("👋 Patient Portal")
    st.info("Your Energy Tracker and Cooper AI will appear here.")
    # Add your energy slider and Cooper chat logic here

elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Caregiver Command")
    st.info("Patient history and Clara AI will appear here.")

elif mode == "Memory Match":
    st.title("🧩 3D Memory Match")
    # THE 3D GAME LOGIC
    memory_js = """
    <div id='mem-game' style='display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px;'></div>
    <script>
    // 3D Game JS with 1s delay logic here...
    </script>
    """
    st.components.v1.html("Memory Game Rendering...", height=400)

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    st.write("Use arrow keys to play.")
