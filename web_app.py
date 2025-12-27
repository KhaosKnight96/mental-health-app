import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & THEME ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    /* Global Background */
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    
    /* Dedicated Role Button Cards */
    .role-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: #1E293B;
        padding: 40px;
        border-radius: 20px;
        border: 2px solid #334155;
        transition: 0.3s;
        margin-bottom: 20px;
    }
    .role-container:hover {
        border-color: #38BDF8;
        background: #263345;
    }
    
    /* Card Text */
    .role-icon { font-size: 50px; margin-bottom: 10px; }
    .role-title { font-size: 24px; font-weight: bold; color: #38BDF8 !important; }
    .role-desc { font-size: 16px; color: #94A3B8 !important; margin-bottom: 20px; }

    /* General UI */
    .portal-card {
        background: rgba(30, 41, 59, 0.7);
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #38BDF8;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGIN PAGE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.write("##")
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
            else: st.error("Access Denied")
    st.stop()

# --- 3. BEAUTIFIED ROLE SELECTION (Side-by-Side Hero Cards) ---
if st.session_state.auth["role"] is None:
    st.write("##")
    st.markdown(f"<h1 style='text-align: center; font-size: 2.5rem; color: white;'>Welcome, {st.session_state.auth['name']}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94A3B8; font-size: 1.1rem;'>Please select your portal to continue</p>", unsafe_allow_html=True)
    st.write("##")
    
    # CSS for the Side-by-Side Cards
    st.markdown("""
    <style>
        .role-card-container {
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px 20px;
            text-align: center;
            transition: all 0.3s ease;
            height: 320px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .role-card-container:hover {
            background: rgba(56, 189, 248, 0.1);
            border-color: #38BDF8;
            transform: translateY(-10px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        }
        .role-icon { font-size: 60px; margin-bottom: 20px; }
        .role-name { font-size: 24px; font-weight: 700; color: white !important; margin-bottom: 10px; }
        .role-text { font-size: 14px; color: #94A3B8 !important; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns([1, 3, 0.5, 3, 1])
    
    with col2:
        st.markdown("""
            <div class="role-card-container">
                <div class="role-icon">👤</div>
                <div class="role-name">Patient Portal</div>
                <div class="role-text">Log daily energy, chat with Cooper, and access the Zen Zone games.</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Access Patient View", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "patient"
            st.rerun()

    with col4:
        st.markdown("""
            <div class="role-card-container">
                <div class="role-icon">👩‍⚕️</div>
                <div class="role-name">Caregiver Command</div>
                <div class="role-text">Analyze health trends with Clara and monitor patient logs.</div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Access Caregiver View", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "caregiver"
            st.rerun()
            
    st.stop()
# --- 4. SIDEBAR NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"**{cname}**")
    
    # Unified Zen Zone Dropdown
    with st.expander("🧩 Zen Zone (Games)", expanded=False):
        game_select = st.selectbox("Choose Activity", ["--- Choose ---", "Memory Match", "Snake", "Breathing Space"])
    
    st.divider()
    # If a game is selected, it overrides the dashboard view
    if game_select != "--- Choose ---":
        mode = game_select
    else:
        mode = "Dashboard" if role == "patient" else "Analytics"

    # Bottom Actions
    if st.button("🔄 Switch Mode", use_container_width=True):
        st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

# --- 5. DASHBOARD LOGIC (COOPER, CLARA, & GRAPHS) ---

if mode == "Dashboard":
    st.title("👋 Cooper Patient Portal")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>Energy Check</h3></div>', unsafe_allow_html=True)
        score = st.select_slider("Energy (1-11)", options=range(1,12), value=6)
        if st.button("Log Energy", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
            st.success("Saved!")
    with col2:
        for m in st.session_state.chat_log:
            with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        p_in = st.chat_input("Message Cooper...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

elif mode == "Analytics":
    st.title("👩‍⚕️ Clara Caregiver Command")
    try:
        all_d = conn.read(worksheet="Sheet1", ttl=0)
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty: 
            st.markdown('<div class="portal-card"><h3>Health History</h3></div>', unsafe_allow_html=True)
            st.line_chart(f_data.set_index("Date")['Energy'])
    except: pass
    
    st.divider()
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
    c_in = st.chat_input("Ask Clara...")
    if c_in:
        prompt = f"You are Clara. Data: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res}); st.rerun()

# Zen Zone Placeholders
elif mode == "Memory Match":
    st.title("🧩 Memory Match")
    st.info("The 3D memory game logic is ready to be pasted here.")

