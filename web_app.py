import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & APP-WIDE STYLING ---
st.set_page_config(page_title="Health Bridge Portal", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #1E293B !important; border-right: 1px solid #334155; }
    .portal-card { background: #1E293B; padding: 25px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    h1, h2, h3, p, label { color: #F8FAFC !important; }
    .stButton>button { border-radius: 12px !important; font-weight: 600 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "current_page" not in st.session_state: st.session_state.current_page = "Dashboard"

# --- 3. PERSISTENT HIGH SCORE LOGIC ---
qp = st.query_params
if "last_score" in qp and st.session_state.auth["logged_in"]:
    new_s = int(qp["last_score"])
    udf = conn.read(worksheet="Users", ttl=0)
    current_high = udf.loc[udf['Username'].astype(str) == str(st.session_state.auth['cid']), 'HighScore'].values[0]
    
    if new_s > current_high:
        udf.loc[udf['Username'].astype(str) == str(st.session_state.auth['cid']), 'HighScore'] = new_s
        conn.update(worksheet="Users", data=udf)
        st.toast(f"🏆 New Personal Best Saved: {new_s}!", icon="🔥")
    st.query_params.clear()

# --- 4. LOGIN SYSTEM ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = conn.read(worksheet="Users", ttl=0)
            udf.columns = [str(c).strip().title() for c in udf.columns]
            # Match credentials
            m = udf[(udf['Username'].astype(str) == u_l) & (udf['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({
                    "logged_in": True, 
                    "cid": u_l, 
                    "name": m.iloc[0]['Fullname']
                })
                st.rerun()
            else:
                st.error("Invalid credentials.")
    st.stop()

# Role selection if logged in but role not picked
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

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"User: **{cname}**")
    main_nav = st.radio("Navigation", ["Dashboard"] if role == "patient" else ["Analytics"])
    
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["Select a Game", "Memory Match", "Snake"])
    
    if game_choice != "Select a Game":
        st.session_state.current_page = game_choice
    else:
        st.session_state.current_page = main_nav

    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
        st.rerun()

# --- 6. PAGE CONTENT ---
if st.session_state.current_page == "Memory Match":
    st.title("🧩 3D Memory Match")
    memory_html = """
    <div id="game-container" style="position: relative; width: 100%; display: flex; flex-direction: column; align-items: center;">
        <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:12px; perspective: 1000px; padding: 20px; max-width: 500px;"></div>
        <div id="win-overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15, 23, 42, 0.95); border-radius:20px; flex-direction:column; justify-content:center; align-items:center; z-index:100; text-align:center; animation: fadeIn 0.5s;">
            <h1 style="color:#FFD700; font-size:42px;">Magnificent!</h1>
            <p style="color:white; font-size:20px;">You matched them all! 🎉</p>
            <button onclick="window.location.reload()" style="padding:15px 40px; background:#219EBC; color:white; border:none; border-radius:12px; cursor:pointer; font-weight:bold; font-size:18px;">Play Again</button>
        </div>
    </div>
    <style>
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .card-inner { width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative; }
    </style>
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
    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let flipped = []; let matched = []; let canFlip = true;
    const container = document.getElementById('game-ui');
    const overlay = document.getElementById('win-overlay');
    let shuffled = icons.sort(() => Math.random() - 0.5);
    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.style = "width: 80px; height: 110px; cursor: pointer;";
        card.innerHTML = `<div class="card-inner" id="card-${i}"><div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 12px; background: #219EBC; color: white; border: 2px solid white;">?</div><div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 32px; border-radius: 12px; background: white; transform: rotateY(180deg); border: 2px solid #219EBC;">${icon}</div></div>`;
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
                    if (matched.length === icons.length) {
                        playTone(523.25, 'sine', 0.2, 0.1);
                        setTimeout(() => playTone(1046.50, 'sine', 0.6, 0.1), 450);
                        setTimeout(() => { overlay.style.display = 'flex'; }, 600);
                    }
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

elif st.session_state.current_page == "Snake":
    st.title("🐍 Zen Snake")
    user_data = conn.read(worksheet="Users", ttl=0)
    pb = user_data.loc[user_data['Username'].astype(str) == cid, 'HighScore'].values[0]
    st.write(f"🏆 Personal Best: **{pb}**")
    
    snake_html = f"""
    <div id="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:24px; position: relative;">
        <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; border-radius:12px; background:#0F172A; max-width: 100%;"></canvas>
        <div id="overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15, 23, 42, 0.9); border-radius:24px; flex-direction:column; justify-content:center; align-items:center; z-index:100;">
            <h1 style="color:#F87171; font-size:48px;">GAME OVER</h1>
            <p id="finalScore" style="color:white; font-size:20px; margin-bottom:20px;">Score: 0</p>
            <button onclick="window.location.reload()" style="padding:15px 30px; background:#38BDF8; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold; margin-bottom:10px;">TRY AGAIN</button>
            <button onclick="saveAndExit()" style="padding:10px 20px; background:transparent; color:#38BDF8; border:1px solid #38BDF8; border-radius:10px; cursor:pointer;">Save Score & Exit</button>
        </div>
    </div>
    <script>
        const canvas = document.getElementById("snakeGame"); const ctx = canvas.getContext("2d");
        const overlay = document.getElementById("overlay"); const scoreDisplay = document.getElementById("finalScore");
        const box = 20; let snake, food, d, score, game;
        function init() {{
            snake = [{{x: 9 * box, y: 10 * box}}];
            food = {{x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box}};
            d = null; score = 0;
            game = setInterval(draw, 120);
        }}
        function saveAndExit() {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set('last_score', score);
            window.parent.location.href = url.href;
        }}
        function draw() {{
            ctx.fillStyle = "#0F172A"; ctx.fillRect(0, 0, canvas.width, canvas.height);
            for(let i=0; i<snake.length; i++) {{
                ctx.fillStyle = (i==0) ? "#38BDF8" : "#219EBC";
                ctx.fillRect(snake[i].x, snake[i].y, box, box);
            }}
            ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
            let sX = snake[0].x, sY = snake[0].y;
            if(d == "LEFT") sX -= box; if(d == "UP") sY -= box;
            if(d == "RIGHT") sX += box; if(d == "DOWN") sY += box;
            if(sX == food.x && sY == food.y) {{
                score++;
                food = {{x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box}};
            }} else if(d) {{ snake.pop(); }}
            let head = {{x: sX, y: sY}};
            if(sX < 0 || sX >= canvas.width || sY < 0 || sY >= canvas.height || (d && collision(head, snake))) {{
                clearInterval(game);
                scoreDisplay.innerText = "Final Score: " + score; overlay.style.display = "flex";
            }}
            if(d) snake.unshift(head);
        }}
        function collision(head, array) {{
            for(let i=0; i<array.length; i++) if(head.x == array[i].x && head.y == array[i].y) return true;
            return false;
        }}
        document.addEventListener("keydown", e => {{
            if(e.keyCode == 37 && d != "RIGHT") d = "LEFT";
            if(e.keyCode == 38 && d != "DOWN") d = "UP";
            if(e.keyCode == 39 && d != "LEFT") d = "RIGHT";
            if(e.keyCode == 40 && d != "UP") d = "DOWN";
        }});
        init();
    </script>
    """
    st.components.v1.html(snake_html, height=600)

else:
    # --- DASHBOARD ---
    st.markdown(f"## ☀️ Welcome back, {cname}")
    st.write(f"Logged in as: **{role.title()}**")
