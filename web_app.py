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

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "clara_history" not in st.session_state: st.session_state.clara_history = []

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

# --- 3. SIDEBAR NAVIGATION ---
cid, cname, role = st.session_state.auth["cid"], st.session_state.auth["name"], st.session_state.auth["role"]

with st.sidebar:
    st.title("🌉 Health Bridge")
    st.write(f"**{cname}**")
    
    if role == "patient":
        mode = st.radio("Navigation", ["Dashboard"])
    else:
        mode = st.radio("Navigation", ["Analytics"])
    
    with st.expander("🧩 Zen Zone", expanded=False):
        game_choice = st.selectbox("Select Break", ["--- Home ---", "Memory Match", "Snake"])
        if game_choice != "--- Home ---": mode = game_choice

    st.divider()
    if st.button("🔄 Switch Role"): st.session_state.auth["role"] = None; st.rerun()
    if st.button("🚪 Logout"): st.session_state.auth = {"logged_in": False, "role": None}; st.rerun()

# --- 4. PAGE CONTENT ---

if mode == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        score_text = st.select_slider("Vibe:", options=["Resting", "Steady", "Vibrant"], value="Steady")
        if st.button("Log Energy"): st.balloons()
    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3></div>', unsafe_allow_html=True)
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        p_in = st.chat_input("Tell Cooper how you're feeling...")
        if p_in:
            st.session_state.chat_log.append({"type": "P", "msg": p_in})
            msgs = [{"role":"system","content":f"You are Cooper, a warm, supportive health companion for {cname}."}] + \
                   [{"role": "user" if m["type"]=="P" else "assistant", "content": m["msg"]} for m in st.session_state.chat_log[-6:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type": "C", "msg": res}); st.rerun()

elif mode == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        f_data = data[data['CoupleID'].astype(str) == str(cid)]
        if not f_data.empty:
            st.line_chart(f_data.set_index("Date")['Energy'])
    except: st.info("No data yet.")

elif mode == "Memory Match":
    st.title("🧩 3D Memory Match")
    # (Previous Memory Match HTML code goes here)

elif mode == "Snake":
    st.title("🐍 Zen Snake")
    st.markdown("<p style='text-align:center; opacity:0.7;'>Swipe the screen or use Arrow Keys to move.</p>", unsafe_allow_html=True)
    
    snake_html = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:30px; border-radius:24px; touch-action: none;">
        <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; border-radius:12px; background:#0F172A; max-width: 100%; height: auto;"></canvas>
    </div>

    <script>
        const canvas = document.getElementById("snakeGame");
        const ctx = canvas.getContext("2d");
        const box = 20;
        let snake = [{x: 9 * box, y: 10 * box}];
        let food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
        let d;

        function changeDir(dir) {
            if(dir == 'left' && d != 'RIGHT') d = 'LEFT';
            if(dir == 'up' && d != 'DOWN') d = 'UP';
            if(dir == 'right' && d != 'LEFT') d = 'RIGHT';
            if(dir == 'down' && d != 'UP') d = 'DOWN';
        }

        // --- Keyboard ---
        document.addEventListener("keydown", e => {
            if(e.keyCode == 37 && d != 'RIGHT') d = 'LEFT';
            if(e.keyCode == 38 && d != 'DOWN') d = 'UP';
            if(e.keyCode == 39 && d != 'LEFT') d = 'RIGHT';
            if(e.keyCode == 40 && d != 'UP') d = 'DOWN';
        });

        // --- Swipe ---
        let xDown = null, yDown = null;
        canvas.addEventListener('touchstart', e => {
            xDown = e.touches[0].clientX; yDown = e.touches[0].clientY;
        }, false);

        canvas.addEventListener('touchmove', e => {
            if (!xDown || !yDown) return;
            let xUp = e.touches[0].clientX, yUp = e.touches[0].clientY;
            let xDiff = xDown - xUp, yDiff = yDown - yUp;

            if (Math.abs(xDiff) > Math.abs(yDiff)) {
                if (xDiff > 0) changeDir('left'); else changeDir('right');
            } else {
                if (yDiff > 0) changeDir('up'); else changeDir('down');
            }
            xDown = null; yDown = null;
        }, false);

        function draw() {
            ctx.fillStyle = "#0F172A";
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            for(let i=0; i<snake.length; i++) {
                ctx.fillStyle = (i==0) ? "#38BDF8" : "#219EBC";
                ctx.fillRect(snake[i].x, snake[i].y, box, box);
            }
            ctx.fillStyle = "#F87171";
            ctx.fillRect(food.x, food.y, box, box);
            
            let snakeX = snake[0].x, snakeY = snake[0].y;
            if(d == "LEFT") snakeX -= box;
            if(d == "UP") snakeY -= box;
            if(d == "RIGHT") snakeX += box;
            if(d == "DOWN") snakeY += box;

            if(snakeX == food.x && snakeY == food.y) {
                food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
            } else {
                snake.pop();
            }

            let newHead = {x: snakeX, y: snakeY};
            if(snakeX < 0 || snakeX >= canvas.width || snakeY < 0 || snakeY >= canvas.height || collision(newHead, snake)) {
                clearInterval(game);
                alert("Game Over! Swipe or Press a key to restart.");
                location.reload();
            }
            snake.unshift(newHead);
        }

        function collision(head, array) {
            for(let i=0; i<array.length; i++) {
                if(head.x == array[i].x && head.y == array[i].y) return true;
            }
            return false;
        }
        let game = setInterval(draw, 120);
    </script>
    """
    st.components.v1.html(snake_html, height=550)
