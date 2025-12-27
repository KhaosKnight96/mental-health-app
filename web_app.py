import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & APP-WIDE STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide", initial_sidebar_state="expanded")

# This CSS forces a deep-slate theme and styles the custom cards
st.markdown("""
<style>
    /* Force Background and Text Contrast */
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    
    /* Clean Cards for Patient/Caregiver Panels */
    .portal-card {
        background: #1E293B;
        padding: 25px;
        border-radius: 20px;
        border: 1px solid #334155;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    
    /* Typography Fixes */
    h1, h2, h3, p, label, .stMarkdown { color: #F8FAFC !important; }
    .stSelectbox label, .stRadio label { color: #F8FAFC !important; font-weight: 600 !important; }

    /* Button Styling */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        transition: 0.3s ease !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

# Connections
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error("Connection error. Please check your Secrets/Credentials.")

# --- 2. LOGIN PAGE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.write("##")
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        st.write("### Welcome Back")
        u_l = st.text_input("Couple ID", key="l_u", placeholder="Enter your ID")
        p_l = st.text_input("Password", type="password", key="l_p", placeholder="••••••••")
        
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else:
                st.error("Access Denied: Check ID or Password")
    st.stop()

# --- 3. BULLETPROOF ROLE SELECTION ---
if st.session_state.auth["role"] is None:
    st.write("##")
    st.markdown(f"<h1 style='text-align: center;'>Hello, {st.session_state.auth['name']}</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 1.2rem; opacity: 0.8;'>Which portal would you like to enter?</p>", unsafe_allow_html=True)
    st.write("##")

    _, col, _ = st.columns([1, 2, 1])
    with col:
        # Styled Selection Box
        choice = st.radio(
            "I am entering as:",
            ["👤 Patient", "👩‍⚕️ Caregiver"],
            horizontal=True,
            index=0
        )
        
        st.divider()
        if "Patient" in choice:
            st.markdown("""<div style='background:#263345; padding:20px; border-radius:15px; border-left: 4px solid #38BDF8;'>
            <b>Patient Portal:</b> Track your energy, chat with Cooper, and access the Zen Zone.</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""<div style='background:#263345; padding:20px; border-radius:15px; border-left: 4px solid #FB8500;'>
            <b>Caregiver Command:</b> Analyze trends with Clara and view patient logs.</div>""", unsafe_allow_html=True)
        
        st.write("##")
        if st.button("Enter Dashboard →", use_container_width=True, type="primary"):
            st.session_state.auth["role"] = "patient" if "Patient" in choice else "caregiver"
            st.rerun()
    st.stop()

# --- 4. NAVIGATION & SIDEBAR ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"Logged in: **{cname}**")
    st.caption(f"Mode: {role.title()}")
    st.divider()

    # Define Navigation
    if role == "patient":
        mode = st.radio("Navigation", ["Dashboard"])
    else:
        mode = st.radio("Navigation", ["Analytics"])

    # Zen Zone Grouping
    st.write("##")
    with st.expander("🧩 Zen Zone (Games)", expanded=False):
        game_choice = st.selectbox("Select Break", ["--- Home ---", "Memory Match", "Snake", "Breathing Space"])
        if game_choice != "--- Home ---":
            mode = game_choice

    st.divider()
    if st.button("🔄 Switch Role", use_container_width=True):
        st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "role": None}
        st.rerun()

# --- 5. PAGE CONTENT ---

# --- PATIENT VIEW ---
if mode == "Dashboard":
    st.markdown(f"""
        <div style="background: linear-gradient(90deg, #219EBC 0%, #023047 100%); padding: 30px; border-radius: 20px; margin-bottom: 25px;">
            <h1 style="margin:0; color: white !important;">Good day, {cname}! ☀️</h1>
            <p style="margin:0; color: #E0FBFC !important; opacity: 0.9;">Cooper is here to support you.</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 2], gap="large")
    with col1:
        st.markdown('<div class="portal-card"><h3>✨ Energy Check-in</h3>', unsafe_allow_html=True)
        score_text = st.select_slider("How is your vibe?", 
                                      options=["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"], 
                                      value="Steady")
        val_map = {"Resting":1, "Low":3, "Steady":5, "Good":7, "Active":9, "Vibrant":10, "Radiant":11}
        
        if st.button("Log Energy", use_container_width=True, type="primary"):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val_map[score_text], "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
            st.balloons()
            st.success("Noted!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Chat with Cooper</h3></div>', unsafe_allow_html=True)
        chat_box = st.container(height=400)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        
        p_in = st.chat_input("Tell Cooper how your day is going...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper, a warm, empathetic health companion for {cname}."}] + \
                   [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

# --- CAREGIVER VIEW ---
elif mode == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    try:
        all_d = conn.read(worksheet="Sheet1", ttl=0)
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty: 
            st.markdown('<div class="portal-card"><h3>Patient Energy Trends</h3></div>', unsafe_allow_html=True)
            st.line_chart(f_data.set_index("Date")['Energy'])
    except: st.info("No data available yet.")

    st.divider()
    st.markdown("### Consult Clara Intelligence")
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
        
    c_in = st.chat_input("Analyze patient history...")
    if c_in:
        prompt = f"You are Clara, a health data analyst. Analyze this history for {cname}: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res}); st.rerun()

# --- ZEN ZONE ---
elif mode == "Memory Match":
    st.title("🧩 Memory Match")
    # Paste your 3D JS logic here
    st.info("Launch 3D Game Component...")

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    st.info("Launch Snake Component...")
