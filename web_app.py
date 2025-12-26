import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CSS ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: white; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; }
    .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: white !important; }
    .action-card {
        background: #1E293B; padding: 25px; border-radius: 15px;
        border: 2px solid #38BDF8; text-align: center; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# State Management
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. AUTHENTICATION ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🧠 Health Bridge Login")
        u_l = st.text_input("Couple ID")
        p_l = st.text_input("Password", type="password")
        if st.button("Enter Portal", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials")
    st.stop()

# --- 3. ROLE SELECTION SCREEN ---
if st.session_state.auth["role"] is None:
    st.title(f"Welcome, {st.session_state.auth['name']}")
    st.write("Please select your mode:")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="action-card"><h2>👤 Patient</h2></div>', unsafe_allow_html=True)
        if st.button("Enter Patient Portal", use_container_width=True):
            st.session_state.auth["role"] = "patient"; st.rerun()
    with c2:
        st.markdown('<div class="action-card"><h2>👩‍⚕️ Caregiver</h2></div>', unsafe_allow_html=True)
        if st.button("Enter Caregiver Command", use_container_width=True):
            st.session_state.auth["role"] = "caregiver"; st.rerun()
    st.stop()

# --- 4. SIDEBAR NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"**{cname}** ({role.title()})")
    
    # NAVIGATION
    if role == "patient":
        mode = st.radio("Go to:", ["Patient Portal", "Zen Zone"])
    else:
        mode = st.radio("Go to:", ["Caregiver Command", "Zen Zone"])
    
    st.divider()
    if st.button("🔄 Switch Role", use_container_width=True):
        st.session_state.auth["role"] = None; st.rerun()
        
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
        st.rerun()

# --- 5. PAGE LOGIC ---

# ZEN ZONE SUB-MENU
if mode == "Zen Zone":
    st.title("🧩 Zen Zone")
    game = st.selectbox("Choose a Break:", ["Memory Match", "Snake", "Breathing Space"])
    
    if game == "Memory Match":
        st.info("3D Memory Match Loading...")
        # (Insert your 3D JS Memory Match here)
        
    elif game == "Snake":
        st.info("Snake Loading...")
        # (Insert your Snake HTML here)

# PATIENT PORTAL (COOPER AI)
elif mode == "Patient Portal":
    st.title("👋 Cooper Support")
    score = st.select_slider("Energy (1-11)", options=range(1,12), value=6)
    
    if st.button("Save Daily Score", use_container_width=True):
        df = conn.read(worksheet="Sheet1", ttl=0)
        new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": score, "CoupleID": cid}])
        conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
        st.success("Entry Saved!")

    st.divider()
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    
    p_in = st.chat_input("Message Cooper...")
    if p_in:
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        msgs = [{"role":"system","content":f"You are Cooper for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

# CAREGIVER COMMAND (CLARA AI)
elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    try:
        all_d = conn.read(worksheet="Sheet1", ttl=0)
        f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
    except: pass

    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
        
    c_in = st.chat_input("Ask Clara...")
    if c_in:
        prompt = f"You are Clara for {cname}. Data: {f_data.tail(5).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res}); st.rerun()
