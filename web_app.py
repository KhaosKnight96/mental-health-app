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

# Initialize Session States
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "current_page" not in st.session_state: st.session_state.current_page = "Dashboard"
if "snake_high_score" not in st.session_state: st.session_state.snake_high_score = 0

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

cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

# --- 3. NAVIGATION LOGIC ---
def reset_to_home():
    st.session_state.current_page = "Dashboard" if role == "patient" else "Analytics"
    if "game_selector" in st.session_state:
        st.session_state.game_selector = "Select a Game"

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"Logged in: **{cname}**")
    
    main_nav = st.radio("Navigation", ["Dashboard"] if role == "patient" else ["Analytics"], key="main_nav_radio")
    
    st.divider()
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["Select a Game", "Memory Match", "Snake"], key="game_selector")
    
    if game_choice != "Select a Game":
        st.session_state.current_page = game_choice
    else:
        st.session_state.current_page = main_nav

    if st.session_state.current_page in ["Memory Match", "Snake"]:
        st.write("##")
        st.button("🏠 Exit Zen Zone", use_container_width=True, type="primary", on_click=reset_to_home)

    st.divider()
    if st.button("🔄 Switch Role"): st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False, "role": None}; st.rerun()

mode = st.session_state.current_page

# --- 4. PAGE CONTENT ---

