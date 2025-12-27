import streamlit as st
import pandas as pd
import datetime
from groq import Groq
from streamlit_gsheets import GSheetsConnection

# --- 1. SETTINGS & STYLING ---
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

def get_clean_users():
    df = conn.read(worksheet="Users", ttl=0)
    df.columns = [str(c).strip().title().replace(" ", "") for c in df.columns]
    if 'Highscore' in df.columns: df = df.rename(columns={'Highscore': 'HighScore'})
    return df

# --- 3. PERSISTENT HIGH SCORE SYNC ---
qp = st.query_params
if "last_score" in qp and st.session_state.auth["logged_in"]:
    new_s = int(qp["last_score"])
    udf = get_clean_users()
    user_mask = udf['Username'].astype(str) == str(st.session_state.auth['cid'])
    if any(user_mask):
        idx = udf.index[user_mask][0]
        current_high = pd.to_numeric(udf.at[idx, 'HighScore'], errors='coerce') or 0
        if new_s > current_high:
            udf.at[idx, 'HighScore'] = new_s
            conn.update(worksheet="Users", data=udf)
            st.toast(f"🏆 Record Saved: {new_s}!", icon="🔥")
    st.query_params.clear()

# --- 4. LOGIN SYSTEM ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID", key="l_u")
        p_l = st.text_input("Password", type="password", key="l_p")
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = get_clean_users()
            m = udf[(udf['Username'].astype(str) == u_l) & (udf['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials.")
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

# --- 5. NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    main_nav = "Dashboard" if role == "patient" else "Analytics"
    side_opt = st.radio("Navigation", [main_nav])
    with st.expander("🧩 Zen Zone"):
        game_choice = st.selectbox("Select Break", ["Select a Game", "Memory Match", "Snake"])
    st.session_state.current_page = game_choice if game_choice != "Select a Game" else side_opt
    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False}; st.rerun()

# --- 6. GAME HTML DEFINITIONS ---

MEMORY_HTML = """
<div id="game-container" style="position: relative; width: 100%; display: flex; flex-direction: column; align-items: center; background: #1E293B; border-radius: 20px; padding: 10px;">
    <div id="game-ui" style="display:flex; justify-content:center; flex-wrap:wrap; gap:10px; perspective: 1000px; padding: 10px; max-width: 450px;"></div>
    <div id="win-overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15, 23, 42, 0.95); border-radius:20px; flex-direction:column; justify-content:center; align-items:center; z-index:100; text-align:center;">
        <h1 style="color:#FFD700; font-family: sans-serif;">Magnificent!</h1>
        <p style="color:white; font-family: sans-serif;">You matched them all! 🎉</p>
        <button onclick="window.location.reload()" style="padding:12px 30px; background:#219EBC; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold;">Play Again</button>
    </div>
</div>
<style>.card-inner { width: 100%; height: 100%; transition: transform 0.6s; transform-style: preserve-3d; position: relative; }</style>
<script>
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playTone(f, t, d) { const o=audioCtx.createOscillator(), g=audioCtx.createGain(); o.type=t; o.frequency.value=f; g.gain.setValueAtTime(0.05, audioCtx.currentTime); o.connect(g); g.connect(audioCtx.destination); o.start(); o.stop(audioCtx.currentTime+d); }
    const icons = ["🌟","🌟","🍀","🍀","🎈","🎈","💎","💎","🌈","🌈","🦄","🦄","🍎","🍎","🎨","🎨"];
    let flipped = [], matched = [], canFlip = true;
    let shuffled = icons.sort(() => Math.random() - 0.5);
    shuffled.forEach((icon, i) => {
        const card = document.createElement('div');
        card.style = "width: 70px; height: 90px; cursor: pointer;";
        card.innerHTML = `<div class="card-inner" id="card-${i}"><div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 20px; border-radius: 8px; background: #219EBC; color: white; border: 2px solid white;">?</div><div style="position: absolute; width: 100%; height: 100%; backface-visibility: hidden; display: flex; align-items: center; justify-content: center; font-size: 24px; border-radius: 8px; background: white; transform: rotateY(180deg); border: 2px solid #219EBC;">${icon}</div></div>`;
        card.onclick = () => {
            if (!canFlip || matched.includes(i) || (flipped.length > 0 && flipped[0].i === i)) return;
            playTone(400, 'sine', 0.1);
            document.getElementById(`card-${i}`).style.transform = "rotateY(180deg)";
            flipped.push({i, icon});
            if (flipped.length === 2) {
                canFlip = false;
                if (flipped[0].icon === flipped[1].icon) {
                    matched.push(flipped[0].i, flipped[1].i);
                    flipped = []; canFlip = true;
                    if (matched.length === icons.length) { 
                        playTone(523, 'sine', 0.2); setTimeout(()=>playTone(1046,'sine',0.4), 200);
                        document.getElementById('win-overlay').style.display = 'flex'; 
                    }
                } else {
                    setTimeout(() => {
                        document.getElementById(`card-${flipped[0].i}`).style.transform = "rotateY(0deg)";
                        document.getElementById(`card-${flipped[1].i}`).style.transform = "rotateY(0deg)";
                        flipped = []; canFlip = true;
                    }, 800);
                }
            }
        };
        document.getElementById('game-ui').appendChild(card);
    });
</script>
"""

SNAKE_HTML = """
<div id="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:24px; position: relative;">
    <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; border-radius:12px; background:#0F172A; max-width: 100%;"></canvas>
    <div id="overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15, 23, 42, 0.9); border-radius:24px; flex-direction:column; justify-content:center; align-items:center; z-index:100;">
        <h1 style="color:#F87171; font-family: sans-serif; font-size:40px;">GAME OVER</h1>
        <p id="finalScore" style="color:white; font-family: sans-serif; font-size:20px; margin-bottom:20px;">Score: 0</p>
        <button onclick="window.location.reload()" style="padding:12px 25px; background:#38BDF8; color:white; border:none; border-radius:10px; cursor:pointer; font-weight:bold; margin-bottom:10px;">TRY AGAIN</button>
        <button onclick="saveAndExit()" style="padding:8px 15px; background:transparent; color:#38BDF8; border:1px solid #38BDF8; border-radius:8px; cursor:pointer;">Save & Exit</button>
    </div>
</div>
<script>
    const canvas = document.getElementById("snakeGame"); const ctx = canvas.getContext("2d");
    const box = 20; let snake = [{x: 9*box, y: 10*box}], food = {x: 10*box, y: 5*box}, d, score = 0;
    function saveAndExit() {
        const url = new URL(window.parent.location.href);
        url.searchParams.set('last_score', score);
        window.parent.location.href = url.href;
    }
    function draw() {
        ctx.fillStyle = "#0F172A"; ctx.fillRect(0, 0, 400, 400);
        for(let i=0; i<snake.length; i++) { ctx.fillStyle = (i==0)?"#38BDF8":"#219EBC"; ctx.fillRect(snake[i].x, snake[i].y, box, box); }
        ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
        let sX = snake[0].x, sY = snake[0].y;
        if(d=="LEFT") sX-=box; if(d=="UP") sY-=box; if(d=="RIGHT") sX+=box; if(d=="DOWN") sY+=box;
        if(sX==food.x && sY==food.y) { score++; food={x:Math.floor(Math.random()*19+1)*box, y:Math.floor(Math.random()*19+1)*box}; }
        else if(d) snake.pop();
        let head = {x:sX, y:sY};
        if(sX<0||sX>=400||sY<0||sY>=400||(d && snake.some(s=>s.x==head.x&&s.y==head.y))) {
            clearInterval(game); document.getElementById("finalScore").innerText="Score: "+score;
            document.getElementById("overlay").style.display="flex";
        }
        if(d) snake.unshift(head);
    }
    document.addEventListener("keydown", e => {
        if(e.keyCode==37 && d!="RIGHT") d="LEFT"; if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT"; if(e.keyCode==40 && d!="UP") d="DOWN";
    });
    let game = setInterval(draw, 120);
</script>
"""

# --- 7. PAGE RENDERING ---
if st.session_state.current_page == "Dashboard":
    st.markdown(f'<div style="background: linear-gradient(90deg, #219EBC, #023047); padding: 25px; border-radius: 20px;"><h1>Hi {cname}! ☀️</h1></div>', unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        udf = get_clean_users()
        try: pb = pd.to_numeric(udf.loc[udf['Username'].astype(str)==cid, 'HighScore'].values[0], errors='coerce') or 0
        except: pb = 0
        st.markdown(f'<div class="portal-card"><h3 style="color:#FFD700;">🏆 Snake Record: {pb}</h3></div>', unsafe_allow_html=True)
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        score_text = st.select_slider("Vibe:", options=["Resting", "Low", "Steady", "Good", "Active", "Vibrant", "Radiant"], value="Steady")
        if st.button("Log Energy", use_container_width=True):
            df = conn.read(worksheet="Sheet1", ttl=0)
            new_row = pd.DataFrame([{"Date": datetime.date.today().strftime("%Y-%m-%d"), "Energy": 5, "CoupleID": cid}])
            conn.update(worksheet="Sheet1", data=pd.concat([df, new_row]))
            st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3>', unsafe_allow_html=True)
        chat_box = st.container(height=350)
        with chat_box:
            for m in st.session_state.chat_log:
                with st.chat_message("user" if m["type"]=="P" else "assistant"): st.write(m["msg"])
        p_in = st.chat_input("Tell Cooper...")
        if p_in:
            st.session_state.chat_log.append({"type":"P", "msg":p_in})
            msgs = [{"role":"system","content":f"You are Cooper, companion for {cname}."}] + [{"role":"user" if m["type"]=="P" else "assistant", "content":m["msg"]} for m in st.session_state.chat_log[-5:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type":"C", "msg":res}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.current_page == "Analytics":
    st.title("👩‍⚕️ Caregiver Command")
    data = conn.read(worksheet="Sheet1", ttl=0)
    f_data = data[data['CoupleID'].astype(str) == str(cid)]
    if not f_data.empty:
        st.line_chart(f_data.set_index("Date")['Energy'])

elif st.session_state.current_page == "Memory Match":
    st.title("🧩 3D Memory Match")
    st.components.v1.html(MEMORY_HTML, height=550)

elif st.session_state.current_page == "Snake":
    st.title("🐍 Zen Snake")
    st.components.v1.html(SNAKE_HTML, height=550)
