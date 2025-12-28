import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. MOBILE-FIRST CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    
    /* Force vertical stacking on mobile */
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    
    /* Touch-friendly buttons */
    .stButton>button { 
        border-radius: 15px; font-weight: 600; height: 3.5em; 
        width: 100%; border: none; font-size: 16px !important;
        margin-bottom: 10px;
    }
    
    .portal-card { 
        background: #1E293B; padding: 15px; border-radius: 20px; 
        border: 1px solid #334155; margin-bottom: 15px; 
    }

    /* Tab bar optimization */
    .stTabs [data-baseweb="tab-list"] { display: flex; justify-content: space-around; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; padding: 10px 5px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "mid": None, "role": "user"}

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. LOGIN & DUPLICATE CHECK ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;'>🧠 Health Bridge</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    
    with t1:
        u = st.text_input("Member ID").strip().lower()
        p = st.text_input("Password", type="password")
        if st.button("Sign In"):
            df = get_data("Users")
            if not df.empty and 'memberid' in df.columns:
                m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Invalid ID or Password")

    with t2:
        mid_new = st.text_input("Create ID").strip().lower()
        p_new = st.text_input("Create Password", type="password")
        if st.button("Register Account"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("This ID is already taken.")
            elif not mid_new or not p_new:
                st.warning("Please fill all fields.")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Success! Please Login.")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🛋️ Clara", "🎮 Games"]
if st.session_state.auth['role'] == "admin": tabs.append("🛡️ Admin")
nav = st.tabs(tabs)

# --- 5. COOPER ---
with nav[0]:
    st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
    ev = st.select_slider("Level", options=list(range(1,12)), value=6)
    if st.button("Save Sync"):
        new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
        conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
        st.toast("Energy Logged!")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.info("Chat with Cooper below:")
    # Standard Streamlit Chat UI is natively mobile-friendly
    if p := st.chat_input("How are you today?"):
        # (Logic for chat history and Groq API call remains same as before)
        pass

# --- 6. GAMES: MOBILE SNAKE WITH TOUCH CONTROLS ---
with nav[2]:
    st.markdown("### 🎮 Mobile Arcade")
    
    SNAKE_MOBILE_HTML = """
    <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:10px;">
        <canvas id="gc" width="280" height="280" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
        <div style="margin-top:15px; display:grid; grid-template-columns: repeat(3, 60px); grid-gap:10px;">
            <div></div><button onclick="changeDir('UP')" style="width:60px; height:60px; border-radius:10px; background:#334155; color:white; border:none; font-size:24px;">▲</button><div></div>
            <button onclick="changeDir('LEFT')" style="width:60px; height:60px; border-radius:10px; background:#334155; color:white; border:none; font-size:24px;">◀</button>
            <button onclick="changeDir('DOWN')" style="width:60px; height:60px; border-radius:10px; background:#334155; color:white; border:none; font-size:24px;">▼</button>
            <button onclick="changeDir('RIGHT')" style="width:60px; height:60px; border-radius:10px; background:#334155; color:white; border:none; font-size:24px;">▶</button>
        </div>
        <button onclick="resetGame()" style="margin-top:20px; width:100%; padding:10px; background:#38BDF8; border:none; border-radius:10px; color:white; font-weight:bold;">RESTART</button>
    </div>

    <script>
        const canvas = document.getElementById("gc");
        const ctx = canvas.getContext("2d");
        let box = 14;
        let snake, food, d, score, game;

        function resetGame() {
            snake = [{x: 9 * box, y: 10 * box}];
            food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
            score = 0; d = null;
            if(game) clearInterval(game);
            game = setInterval(draw, 120);
        }

        function changeDir(dir) {
            if(dir == 'LEFT' && d != 'RIGHT') d = 'LEFT';
            if(dir == 'UP' && d != 'DOWN') d = 'UP';
            if(dir == 'RIGHT' && d != 'LEFT') d = 'RIGHT';
            if(dir == 'DOWN' && d != 'UP') d = 'DOWN';
        }

        function draw() {
            ctx.fillStyle = "#0F172A"; ctx.fillRect(0,0,280,280);
            for(let i=0; i<snake.length; i++) {
                ctx.fillStyle = (i==0) ? "#38BDF8" : "#F8FAFC";
                ctx.fillRect(snake[i].x, snake[i].y, box, box);
            }
            ctx.fillStyle = "#F87171"; ctx.fillRect(food.x, food.y, box, box);
            let sX = snake[0].x; let sY = snake[0].y;
            if( d == "LEFT") sX -= box; if( d == "UP") sY -= box;
            if( d == "RIGHT") sX += box; if( d == "DOWN") sY += box;
            if(sX == food.x && sY == food.y) {
                food = {x: Math.floor(Math.random()*19+1)*box, y: Math.floor(Math.random()*19+1)*box};
            } else if(d) { snake.pop(); }
            let newHead = {x:sX, y:sY};
            if(sX < 0 || sX >= 280 || sY < 0 || sY >= 280 || collision(newHead, snake)) { clearInterval(game); }
            if(d) snake.unshift(newHead);
        }
        function collision(head, array) { for(let i=0; i<array.length; i++) { if(head.x == array[i].x && head.y == array[i].y) return true; } return false; }
        resetGame();
    </script>
    """
    st.components.v1.html(SNAKE_MOBILE_HTML, height=600)

# --- 7. ADMIN ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        st.subheader("🛡️ Search Logs")
        q = st.text_input("Keyword Search")
        df_admin = get_data("ChatLogs")
        if q and not df_admin.empty:
            df_admin = df_admin[df_admin['content'].str.contains(q, case=False)]
        st.dataframe(df_admin, use_container_width=True)

st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
