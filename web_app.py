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
    /* Hide the technical sync button from the user */
    div.element-container:has(#hidden_sync_btn) { display: none; }
</style>
""", unsafe_allow_html=True)

# --- 2. CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
if "chat_log" not in st.session_state: st.session_state.chat_log = []
if "temp_score" not in st.session_state: st.session_state.temp_score = 0

def get_clean_users():
    try:
        df = conn.read(worksheet="Users", ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        target = [c for c in df.columns if c.lower().replace(" ", "") == "highscore"]
        if target:
            df = df.rename(columns={target[0]: "HighScore"})
            df['HighScore'] = pd.to_numeric(df['HighScore'], errors='coerce').fillna(0).astype(int)
        return df
    except: return pd.DataFrame()

# --- 3. THE FAIL-SAFE SYNC ENGINE ---
def sync_score_to_sheets():
    new_s = st.session_state.temp_score
    udf = get_clean_users()
    if not udf.empty:
        user_mask = udf['Username'].astype(str) == str(st.session_state.auth['cid'])
        if any(user_mask):
            idx = udf.index[user_mask][0]
            if new_s > int(udf.at[idx, 'HighScore']):
                udf.at[idx, 'HighScore'] = new_s
                conn.update(worksheet="Users", data=udf)
                st.cache_data.clear()
                st.toast(f"🏆 Record Updated: {new_s}!", icon="🔥")
            else:
                st.toast(f"Game Over! Score: {new_s}", icon="🎮")
    st.session_state.temp_score = 0 # Reset

# --- 4. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
        u_l = st.text_input("Couple ID")
        p_l = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True, type="primary"):
            udf = get_clean_users()
            m = udf[(udf['Username'].astype(str) == u_l) & (udf['Password'].astype(str) == p_l)]
            if not m.empty:
                st.session_state.auth.update({"logged_in": True, "cid": u_l, "name": m.iloc[0]['Fullname']})
                st.rerun()
            else: st.error("Invalid credentials.")
    st.stop()

# --- 5. SIDEBAR & NAVIGATION ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    page = st.radio("Navigation", ["Dashboard", "Snake", "Memory Match"])
    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None}
        st.rerun()

# --- 6. PAGE CONTENT ---
if page == "Dashboard":
    st.markdown(f"<h1>Hi {st.session_state.auth['name']}! ☀️</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        udf = get_clean_users()
        row = udf[udf['Username'].astype(str) == str(st.session_state.auth['cid'])]
        pb = int(row['HighScore'].values[0]) if not row.empty else 0
        st.markdown(f'<div class="portal-card"><h3 style="color:#FFD700;">🏆 Record: {pb}</h3></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        if st.button("Log Daily Wellness", use_container_width=True): st.balloons()
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
            msgs = [{"role":"system","content":"You are Cooper."}] + \
                   [{"role":"user" if m["type"]=="P" else "assistant", "content":m["msg"]} for m in st.session_state.chat_log[-5:]]
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs).choices[0].message.content
            st.session_state.chat_log.append({"type":"C", "msg":res}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "Snake":
    st.title("🐍 Zen Snake")
    
    # Hidden communication bridge
    if st.session_state.temp_score > 0:
        sync_score_to_sheets()

    # The Game
    SNAKE_HTML = """
    <div id="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:24px; position:relative;">
        <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; background:#0F172A; border-radius:12px;"></canvas>
        <div id="overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.95); flex-direction:column; justify-content:center; align-items:center; border-radius:24px;">
            <h1 style="color:white; font-family:sans-serif;">GAME OVER</h1>
            <p id="finalScore" style="color:cyan; font-size:32px; font-family:sans-serif; margin-bottom:20px;"></p>
            <button id="realSaveBtn" style="padding:15px 40px; background:#38BDF8; color:white; border:none; border-radius:12px; cursor:pointer; font-weight:bold; font-size:20px;">💾 SAVE & EXIT</button>
        </div>
    </div>

    <script>
    const canvas = document.getElementById("snakeGame");
    const ctx = canvas.getContext("2d");
    const box = 20; let score = 0; let d = null;
    let snake = [{x: 9*box, y: 10*box}];
    let food = {x: Math.floor(Math.random()*19)*box, y: Math.floor(Math.random()*19)*box};

    // The Bridge: Send data back to Streamlit
    function sendToStreamlit(scoreValue) {
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: scoreValue
        }, '*');
    }

    document.getElementById("realSaveBtn").onclick = () => {
        sendToStreamlit(score);
    };

    document.addEventListener("keydown", e => {
        if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
        if(e.keyCode==37 && d!="RIGHT") d="LEFT";
        if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT";
        if(e.keyCode==40 && d!="UP") d="DOWN";
    });

    function draw() {
        ctx.fillStyle = "#0F172A"; ctx.fillRect(0,0,400,400);
        ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
        for(let i=0; i<snake.length; i++) {
            ctx.fillStyle = (i==0) ? "#38BDF8" : "#219EBC";
            ctx.fillRect(snake[i].x, snake[i].y, box, box);
        }
        let sX = snake[0].x; let sY = snake[0].y;
        if(d=="LEFT") sX-=box; if(d=="UP") sY-=box; if(d=="RIGHT") sX+=box; if(d=="DOWN") sY+=box;
        if(sX==food.x && sY==food.y) {
            score++;
            food={x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box};
        } else if(d) snake.pop();
        let head = {x:sX, y:sY};
        if(sX<0 || sX>=400 || sY<0 || sY>=400 || (d && snake.some(s=>s.x==head.x && s.y==head.y))) {
            clearInterval(game);
            document.getElementById("finalScore").innerText = score + " Points";
            document.getElementById("overlay").style.display="flex";
        }
        if(d) snake.unshift(head);
    }
    let game = setInterval(draw, 100);
    </script>
    """
    
    # capturing the result from the HTML component
    # This is the "Magic" line that catches the score from JavaScript
    result = st.components.v1.html(SNAKE_HTML, height=500)
    if result is not None:
        st.session_state.temp_score = result
        st.rerun()

elif page == "Memory Match":
    st.title("🧩 Memory Match")
    st.info("Feature in progress...")
