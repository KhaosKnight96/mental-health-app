import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    .stButton>button { border-radius: 15px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    .portal-card { background: #1E293B; padding: 15px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 15px; }
    .dpad { display: grid; grid-template-columns: repeat(3, 65px); grid-gap: 10px; justify-content: center; margin-top: 15px; }
    .btn { width: 65px; height: 65px; background: #334155; color: white; border: none; border-radius: 12px; font-size: 24px; cursor: pointer; }
    .btn:active { background: #38BDF8; }
    .empty { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- 2. HELPERS ---
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

# --- 3. LOGIN GATE (FIXED KEYS) ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;'>🧠 Health Bridge</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        # Added unique keys: 'login_mid' and 'login_pass'
        u = st.text_input("Member ID", key="login_mid").strip().lower()
        p = st.text_input("Password", type="password", key="login_pass")
        if st.button("Sign In", key="btn_signin"):
            df = get_data("Users")
            if not df.empty:
                m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Invalid credentials")

    with t2:
        # Added unique keys: 'reg_name', 'reg_mid', 'reg_pass'
        n = st.text_input("Full Name", key="reg_name")
        mid_new = st.text_input("Create Member ID", key="reg_mid").strip().lower()
        p_new = st.text_input("Create Password", type="password", key="reg_pass")
        if st.button("Register Account", key="btn_reg"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("This ID is already taken.")
            else:
                new_user = pd.DataFrame([{"fullname": n, "memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Registered! Go to Login tab.")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🎮 Games"]
if st.session_state.auth['role'] == "admin": tabs.append("🛡️ Admin")
nav = st.tabs(tabs)

# --- 5. COOPER ---
with nav[0]:
    st.chat_message("assistant").write("I'm Cooper. How can I help?")
    if p := st.chat_input("Message Cooper..."):
        st.session_state.cooper_logs.append({"role": "user", "content": p})
        # Simple AI Response logic
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        st.rerun()

# --- 6. GAMES (D-PAD FOR BOTH) ---
with nav[1]:
    game_choice = st.radio("Choose Game", ["Snake", "2048"], horizontal=True)
    
    # Common D-Pad HTML snippet
    DPAD_HTML = """
    <div class="dpad">
        <div class="empty"></div><button class="btn" onclick="sendDir('UP')">▲</button><div class="empty"></div>
        <button class="btn" onclick="sendDir('LEFT')">◀</button><button class="btn" onclick="sendDir('DOWN')">▼</button><button class="btn" onclick="sendDir('RIGHT')">▶</button>
    </div>
    """

    if game_choice == "Snake":
        S_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:15px; border-radius:15px;">
            <canvas id="sc" width="280" height="280" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            {DPAD_HTML}
        </div>
        <script>
            const canvas=document.getElementById("sc"); const ctx=canvas.getContext("2d");
            let box=14, snake, food, d, game;
            window.sendDir = (dir) => {{ if(dir=='UP'&&d!='DOWN')d='UP'; if(dir=='DOWN'&&d!='UP')d='DOWN'; if(dir=='LEFT'&&d!='RIGHT')d='LEFT'; if(dir=='RIGHT'&&d!='LEFT')d='RIGHT'; }};
            function reset(){{ snake=[{{x:9*box,y:10*box}}]; food={{x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}}; d=null; if(game) clearInterval(game); game=setInterval(draw,130); }}
            function draw(){{
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,280,280);
                ctx.fillStyle="#F87171"; ctx.fillRect(food.x, food.y, box, box);
                snake.forEach((p,i)=>{{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,box,box); }});
                let hX=snake[0].x, hY=snake[0].y;
                if(d=='LEFT') hX-=box; if(d=='UP') hY-=box; if(d=='RIGHT') hX+=box; if(d=='DOWN') hY+=box;
                if(hX==food.x && hY==food.y) food={{x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}};
                else if(d) snake.pop();
                let head={{x:hX,y:hY}};
                if(hX<0||hX>=280||hY<0||hY>=280||(d && snake.some(s=>s.x==head.x&&s.y==head.y))) reset();
                if(d) snake.unshift(head);
            }}
            reset();
        </script>
        """
        st.components.v1.html(S_HTML, height=500)

    else:
        T2048_HTML = f"""
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; padding:15px; border-radius:15px;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,60px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
            {DPAD_HTML}
        </div>
        <script>
            let board=Array(16).fill(0);
            window.sendDir = (dir) => {{ 
                let old=JSON.stringify(board);
                if(dir=='UP') mv(0,4,1); if(dir=='DOWN') mv(12,-4,1); if(dir=='LEFT') mv(0,1,4); if(dir=='RIGHT') mv(3,-1,4);
                if(old!==JSON.stringify(board)){{ add(); ren(); }}
            }};
            function add(){{ let e=board.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=2; }}
            function ren(){{ const g=document.getElementById('grid'); g.innerHTML=''; board.forEach(v=>{{ const t=document.createElement('div'); t.style=`width:60px;height:60px;background:${{v?'#38BDF8':'#334155'}};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }}); }}
            function mv(s,st,sd){{ for(let i=0;i<4;i++){{ let l=[]; for(let j=0;j<4;j++) l.push(board[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){{ f[j]*=2; f.splice(j+1,1); }} while(f.length<4) f.push(0); for(let j=0;j<4;j++) board[s+i*sd+j*st]=f[j]; }} }}
            add(); add(); ren();
        </script>
        """
        st.components.v1.html(T2048_HTML, height=500)

# --- 7. ADMIN (KEYWORD SEARCH) ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        st.subheader("🛡️ Admin Log Search")
        # Unique key 'admin_search'
        q = st.text_input("🔍 Search Keyword", key="admin_search").strip().lower()
        logs_df = get_data("ChatLogs")
        if not logs_df.empty:
            if q:
                logs_df = logs_df[logs_df['content'].astype(str).str.lower().str.contains(q)]
            st.dataframe(logs_df, use_container_width=True)

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
