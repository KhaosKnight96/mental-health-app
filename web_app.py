import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# Custom CSS for modern UI
st.markdown("""
<style>
    .stApp { background-color: #fcfcfc; }
    .portal-card {
        background: white; padding: 25px; border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 5px solid #219EBC;
        text-align: center; transition: transform 0.2s;
    }
    .portal-card:hover { transform: translateY(-5px); }
    .role-btn {
        background-color: #219EBC; color: white; padding: 20px;
        border-radius: 10px; cursor: pointer; text-align: center;
        font-weight: bold; margin: 10px; border: none; width: 100%;
    }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user", "needs_role": False}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- 2. HELPER FUNCTIONS ---
def log_to_master(cid, user_type, speaker, message):
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        df_logs = conn.read(worksheet="ChatLogs", ttl=0)
        new_entry = pd.DataFrame([{"Timestamp": now, "CoupleID": cid, "UserType": user_type, "Speaker": speaker, "Message": message}])
        conn.update(worksheet="ChatLogs", data=pd.concat([df_logs, new_entry], ignore_index=True))
    except: pass

def sync_nav():
    st.session_state.zen_nav = "--- Choose ---"

# --- 3. LOGIN & ROLE SELECTION ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    
    with t1:
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Verify Identity", use_container_width=True):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth.update({
                    "logged_in": True, "cid": u_l, 
                    "name": m.iloc[0]['Fullname'], "needs_role": True
                })
                st.rerun()
            else: st.error("Invalid credentials")
    with t2:
        st.info("New accounts must be authorized by your clinic.")
    st.stop()

# --- POST-LOGIN ROLE SELECTION ---
if st.session_state.auth["needs_role"]:
    st.title(f"Welcome, {st.session_state.auth['name']}")
    st.subheader("Please select your role for this session:")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👤 I am the PATIENT", use_container_width=True):
            st.session_state.auth["role"] = "patient"
            st.session_state.auth["needs_role"] = False
            st.rerun()
    with c2:
        if st.button("👩‍⚕️ I am the CAREGIVER", use_container_width=True):
            st.session_state.auth["role"] = "caregiver"
            st.session_state.auth["needs_role"] = False
            st.rerun()
    st.stop()

# --- 4. NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    st.write(f"Active Role: **{role.capitalize()}**")
    
    main_opts = ["Patient Portal", "Caregiver Command"]
    if role == "admin": main_opts.append("🛡️ Admin Panel")
    
    # Filter menu based on selection
    if role == "patient": main_opts = ["Patient Portal"]
    elif role == "caregiver": main_opts = ["Caregiver Command"]
    
    mode = st.radio("Go to:", main_opts, key="main_nav", on_change=sync_nav)
    st.divider()
    st.subheader("🧩 Zen Zone")
    game_choice = st.selectbox("Quick Break:", ["--- Choose ---", "Memory Match", "Breathing Space", "Snake"], key="zen_nav")
    
    if game_choice != "--- Choose ---": mode = game_choice

    st.divider()
    if st.button("Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": "user", "needs_role": False}
        st.rerun()

# --- 5. PORTAL LOGIC ---

if mode == "Patient Portal":
    st.title("👋 Cooper Support")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="portal-card"><h3>Daily Energy</h3><p>How are you feeling right now?</p></div>', unsafe_allow_html=True)
        score = st.select_slider("Level (1-11)", options=range(1,12), value=6)
        if st.button("Save Daily Score", use_container_width=True):
            st.success("Entry Saved!")
    with col2:
        st.markdown('<div class="portal-card"><h3>Cooper AI</h3><p>Chat with your assistant below.</p></div>', unsafe_allow_html=True)
    
    st.divider()
    # (Your existing Cooper Chat Logic goes here)

elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="portal-card"><h3>Vital Trends</h3><p>Review patient history.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>Clara AI</h3><p>Ask for medical log summaries below.</p></div>', unsafe_allow_html=True)
    
    st.divider()
    # (Your existing Clara Chat Logic goes here)

elif mode == "Memory Match":
    st.title("🧩 Zen Memory Match")
    st.write("Match the pairs. Mismatches will stay up for 1 second to help you memorize!")
    
    memory_html = """
    <div id="game-container" style="display:flex; justify-content:center; flex-wrap:wrap; gap:10px; perspective:1000px; padding:20px;"></div>
    <script>
    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let shuffled = icons.sort(() => Math.random() - 0.5);
    let flipped = []; let matched = []; let canFlip = true;
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playSnd(f, t, d) {
        let o = audioCtx.createOscillator(); let g = audioCtx.createGain();
        o.type = t; o.frequency.value = f; g.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + d);
        o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + d);
    }
    const container = document.getElementById('game-container');
    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.style = "width: 70px; height: 100px; cursor: pointer;";
        card.innerHTML = `<div class="inner" id="c-${i}" style="width:100%; height:100%; transition: transform 0.6s; transform-style:preserve-3d; position:relative;">
            <div style="position:absolute; width:100%; height:100%; backface-visibility:hidden; display:flex; align-items:center; justify-content:center; font-size:24px; border-radius:10px; background:#219EBC; color:white; border:2px solid white; box-shadow:0 4px 8px rgba(0,0,0,0.1);">?</div>
            <div style="position:absolute; width:100%; height:100%; backface-visibility:hidden; display:flex; align-items:center; justify-content:center; font-size:32px; border-radius:10px; background:white; transform:rotateY(180deg); border:2px solid #219EBC;">${icon}</div>
        </div>`;
        card.onclick = () => {
            if(!canFlip || flipped.includes(i) || matched.includes(i)) return;
            document.getElementById(`c-${i}`).style.transform = "rotateY(180deg)";
            flipped.push({i, icon}); playSnd(400, 'sine', 0.1);
            if(flipped.length === 2) {
                canFlip = false;
                if(flipped[0].icon === flipped[1].icon) {
                    matched.push(flipped[0].i, flipped[1].i);
                    setTimeout(() => { playSnd(600, 'sine', 0.3); canFlip = true; }, 300);
                    flipped = [];
                } else {
                    setTimeout(() => {
                        document.getElementById(`c-${flipped[0].i}`).style.transform = "rotateY(0deg)";
                        document.getElementById(`c-${flipped[1].i}`).style.transform = "rotateY(0deg)";
                        playSnd(150, 'sawtooth', 0.2);
                        flipped = []; canFlip = true;
                    }, 1000);
                }
            }
        };
        container.appendChild(card);
    });
    </script>
    """
    st.components.v1.html(memory_html, height=500)

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    # (Your existing Snake HTML with sound goes here)

elif mode == "Breathing Space":
    st.title("🌬️ Breathing Space")
    # (Your existing Breathing Space CSS goes here)
