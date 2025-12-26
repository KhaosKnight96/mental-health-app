import streamlit as st
import pandas as pd
import datetime
import random
import time
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

# Custom UI Styling
st.markdown("""
<style>
    .portal-card {
        background: #ffffff;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        border-top: 5px solid #219EBC;
        text-align: center;
        margin-bottom: 15px;
    }
    .stButton>button { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
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

# --- 3. LOGIN & SIGN-UP WITH ROLE SELECTION ---
if not st.session_state.auth["logged_in"]:
    st.title("🧠 Health Bridge Portal")
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    try:
        udf = conn.read(worksheet="Users", ttl=0)
        udf.columns = [str(c).strip().title() for c in udf.columns] 
    except:
        st.error("Database connection failed.")
        st.stop()

    with t1:
        u_l, p_l = st.text_input("Couple ID", key="l_u"), st.text_input("Password", type="password", key="l_p")
        role_choice = st.selectbox("Log in as:", ["Patient", "Caregiver", "Admin"])
        
        if st.button("Enter Dashboard", use_container_width=True):
            m = udf[(udf['Username'].astype(str)==u_l) & (udf['Password'].astype(str)==p_l)]
            if not m.empty:
                st.session_state.auth = {"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname'], "role": role_choice.lower()}
                st.rerun()
            else: st.error("Invalid credentials")
    with t2:
        st.info("Registration is currently restricted to invited users.")
    st.stop()

# --- 4. NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.subheader(f"🏠 {cname}")
    st.write(f"Access: **{role.capitalize()}**")
    
    # Dynamic Navigation Based on Role
    nav_options = []
    if role == "patient": nav_options = ["Patient Portal", "Zen Zone"]
    elif role == "caregiver": nav_options = ["Caregiver Command", "Zen Zone"]
    elif role == "admin": nav_options = ["Admin Panel", "Patient Portal", "Caregiver Command", "Zen Zone"]
    
    mode = st.radio("Go to:", nav_options)
    
    st.divider()
    if st.button("Log Out", use_container_width=True):
        st.session_state.auth = {"logged_in": False}
        st.rerun()

# --- 5. PORTAL LOGIC ---

if mode == "Patient Portal":
    st.title(f"👋 Cooper Support")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="portal-card"><h3>Energy Check-in</h3><p>Log your current vitals and energy.</p></div>', unsafe_allow_html=True)
        score = st.select_slider("Energy (1-11)", options=range(1,12), value=6)
        if st.button("Submit Energy Score", use_container_width=True):
            st.success("Score recorded for today!")
    with col2:
        st.markdown('<div class="portal-card"><h3>Cooper AI</h3><p>Chat with your digital health companion.</p></div>', unsafe_allow_html=True)
        st.info("Type in the chat box below to begin.")
    
    st.divider()
    # (Existing Patient Chat Logic here)

elif mode == "Caregiver Command":
    st.title("👩‍⚕️ Clara Analyst")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="portal-card"><h3>Health Trends</h3><p>Visualize patient energy over time.</p></div>', unsafe_allow_html=True)
        # (Existing Line Chart Logic here)
    with col2:
        st.markdown('<div class="portal-card"><h3>Clara Intelligence</h3><p>Analyze logs for health patterns.</p></div>', unsafe_allow_html=True)
    
    st.divider()
    # (Existing Clara Chat Logic here)

elif mode == "Zen Zone":
    st.title("🧩 Zen Zone")
    game_choice = st.selectbox("Quick Break:", ["Memory Match", "Snake", "Breathing Space"])

    if game_choice == "Memory Match":
        memory_html = """
        <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:12px; perspective: 1000px; padding: 20px;"></div>
        <script>
        const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
        let shuffled = icons.sort(() => Math.random() - 0.5);
        let flipped = [];
        let matched = [];
        let canFlip = true;

        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playSound(f, type, d) {
            let o = audioCtx.createOscillator(); let g = audioCtx.createGain();
            o.type = type; o.frequency.value = f; g.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + d);
            o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime + d);
        }

        const container = document.getElementById('game-ui');
        shuffled.forEach((icon, i) => {
            const card = document.createElement('div');
            card.style = "width: 70px; height: 95px; cursor: pointer;";
            card.innerHTML = `
                <div class="card-inner" id="card-${i}" style="width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative;">
                    <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 12px; background: linear-gradient(135deg, #219EBC, #023047); color: white; border: 2px solid white; box-shadow: 0 4px 8px rgba(0,0,0,0.2);">?</div>
                    <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 32px; border-radius: 12px; background: white; transform: rotateY(180deg); border: 2px solid #219EBC; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">${icon}</div>
                </div>`;
            card.onclick = () => {
                if (!canFlip || flipped.includes(i) || matched.includes(i)) return;
                document.getElementById(`card-${i}`).style.transform = "rotateY(180deg)";
                flipped.push({i, icon});
                playSound(400, 'sine', 0.1);

                if (flipped.length === 2) {
                    canFlip = false;
                    if (flipped[0].icon === flipped[1].icon) {
                        matched.push(flipped[0].i, flipped[1].i);
                        setTimeout(() => { playSound(600, 'sine', 0.3); canFlip = true; }, 300);
                        flipped = [];
                    } else {
                        // Keep face up for 1 second before flipping back
                        setTimeout(() => {
                            document.getElementById(`card-${flipped[0].i}`).style.transform = "rotateY(0deg)";
                            document.getElementById(`card-${flipped[1].i}`).style.transform = "rotateY(0deg)";
                            playSound(150, 'sawtooth', 0.2);
                            flipped = [];
                            canFlip = true;
                        }, 1000);
                    }
                }
            };
            container.appendChild(card);
        });
        </script>
        """
        st.components.v1.html(memory_html, height=500)
    
    elif game_choice == "Snake":
        # (Insert your Snake Logic with Sound/Swipe here)
        st.info("Snake Game Loading...")

elif mode == "Admin Panel":
    st.title("🛡️ Admin Oversight")
    # (Existing Admin Log Logic here)
