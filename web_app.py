import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    .portal-card { background: #1E293B; padding: 20px; border-radius: 20px; border: 1px solid #334155; margin-bottom: 20px; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; border: none; }
    .game-box { touch-action: none; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA HELPERS ---
conn = st.connection("gsheets", type=GSheetsConnection)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "mid": None, "role": "user"}
if "cooper_logs" not in st.session_state: st.session_state.cooper_logs = []
if "clara_logs" not in st.session_state: st.session_state.clara_logs = []

def get_data(worksheet_name):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def save_chat(agent, role, content):
    new_entry = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'],
        "agent": agent, "role": role, "content": content
    }])
    conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_entry], ignore_index=True))

# --- 3. LOGIN GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h2 style='text-align:center;'>🧠 Health Bridge</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Member ID", key="l_id").strip().lower()
        p = st.text_input("Password", type="password", key="l_pw")
        if st.button("Sign In", key="l_btn"):
            df = get_data("Users")
            if not df.empty:
                m = df[(df['memberid'].astype(str).str.lower() == u) & (df['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
    with t2:
        mid_new = st.text_input("New Member ID", key="s_id").strip().lower()
        p_new = st.text_input("Password", type="password", key="s_pw")
        if st.button("Register", key="s_btn"):
            df = get_data("Users")
            if not df.empty and mid_new in df['memberid'].astype(str).str.lower().values:
                st.error("ID taken")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df, new_user], ignore_index=True))
                st.success("Account created!")
    st.stop()

# --- 4. NAVIGATION ---
tabs = ["🏠 Cooper", "🛋️ Clara", "🎮 Games"]
if st.session_state.auth['role'] == "admin": tabs.append("🛡️ Admin")
nav = st.tabs(tabs)

# --- 5. COOPER'S CORNER ---
with nav[0]:
    st.markdown('<div class="portal-card"><h3>⚡ Energy Status</h3>', unsafe_allow_html=True)
    ev = st.select_slider("How are you feeling?", options=list(range(1,12)), value=6, key="energy_slider")
    if st.button("💾 Sync Data", key="sync_energy"):
        new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
        conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
        st.toast("Logged!")
    st.markdown('</div>', unsafe_allow_html=True)

    for m in st.session_state.cooper_logs:
        st.chat_message(m["role"]).write(m["content"])
    
    if p := st.chat_input("Speak with Cooper...", key="cooper_chat"):
        st.session_state.cooper_logs.append({"role": "user", "content": p})
        save_chat("Cooper", "user", p)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        save_chat("Cooper", "assistant", res)
        st.rerun()

# --- 6. CLARA'S COUCH ---
with nav[1]:
    st.subheader("🧘‍♀️ Clara's Analytics")
    df_l = get_data("Sheet1")
    if not df_l.empty:
        df_p = df_l[df_l['memberid'].astype(str).str.lower() == st.session_state.auth['mid']].copy()
        if not df_p.empty:
            df_p['timestamp'] = pd.to_datetime(df_p['timestamp'])
            fig = go.Figure(go.Scatter(x=df_p['timestamp'], y=df_p['energylog'], fill='tozeroy', line=dict(color='#F472B6')))
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

    for m in st.session_state.clara_logs:
        st.chat_message(m["role"]).write(m["content"])

    if cp := st.chat_input("Analyze with Clara...", key="clara_chat"):
        st.session_state.clara_logs.append({"role": "user", "content": cp})
        save_chat("Clara", "user", cp)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara."}]+st.session_state.clara_logs[-3:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res})
        save_chat("Clara", "assistant", res)
        st.rerun()