if mode in ["Dashboard", "Analytics"]:
    if role == "patient":
        st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown(f'<div class="portal-card"><h3>🏆 Snake Record: {st.session_state.snake_high_score}</h3></div>', unsafe_allow_html=True)
            st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
            options = ["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"]
            val_map = {"Resting":1, "Low":3, "Steady":5, "Good":7, "Active":9, "Vibrant":10, "Radiant":11}
            score_text = st.select_slider("Vibe:", options=options, value="Steady")
            if st.button("Log Energy", use_container_width=True):
                df = conn.read(worksheet="Sheet1", ttl=0)
                new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": val_map[score_text], "CoupleID": cid}])
                conn.update(worksheet="Sheet1", data=pd.concat([df, new_row], ignore_index=True))
                st.balloons()
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3></div>', unsafe_allow_html=True)
            chat_box = st.container(height=350)
            with chat_box:
                for m in st.session_state.chat_log:
                    with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
            p_in = st.chat_input("Tell Cooper...")
            if p_in:
                st.session_state.chat_log.append({"type": "P", "msg": p_in})
                msgs = [{"role":"system","content":f"You are Cooper, a companion for {cname}."}] + [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
                res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
                st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()
    else:
        st.title("👩‍⚕️ Caregiver Command")
        try:
            data = conn.read(worksheet="Sheet1", ttl=0)
            f_data = data[data['CoupleID'].astype(str) == str(cid)]
            if not f_data.empty: st.line_chart(f_data.set_index("Date")['Energy'])
        except: st.info("No data yet.")

elif mode == "Memory Match":
    st.title("🧩 3D Memory Match")
    st.write("Match all icons for a celebration!")
    
    memory_html = """
    <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:12px; perspective: 1000px; padding: 20px;"></div>
    <script>
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playTone(freq, type, dur, vol=0.05) {
        const osc = audioCtx.createOscillator(); const gain = audioCtx.createGain();
        osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(vol, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.start(); osc.stop(audioCtx.currentTime + dur);
    }
    
    function winCelebration() {
        // High-pitched victory chime
        playTone(523.25, 'sine', 0.2, 0.1); // C5
        setTimeout(() => playTone(659.25, 'sine', 0.2, 0.1), 150); // E5
        setTimeout(() => playTone(783.99, 'sine', 0.2, 0.1), 300); // G5
        setTimeout(() => playTone(1046.50, 'sine', 0.6, 0.1), 450); // C6
        setTimeout(() => { alert("🎉 Magnificent! You matched them all!"); }, 700);
    }

    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let shuffled = icons.sort(() => Math.random() - 0.5);
    let flipped = []; let matched = []; let canFlip = true;
    const container = document.getElementById('game-ui');

    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.style = "width: 80px; height: 110px; cursor: pointer;";
        card.innerHTML = `<div class="card-inner" id="card-${i}" style="width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative;">
                <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 12px; background: #219EBC; color: white; border: 2px solid white;">?</div>
                <div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 32px; border-radius: 12px; background: white; transform: rotateY(180deg); border: 2px solid #219EBC;">${icon}</div>
            </div>`;
        card.onclick = () => {
            if (!canFlip || matched.includes(i) || (flipped.length > 0 && flipped[0].i === i)) return;
            
            playTone(400, 'sine', 0.1);
            document.getElementById(`card-${i}`).style.transform = "rotateY(180deg)";
            flipped.push({i, icon});

            if (flipped.length === 2) {
                canFlip = false;
                if (flipped[0].icon === flipped[1].icon) {
                    setTimeout(() => playTone(800, 'triangle', 0.2), 300);
                    matched.push(flipped[0].i, flipped[1].i);
                    flipped = []; canFlip = true;
                    if (matched.length === icons.length) setTimeout(winCelebration, 600);
                } else {
                    setTimeout(() => {
                        playTone(200, 'sine', 0.1);
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

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    # (Snake Code remains unchanged from previous stable version)
    snake_html = """
    <div id="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:24px; touch-action: none; position: relative;">
        <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; border-radius:12px; background:#0F172A; max-width: 100%;"></canvas>
        <div id="overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15, 23, 42, 0.9); border-radius:24px; flex-direction:column; justify-content:center; align-items:center; z-index:100;">
            <h1 style="color:#F87171; font-size:48px;">GAME OVER</h1>
            <p id="finalScore" style="color:white; font-size:20px;">Score: 0</p>
            <button onclick="resetGame()" style="padding:15px 30px; background:#38BDF8; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold;">TRY AGAIN</button>
        </div>
    </div>
    <script>
        const canvas = document.getElementById("snakeGame"); const ctx = canvas.getContext("2d");
        const overlay = document.getElementById("overlay"); const scoreDisplay = document.getElementById("finalScore");
        const box = 20; let snake, food, d, score, game;
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        function playTone(freq, type, dur) {
            const osc = audioCtx.createOscillator(); const gain = audioCtx.createGain();
            osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
            osc.connect(gain); gain.connect(audioCtx.destination);
            osc.start(); osc.stop(audioCtx.currentTime + dur);
        }
        function init() {
            snake = [{x: 9 * box, y: 10 * box}];
            food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
            d = null; score = 0; overlay.style.display = "none";
            if(game) clearInterval(game); game = setInterval(draw, 120);
        }
        function resetGame() { init(); }
        function changeDir(dir) {
            if(dir == 'left' && d != 'RIGHT') d = 'LEFT';
            if(dir == 'up' && d != 'DOWN') d = 'UP';
            if(dir == 'right' && d != 'LEFT') d = 'RIGHT';
            if(dir == 'down' && d != 'UP') d = 'DOWN';
        }
        document.addEventListener("keydown", e => {
            const keys = {37:'left', 38:'up', 39:'right', 40:'down'};
            if(keys[e.keyCode]) changeDir(keys[e.keyCode]);
        });
        let xD, yD;
        canvas.addEventListener('touchstart', e => { xD = e.touches[0].clientX; yD = e.touches[0].clientY; }, false);
        canvas.addEventListener('touchmove', e => {
            if (!xD || !yD) return;
            let xU = e.touches[0].clientX, yU = e.touches[0].clientY;
            let xDf = xD - xU, yDf = yD - yU;
            if (Math.abs(xDf) > Math.abs(yDf)) { changeDir(xDf > 0 ? 'left' : 'right'); }
            else { changeDir(yDf > 0 ? 'up' : 'down'); }
            xD = null; yD = null;
        }, false);
        function draw() {
            ctx.fillStyle = "#0F172A"; ctx.fillRect(0, 0, canvas.width, canvas.height);
            for(let i=0; i<snake.length; i++) {
                ctx.fillStyle = (i==0) ? "#38BDF8" : "#219EBC";
                ctx.fillRect(snake[i].x, snake[i].y, box, box);
            }
            ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
            let sX = snake[0].x, sY = snake[0].y;
            if(d == "LEFT") sX -= box; if(d == "UP") sY -= box;
            if(d == "RIGHT") sX += box; if(d == "DOWN") sY += box;
            if(sX == food.x && sY == food.y) {
                score++; playTone(600, 'sine', 0.1);
                food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
            } else if(d) { snake.pop(); }
            let head = {x: sX, y: sY};
            if(sX < 0 || sX >= canvas.width || sY < 0 || sY >= canvas.height || (d && collision(head, snake))) {
                clearInterval(game); playTone(150, 'sawtooth', 0.5);
                scoreDisplay.innerText = "Final Score: " + score; overlay.style.display = "flex";
            }
            if(d) snake.unshift(head);
        }
        function collision(h, a) {
            for(let i=0; i<a.length; i++) if(h.x==a[i].x && h.y==a[i].y) return true;
            return false;
        }
        init();
    </script>
    """
    st.components.v1.html(snake_html, height=600)
