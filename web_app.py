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
</style>
""", unsafe_allow_html=True)

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = [] # Cooper
if "clara_history" not in st.session_state: st.session_state.clara_history = [] # Clara

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

# --- 4. SIDEBAR ---
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
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False, "role": None}; st.rerun()

# --- 5. PAGE CONTENT ---

# --- PATIENT: COOPER AI ---
if mode == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        score_text = st.select_slider("Current Vibe:", options=["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"], value="Steady")
        val_map = {"Resting":1, "Low":3, "Steady":5, "Good":7, "Active":9, "Vibrant":10, "Radiant":11}
        if st.button("Log My Energy", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val_map[score_text], "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
            st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Chat with Cooper</h3></div>', unsafe_allow_html=True)
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        
        p_in = st.chat_input("Tell Cooper how you're feeling...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper, a warm, supportive health companion for {cname}. Use gentle, encouraging language."}] + \
                   [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res})
            st.rerun()

# --- CAREGIVER: CLARA AI & GRAPHS ---
elif mode == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown('<div class="portal-card"><h4>Energy History</h4>', unsafe_allow_html=True)
                st.line_chart(f_data.set_index("Date")['Energy'])
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="portal-card"><h4>Recent Entries</h4>', unsafe_allow_html=True)
                st.dataframe(f_data.tail(5)[['Date', 'Energy']], hide_index=True)
                st.markdown('</div>', unsafe_allow_html=True)
    except: st.info("Waiting for first energy log...")

    st.divider()
    st.write("### 🧠 Consult Clara Intelligence")
    for m in st.session_state.clara_history:
        with st.chat_message(m["role"]): st.write(m["content"])
        
    c_in = st.chat_input("Ask Clara for a health analysis...")
    if c_in:
        prompt = f"You are Clara, a medical data analyst. Analyze this history for {cname}: {f_data.tail(10).to_string()}"
        msgs = [{"role":"system", "content": prompt}] + st.session_state.clara_history[-4:] + [{"role": "user", "content": c_in}]
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
        st.session_state.clara_history.append({"role": "user", "content": c_in})
        st.session_state.clara_history.append({"role": "assistant", "content": res})
        st.rerun()

# --- GAMES ---
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
                    }, 1000); // 1-second memory pause
                }
            }
        };
        container.appendChild(card);
    });
    </script>
    """
    st.components.v1.html(memory_html, height=600)