# --- 7. GAMES (HYBRID: KEYBOARD + SWIPE) ---
with nav[2]:
    game_mode = st.radio("Select Game", ["Snake", "2048"], horizontal=True, key="game_selector")
    
    if game_mode == "Snake":
        S_HTML = """
        <div class="game-box" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:15px;">
            <canvas id="sc" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            <p style="color:#38BDF8; margin-top:10px;" id="score">Score: 0</p>
        </div>
        <script>
            const canvas=document.getElementById("sc"); const ctx=canvas.getContext("2d");
            let box=15, snake, food, d, game, tsX, tsY;
            window.addEventListener('keydown', e => { 
                if(e.key=="ArrowLeft"&&d!='RIGHT') d='LEFT'; if(e.key=="ArrowUp"&&d!='DOWN') d='UP';
                if(e.key=="ArrowRight"&&d!='LEFT') d='RIGHT'; if(e.key=="ArrowDown"&&d!='UP') d='DOWN';
            });
            canvas.addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            canvas.addEventListener('touchend', e => {
                let dx=e.changedTouches[0].clientX-tsX, dy=e.changedTouches[0].clientY-tsY;
                if(Math.abs(dx)>Math.abs(dy)) { if(dx>30&&d!='LEFT') d='RIGHT'; else if(dx<-30&&d!='RIGHT') d='LEFT'; }
                else { if(dy>30&&d!='UP') d='DOWN'; else if(dy<-30&&d!='DOWN') d='UP'; }
            });
            function reset(){ snake=[{x:9*box,y:10*box}]; food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}; d=null; if(game) clearInterval(game); game=setInterval(draw,130); }
            function draw(){
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300); ctx.fillStyle="#F87171"; ctx.fillRect(food.x,food.y,box,box);
                snake.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,box,box); });
                let h={...snake[0]}; if(d=='LEFT') h.x-=box; if(d=='UP') h.y-=box; if(d=='RIGHT') h.x+=box; if(d=='DOWN') h.y+=box;
                if(h.x==food.x&&h.y==food.y) food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}; else if(d) snake.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||(d&&snake.some(s=>s.x==h.x&&s.y==h.y))) reset();
                if(d) snake.unshift(h); document.getElementById("score").innerText="Score: "+(snake.length-1);
            }
            reset();
        </script>"""
        st.components.v1.html(S_HTML, height=450)
    else:
        T2048_HTML = """
        <div id="g2k" class="game-box" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:15px;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,65px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
        </div>
        <script>
            let board=Array(16).fill(0), tsX, tsY;
            window.addEventListener('keydown', e => {
                if(e.key=="ArrowLeft") mv(0,1,4); if(e.key=="ArrowRight") mv(3,-1,4);
                if(e.key=="ArrowUp") mv(0,4,1); if(e.key=="ArrowDown") mv(12,-4,1); add(); ren();
            });
            document.getElementById('g2k').addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            document.getElementById('g2k').addEventListener('touchend', e => {
                let dx=e.changedTouches[0].clientX-tsX, dy=e.changedTouches[0].clientY-tsY;
                if(Math.abs(dx)>Math.abs(dy)) { if(dx>40) mv(3,-1,4); else if(dx<-40) mv(0,1,4); }
                else { if(dy>40) mv(12,-4,1); else if(dy<-40) mv(0,4,1); }
                add(); ren();
            });
            function add(){ let e=board.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=2; }
            function ren(){ const g=document.getElementById('grid'); g.innerHTML=''; board.forEach(v=>{ const t=document.createElement('div'); t.style=`width:65px;height:65px;background:${v?'#38BDF8':'#334155'};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }); }
            function mv(s,st,sd){ for(let i=0;i<4;i++){ let l=[]; for(let j=0;j<4;j++) l.push(board[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){ f[j]*=2; f.splice(j+1,1); } while(f.length<4) f.push(0); for(let j=0;j<4;j++) board[s+i*sd+j*st]=f[j]; } }
            add(); add(); ren();
        </script>"""
        st.components.v1.html(T2048_HTML, height=450)

# --- 8. ADMIN ---
if st.session_state.auth['role'] == "admin":
    with nav[-1]:
        q = st.text_input("🔍 Search Keyword", key="admin_q")
        df_logs = get_data("ChatLogs")
        if q and not df_logs.empty:
            df_logs = df_logs[df_logs['content'].astype(str).str.contains(q, case=False)]
        st.dataframe(df_logs, use_container_width=True)

if st.sidebar.button("Logout", key="logout_sidebar"):
    st.session_state.clear()
    st.rerun()
