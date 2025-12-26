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
    /* Global Theme */
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    
    /* Role Card Styling */
    .role-card {
        background: #1E293B;
        padding: 3rem;
        border-radius: 24px;
        border: 2px solid #334155;
        text-align: center;
        transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }
    .role-card:hover {
        border-color: #38BDF8;
        transform: translateY(-8px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }
    
    /* Standard Portal Card */
    .portal-card {
        background: rgba(30, 41, 59, 0.7);
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #38BDF8;
        margin-bottom: 1rem;
    }

    /* Text Color Fixes */
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stSelectbox label { color: #F8FAFC !important; }
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
            else: st.error("Access Denied: Check ID/Password")
    st.stop()

# --- 3. BEAUTIFIED ROLE SELECTION ---
if st.session_state.auth["role"] is None:
    st.write("##")
    st.markdown(f"<h1 style='text-align: center; font-size: 3rem;'>Welcome, {st.session_state.auth['name']}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; opacity: 0.8;'>Choose your perspective for this session</p>", unsafe_allow_html=True)
    st.write("##")
    
    c1, c2, c3 = st.columns([1, 4, 1])
    with c2:
        sub1, sub2 = st.columns(2)
        with sub1:
            st.markdown('<div class="role-card"><h1>👤</h1><h2>Patient</h2><p>View support and energy logs</p></div>', unsafe_allow_html=True)
            if st.button("Enter as Patient", use_container_width=True):
                st.session_state.auth["role"] = "patient"; st.rerun()
        with sub2:
            st.markdown('<div class="role-card"><h1>👩‍⚕️</h1><h2>Caregiver</h2><p>Analyze data and trends</p></div>', unsafe_allow_html=True)
            if st.button("Enter as Caregiver", use_container_width=True):
                st.session_state.auth["role"] = "caregiver"; st.rerun()
    st.stop()

# --- 4. SIDEBAR NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"**{cname}**")
    
    # Primary Navigation
    if role == "patient":
        mode = st.radio("Main Menu", ["Dashboard", "Zen Zone"])
    else:
        mode = st.radio("Main Menu", ["Analytics Center", "Zen Zone"])

    st.write("##")
    # Quick Action Buttons
    if st.button("🔄 Switch Mode", use_container_width=True):
        st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

# --- 5. PAGE CONTENT ---

if mode == "Dashboard":
    st.title("👋 Cooper Support")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown('<div class="portal-card"><h3>Energy Check</h3></div>', unsafe_allow_html=True)
        score = st.select_slider("How are you feeling?", options=range(1,12), value=6)
        if st.button("Save Entry", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
            st.success("Logged!")

    with col2:
        for m in st.session_state.chat_log:
            with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        
        p_in = st.chat_input("Message Cooper...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

elif mode == "Analytics Center":
    st.title("👩‍⚕️ Clara Command")
    try:
        all_d = conn.read(worksheet="Sheet1", ttl=0)
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty: 
            st.markdown('<div class="portal-card"><h3>Patient Energy Trends</h3></div>', unsafe_allow_html=True)
            st.line_chart(f_data.set_index("Date")['Energy'])
    except: st.info("No data available yet.")

    st.divider()
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
        
    c_in = st.chat_input("Consult Clara...")
    if c_in:
        prompt = f"You are Clara. Data: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res}); st.rerun()

elif mode == "Zen Zone":
    st.title("🧩 Zen Zone")
    game = st.selectbox("Select Activity", ["Memory Match", "Snake", "Breathing Space"])
    
    if game == "Memory Match":
        # Insert the 3D Javascript code here (as per your building block)
        st.info("Launch 3D Memory Card Game...")
    elif game == "Snake":
        st.info("Launch Snake Arcade...")
