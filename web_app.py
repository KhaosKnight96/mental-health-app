import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for "App-like" Buttons and UI
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 12px; height: 3em; transition: all 0.3s; border: none; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    /* Portal Card Styles */
    .portal-card {
        background: white; padding: 25px; border-radius: 20px;
        border-left: 8px solid #219EBC; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .action-btn {
        background-color: #219EBC !important; color: white !important;
        font-weight: bold !important; width: 100%; border-radius: 15px !important;
    }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. LOGIC FUNCTIONS ---
def log_to_master(cid, user_type, speaker, message):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        df_logs = conn.read(worksheet="ChatLogs", ttl=0)
        new_entry = pd.DataFrame([{"Timestamp": now, "CoupleID": cid, "UserType": user_type, "Speaker": speaker, "Message": message}])
        conn.update(worksheet="ChatLogs", data=pd.concat([df_logs, new_entry], ignore_index=True))
    except: pass

# --- 3. LOGIN WITH ROLE SELECTION ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    
    with t1:
        u_l = st.text_input("Couple ID")
        p_l = st.text_input("Password", type="password")
        role_l = st.selectbox("I am the:", ["Patient", "Caregiver"])
        
        if st.button("Enter Dashboard", use_container_width=True):
            udf = conn.read(worksheet="Users", ttl=0)
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname'], "role": role_l}
                st.rerun()
            else: st.error("Invalid credentials")
    with t2:
        st.info("Please contact your provider to register a new Couple ID.")
    st.stop()

# --- 4. NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.markdown(f"### 🏠 {cname}")
    st.markdown(f"**Role:** {role}")
    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 5. PORTALS ---

# PATIENT PORTAL
if role == "Patient":
    st.title(f"☀️ Welcome back, {cname.split()[0]}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="portal-card"><h3>How is your energy?</h3><p>Slide to record your daily level.</p></div>', unsafe_allow_html=True)
        energy = st.select_slider("Select 1-11", options=range(1,12), value=6)
        if st.button("Submit Daily Energy", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": energy, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new], ignore_index=True))
            st.success("Energy Recorded!")

    with col2:
        st.markdown('<div class="portal-card"><h3>Zen Zone</h3><p>Take a quick brain break with a game.</p></div>', unsafe_allow_html=True)
        game_sel = st.selectbox("Choose Activity", ["--- Select ---", "Memory Match", "Snake", "Breathing Space"])

    st.divider()
    st.subheader("💬 Chat with Cooper")
    for m in st.session_state.chat_log:
        with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
    
    p_in = st.chat_input("Talk to Cooper...")
    if p_in:
        st.session_state.chat_log.append({"type": "P", "msg": p_in})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}] + [{"role":"user","content":p_in}]).choices[0].message.content
        st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

# CAREGIVER PORTAL
elif role == "Caregiver":
    st.title("👩‍⚕️ Caregiver Command")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>Quick Actions</h3></div>', unsafe_allow_html=True)
        if st.button("📈 View Trends", use_container_width=True): st.toast("Loading Trends...")
        if st.button("🧩 Try Zen Games", use_container_width=True): st.info("Select a game from the Zen Zone below.")
        game_sel = st.selectbox("Zen Zone", ["--- Select ---", "Memory Match", "Snake", "Breathing Space"])

    with col2:
        st.markdown('<div class="portal-card"><h3>Energy History</h3></div>', unsafe_allow_html=True)
        try:
            all_d = conn.read(worksheet="Sheet1", ttl=0)
            f_data = all_d[all_d['CoupleID'].astype(str) == str(cid)]
            if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
        except: st.write("No data yet.")

    st.divider()
    st.subheader("🤖 Clara Analyst")
    c_in = st.chat_input("Ask Clara about the latest data...")
    if c_in:
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":c_in}]).choices[0].message.content
        st.session_state.clara_history.append({"role":"user", "content":c_in})
        st.session_state.clara_history.append({"role":"assistant", "content":res})
        st.rerun()

# --- 6. GAMES LOGIC ---
if "game_sel" in locals() and game_sel == "Memory Match":
    st.subheader("🧩 3D Memory Match")
    
    memory_html = """
    <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:10px; perspective: 1000px;"></div>
    <script>
    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let shuffled = icons.sort(() => Math.random() - 0.5);
    let flipped = [];
    let matched = [];
    let canFlip = true;

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSound(f, d) {
        let o = audioCtx.createOscillator(); let g = audioCtx.createGain();
        o.frequency.value = f; g.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + d);
        o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + d);
    }

    const container = document.getElementById('game-ui');
    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.innerHTML = `
            <div class="card-inner" id="card-${i}">
                <div class="card-front">❓</div>
                <div class="card-back">${icon}</div>
            </div>`;
        card.className = 'card';
        card.onclick = () => flipCard(i, icon);
        container.appendChild(card);
    });

    function flipCard(i, icon) {
        if (!canFlip || flipped.includes(i) || matched.includes(i)) return;
        
        document.getElementById(`card-${i}`).style.transform = "rotateY(180deg)";
        flipped.push({i, icon});
        playSound(400, 0.1);

        if (flipped.length === 2) {
            canFlip = false;
            if (flipped[0].icon === flipped[1].icon) {
                matched.push(flipped[0].i, flipped[1].i);
                setTimeout(() => { playSound(800, 0.3); canFlip = True; }, 300);
                flipped = [];
                canFlip = true;
            } else {
                setTimeout(() => {
                    document.getElementById(`card-${flipped[0].i}`).style.transform = "rotateY(0deg)";
                    document.getElementById(`card-${flipped[1].i}`).style.transform = "rotateY(0deg)";
                    playSound(200, 0.2);
                    flipped = [];
                    canFlip = true;
                }, 1000);
            }
        }
    }
    </script>
    <style>
    .card { width: 70px; height: 90px; cursor: pointer; }
    .card-inner { width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative; }
    .card-front, .card-back { position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border: 2px solid white; }
    .card-front { background: linear-gradient(135deg, #219EBC, #023047); color: white; }
    .card-back { background: white; transform: rotateY(180deg); }
    </style>
    """
    st.components.v1.html(memory_html, height=500)

elif "game_sel" in locals() and game_sel == "Snake":
    # (Previous Snake code goes here)
    st.info("Snake Game Loading...")
