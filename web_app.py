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

def get_clean_users():
    """Fetches the latest data with zero caching (ttl=0)."""
    try:
        df = conn.read(worksheet="Users", ttl=0)
        df.columns = [str(c).strip() for c in df.columns]
        target = [c for c in df.columns if c.lower().replace(" ", "") == "highscore"]
        if target:
            df = df.rename(columns={target[0]: "HighScore"})
            df['HighScore'] = pd.to_numeric(df['HighScore'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Sheet Access Error: {e}")
        return pd.DataFrame()

# --- 3. THE HIGH SCORE SYNC ENGINE (RE-ENGINEERED) ---
# This part catches the score from the URL after the game exits
qp = st.query_params
if "score_sync" in qp and st.session_state.auth.get("logged_in"):
    try:
        new_s = int(float(qp["score_sync"]))
        udf = get_clean_users()
        if not udf.empty:
            cid_str = str(st.session_state.auth['cid'])
            user_mask = udf['Username'].astype(str) == cid_str
            if any(user_mask):
                idx = udf.index[user_mask][0]
                old_record = int(udf.at[idx, 'HighScore'])
                if new_s > old_record:
                    udf.at[idx, 'HighScore'] = new_s
                    conn.update(worksheet="Users", data=udf)
                    st.cache_data.clear()
                    st.success(f"🏆 NEW RECORD SAVED: {new_s}!")
                else:
                    st.toast(f"Score: {new_s}. Record: {old_record}", icon="🎮")
    except Exception as e:
        st.error(f"Sync error: {e}")
    st.query_params.clear()
    st.rerun()

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

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🌉 Health Bridge")
    page = st.radio("Navigation", ["Dashboard", "Snake"])
    if st.button("🚪 Logout"):
        st.session_state.auth = {"logged_in": False, "cid": None, "name": None, "role": None}
        st.rerun()

# --- 6. PAGE CONTENT ---
if page == "Dashboard":
    st.markdown(f"<h1>Hi {st.session_state.auth['name']}! ☀️</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 2])
    with col1:
        udf = get_clean_users()
        user_row = udf[udf['Username'].astype(str) == str(st.session_state.auth['cid'])]
        pb = int(user_row['HighScore'].values[0]) if not user_row.empty else 0
        st.markdown(f'<div class="portal-card"><h3 style="color:#FFD700;">🏆 Best Score: {pb}</h3></div>', unsafe_allow_html=True)
        
        # Energy Log
        st.markdown('<div class="portal-card"><h3>✨ Energy Log</h3>', unsafe_allow_html=True)
        if st.button("Log Daily Wellness", use_container_width=True): st.balloons()
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="portal-card"><h3>🤖 Cooper AI</h3>', unsafe_allow_html=True)
        # Cooper AI Logic...
        st.info("Cooper is ready to chat on the dashboard.")
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "Snake":
    st.title("🐍 Zen Snake")
    st.warning("⚠️ **Note:** When Game Over appears, click 'SAVE & EXIT' to sync your score.")
    
    # We use a more robust JS redirect method
    SNAKE_HTML = f"""
    <div id="game-container" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:20px; border-radius:24px; position:relative;">
        <canvas id="snakeGame" width="400" height="400" style="border:4px solid #38BDF8; background:#0F172A;"></canvas>
        <div id="overlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.9); flex-direction:column; justify-content:center; align-items:center; border-radius:24px; z-index:999;">
            <h1 style="color:white; font-family:sans-serif; margin-bottom:10px;">GAME OVER</h1>
            <p id="finalScore" style="color:cyan; font-size:28px; font-family:sans-serif; margin-bottom:20px;"></p>
            <button id="saveBtn" style="padding:15px 30px; background:#38BDF8; color:white; border:none; border-radius:12px; cursor:pointer; font-weight:bold; font-size:18px;">💾 SAVE & EXIT</button>
        </div>
    </div>
    <script>
    const canvas = document.getElementById("snakeGame");
    const ctx = canvas.getContext("2d");
    const box = 20; let score = 0; let d = null;
    let snake = [{{x: 9*box, y: 10*box}}];
    let food = {{x: Math.floor(Math.random()*19)*box, y: Math.floor(Math.random()*19)*box}};

    function saveAndExit() {{
        // This is the most reliable way to break out of an iframe in Streamlit
        window.top.location.href = window.top.location.pathname + "?score_sync=" + score;
    }}

    document.getElementById("saveBtn").onclick = saveAndExit;

    document.addEventListener("keydown", e => {{
        if(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) e.preventDefault();
        if(e.keyCode==37 && d!="RIGHT") d="LEFT";
        if(e.keyCode==38 && d!="DOWN") d="UP";
        if(e.keyCode==39 && d!="LEFT") d="RIGHT";
        if(e.keyCode==40 && d!="UP") d="DOWN";
    }});

    function draw() {{
        ctx.fillStyle = "#0F172A"; ctx.fillRect(0,0,400,400);
        ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
        for(let i=0; i<snake.length; i++) {{
            ctx.fillStyle = (i==0) ? "#38BDF8" : "#219EBC";
            ctx.fillRect(snake[i].x, snake[i].y, box, box);
        }}
        let sX = snake[0].x; let sY = snake[0].y;
        if(d=="LEFT") sX-=box; if(d=="UP") sY-=box; if(d=="RIGHT") sX+=box; if(d=="DOWN") sY+=box;
        if(sX==food.x && sY==food.y) {{
            score++;
            food={{x:Math.floor(Math.random()*19)*box, y:Math.floor(Math.random()*19)*box}};
        }} else if(d) snake.pop();
        let head = {{x:sX, y:sY}};
        if(sX<0 || sX>=400 || sY<0 || sY>=400 || (d && snake.some(s=>s.x==head.x && s.y==head.y))) {{
            clearInterval(game);
            document.getElementById("finalScore").innerText = "Score: " + score;
            document.getElementById("overlay").style.display="flex";
        }}
        if(d) snake.unshift(head);
    }}
    let game = setInterval(draw, 100);
    </script>
    """
    st.components.v1.html(SNAKE_HTML, height=500)
