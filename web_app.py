import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. MOBILE-FIRST CONFIGURATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    .stButton>button { 
        border-radius: 15px; font-weight: 600; height: 3.5em; 
        width: 100%; border: none; font-size: 16px !important;
    }
    .portal-card { 
        background: #1E293B; padding: 15px; border-radius: 20px; 
        border: 1px solid #334155; margin-bottom: 15px; 
    }
    .game-box { touch-action: none; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "mid": None, "role": "user"}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

# --- 3. LOGIN & DUPLICATE PROTECTION (FIXED KEYS) ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;'>🧠 Health Bridge</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Member ID", key="login_id").strip().lower()
        p = st.text_input("Password", type="password", key="login_pass")
        if st.button("Sign In", key="login_btn"):
            df = get_data("Users")
            if not df.empty:
                m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Check credentials")
    with t2:
        mid_new = st.text_input("New Member ID", key="signup_id").strip().lower()
        p_new = st.text_input("Create Password", type="password", key="signup_pass")
        if st.button("Register", key="signup_btn"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("ID already exists.")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🎮 Games"]
if st.session_state.auth['role'] == "admin": tabs.append("🛡️ Admin")
nav = st.tabs(tabs)

# --- 5. COOPER ---
with nav[0]:
    for m in st.session_state.cooper_logs:
        st.chat_message(m["role"]).write(m["content"])
    if p := st.chat_input("Speak with Cooper..."):
        st.session_state.cooper_logs.append({"role": "user", "content": p})
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        st.rerun()

# --- 6. GAMES (HYBRID: SWIPE + KEYBOARD) ---
with nav[1]:
    game_mode = st.radio("Select Game", ["Snake Hybrid", "2048 Hybrid"], horizontal=True)
    
    if game_mode == "Snake Hybrid":
        SNAKE_HTML = """
        <div class="game-box" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:15px; touch-action:none;">
            <canvas id="sc" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px; outline:none;" tabindex="0"></canvas>
            <p style="color:#38BDF8; font-weight:bold; margin-top:10px;" id="score">Score: 0</p>
        </div>
        <script>
            const canvas = document.getElementById("sc"); const ctx = canvas.getContext("2d");
            let box = 15; let snake, food, d, game;
            let tsX, tsY;

            // KEYBOARD CONTROLS
            window.addEventListener('keydown', e => {
                if(e.key=="ArrowLeft" && d!='RIGHT') d='LEFT';
                if(e.key=="ArrowUp" && d!='DOWN') d='UP';
                if(e.key=="ArrowRight" && d!='LEFT') d='RIGHT';
                if(e.key=="ArrowDown" && d!='UP') d='DOWN';
            });

            // SWIPE CONTROLS
            canvas.addEventListener('touchstart', e => { tsX = e.touches[0].clientX; tsY = e.touches[0].clientY; });
            canvas.addEventListener('touchend', e => {
                let dx = e.changedTouches[0].clientX - tsX; let dy = e.changedTouches[0].clientY - tsY;
                if(Math.abs(dx) > Math.abs(dy)) { if(dx>30 && d!='LEFT') d='RIGHT'; else if(dx<-30 && d!='RIGHT') d='LEFT'; }
                else { if(dy>30 && d!='UP') d='DOWN'; else if(dy<-30 && d!='DOWN') d='UP'; }
            });

            function reset() { snake=[{x:9*box,y:10*box}]; food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}; d=null; if(game) clearInterval(game); game=setInterval(draw,130); }
            function draw() {
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300);
                ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
                snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,box,box); });
                let head = {x:snake[0].x, y:snake[0].y};
                if(d=='LEFT') head.x-=box; if(d=='UP') head.y-=box; if(d=='RIGHT') head.x+=box; if(d=='DOWN') head.y+=box;
                if(head.x==food.x && head.y==food.y) food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box};
                else if(d) snake.pop();
                if(head.x<0||head.x>=300||head.y<0||head.y>=300||(d && snake.some(s=>s.x==head.x&&s.y==head.y))) reset();
                if(d) snake.unshift(head); document.getElementById("score").innerText="Score: "+(snake.length-1);
            }
            reset();
        </script>
        """
        st.components.v1.html(SNAKE_HTML, height=450)

    else:
        T2048_HTML = """
        <div id="g2048" class="game-box" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:15px; touch-action:none;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,65px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
            <h3 id="sc2" style="color:#38BDF8; margin-top:10px;">Score: 0</h3>
        </div>
        <script>
            let board=Array(16).fill(0); let score=0; let tsX, tsY;
            
            // KEYBOARD CONTROLS
            window.addEventListener('keydown', e => {
                if(e.key=="ArrowLeft") mv(0,1,4); if(e.key=="ArrowRight") mv(3,-1,4);
                if(e.key=="ArrowUp") mv(0,4,1); if(e.key=="ArrowDown") mv(12,-4,1);
                add(); ren();
            });

            // SWIPE CONTROLS
            document.getElementById('g2048').addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            document.getElementById('g2048').addEventListener('touchend', e => {
                let dx=e.changedTouches[0].clientX-tsX; let dy=e.changedTouches[0].clientY-tsY;
                if(Math.abs(dx)>Math.abs(dy)) { if(dx>40) mv(3,-1,4); else if(dx<-40) mv(0,1,4); }
                else { if(dy>40) mv(12,-4,1); else if(dy<-40) mv(0,4,1); }
                add(); ren();
            });

            function add(){ let e=board.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=2; }
            function ren(){ 
                const g=document.getElementById('grid'); g.innerHTML='';
                board.forEach(v=>{ const t=document.createElement('div'); t.style=`width:65px;height:65px;background:${v?'#38BDF8':'#334155'};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); });
                document.getElementById('sc2').innerText="Score: "+score;
            }
            function mv(s,st,sd){ for(let i=0;i<4;i++){ let l=[]; for(let j=0;j<4;j++) l.push(board[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){ f[j]*=2; score+=f[j]; f.splice(j+1,1); } while(f.length<4) f.push(0); for(let j=0;j<4;j++) board[s+i*sd+j*st]=f[j]; } }
            add(); add(); ren();
        </script>
        """
        st.components.v1.html(T2048_HTML, height=450)

# --- 7. ADMIN (FIXED SEARCH KEY) ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        st.subheader("🛡️ Admin Log Search")
        q = st.text_input("🔍 Search Keyword", key="admin_search_input")
        df_logs = get_data("ChatLogs")
        if q and not df_logs.empty:
            df_logs = df_logs[df_logs['content'].astype(str).str.contains(q, case=False)]
        st.dataframe(df_logs, use_container_width=True)

if st.button("Logout", key="logout_btn"):
    st.session_state.clear()
    st.rerun()
