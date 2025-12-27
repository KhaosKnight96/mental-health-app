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

# --- 2. AUTHENTICATION & ROLE SELECTION ---
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

if st.session_state.auth["role"] is None:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown(f"<h2 style='text-align:center;'>Welcome, {st.session_state.auth['name']}</h2>", unsafe_allow_html=True)
        choice = st.radio("Choose your portal:", ["👤 Patient", "👩‍⚕️ Caregiver"], horizontal=True)
        if st.button("Enter Dashboard →", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "patient" if "Patient" in choice else "caregiver"
            st.rerun()
    st.stop()

# --- 3. SIDEBAR ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"Logged in: **{cname}**")
    if role == "patient":
        mode = st.radio("Navigation", ["Dashboard"])
    else:
        mode = st.radio("Navigation", ["Analytics"])
    
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["--- Home ---", "Memory Match"])
        if game_choice != "--- Home ---": mode = game_choice

    st.divider()
    if st.button("🔄 Switch Role"): st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False}; st.rerun()

# --- 4. PAGE LOGIC ---

if mode == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        score = st.select_slider("Vibe:", options=["Resting", "Steady", "Vibrant"], value="Steady")
        if st.button("Log Energy"): st.balloons()
    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3></div>', unsafe_allow_html=True)
        # Cooper Chat Logic Here

elif mode == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown('<div class="portal-card"><h4>Energy Trends</h4>', unsafe_allow_html=True)
                st.line_chart(f_data.set_index("Date")['Energy'])
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="portal-card"><h4>Recent Logs</h4>', unsafe_allow_html=True)
                st.dataframe(f_data.tail(5)[['Date', 'Energy']], hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
    except: st.info("No data found yet.")

elif mode == "Memory Match":
    st.title("🧩 3D Memory Match")
    
    memory_html = """
    <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:12px; perspective: 1000px; padding: 20px;"></div>
    <script>
    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let shuffled = icons.sort(() => Math.random() - 0.5);
    let flipped = []; let matched = []; let canFlip = true;
    const container = document.getElementById('game-ui');
    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.style = "width: 80px; height: 110px; cursor: pointer;";
        card.innerHTML = `
            <div class="card-inner" id="card-${i}" style="width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative;">
                <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 12px; background: #219EBC; color: white; border: 2px solid white;">?</div>
                <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 32px; border-radius: 12px; background: white; transform: rotateY(180deg); border: 2px solid #219EBC;">${icon}</div>
            </div>`;
        card.onclick = () => {
            if (!canFlip || flipped.includes(i) || matched.includes(i)) return;
            document.getElementById(`card-${i}`).style.transform = "rotateY(180deg)";
            flipped.push({i, icon});
            if (flipped.length === 2) {
                canFlip = false;
                if (flipped[0].icon === flipped[1].icon) {
                    matched.push(flipped[0].i, flipped[1].i);
                    flipped = []; canFlip = true;
                } else {
                    setTimeout(() => {
                        document.getElementById(`card-${flipped[0].i}`).style.transform = "rotateY(0deg)";
                        document.getElementById(`card-${flipped[1].i}`).style.transform = "rotateY(0deg)";
                        flipped = []; canFlip = true;
                    }, 1000);
                }
            }
        };
        container.appendChild(card);
    });
    </script>
    """
    st.components.v1.html(memory_html, height=600)
