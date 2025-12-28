import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION & STYLING ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 24px; padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }
    .avatar-circle {
        width: 70px; height: 70px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 35px; margin: 0 auto 10px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.4); }
        70% { box-shadow: 0 0 0 12px rgba(56, 189, 248, 0); }
        100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
    }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA CORE ---
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

# --- 3. LOGIN ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    with t1:
        u = st.text_input("Member ID", key="l_u").strip().lower()
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Portal", key="l_b"):
            df_u = get_data("Users")
            if not df_u.empty:
                m = df_u[(df_u['memberid'].astype(str).str.lower() == u) & (df_u['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
    with t2:
        mid_new = st.text_input("New Member ID", key="r_u").strip().lower()
        p_new = st.text_input("New Password", type="password", key="r_p")
        if st.button("Register", key="r_b"):
            df_u = get_data("Users")
            if not df_u.empty and mid_new in df_u['memberid'].astype(str).str.lower().values:
                st.error("ID taken")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df_u, new_user], ignore_index=True))
                st.success("Ready! Login now.")
    st.stop()

# --- 4. NAVIGATION ---
nav_tabs = ["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games"]
if st.session_state.auth['role'] == "admin": nav_tabs.append("🛡️ Admin")
tabs = st.tabs(nav_tabs)

# --- 5. COOPER ---
with tabs[0]:
    st.markdown("""<div class="glass-card"><div class="avatar-circle" style="background:linear-gradient(135deg,#0ea5e9,#6366f1);">🤖</div><h2 style="text-align:center;margin:0;">Cooper's Corner</h2></div>""", unsafe_allow_html=True)
    with st.expander("⚡ Sync Daily Energy Status", expanded=False):
        ev = st.select_slider("Level (1-11)", options=list(range(1,12)), value=6, key="e_sl")
        if st.button("💾 Sync Data", key="e_bt"):
            new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
            st.toast("Synced!")
    for msg in st.session_state.cooper_logs: st.chat_message(msg["role"]).write(msg["content"])
    if p := st.chat_input("Talk to Cooper...", key="c_in"):
        st.session_state.cooper_logs.append({"role": "user", "content": p}); save_chat("Cooper", "user", p)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res}); save_chat("Cooper", "assistant", res); st.rerun()

# --- 6. CLARA ---
with tabs[1]:
    st.markdown("""<div class="glass-card"><div class="avatar-circle" style="background:linear-gradient(135deg,#f472b6,#e11d48);">🧘‍♀️</div><h2 style="text-align:center;margin:0;">Clara's Couch</h2></div>""", unsafe_allow_html=True)
    df_l = get_data("Sheet1")
    if not df_l.empty:
        df_p = df_l[df_l['memberid'].astype(str).str.lower() == st.session_state.auth['mid']].copy()
        if not df_p.empty:
            df_p['timestamp'] = pd.to_datetime(df_p['timestamp'])
            fig = go.Figure(go.Scatter(x=df_p['timestamp'], y=df_p['energylog'], fill='tozeroy', line=dict(color='#F472B6', width=3)))
            fig.update_layout(height=250, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)
    for msg in st.session_state.clara_logs: st.chat_message(msg["role"]).write(msg["content"])
    if cp := st.chat_input("Analyze with Clara...", key="cl_in"):
        st.session_state.clara_logs.append({"role": "user", "content": cp}); save_chat("Clara", "user", cp)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara."}]+st.session_state.clara_logs[-3:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res}); save_chat("Clara", "assistant", res); st.rerun()

# --- 7. GAMES (MEMORY + SNAKE + 2048 WITH SOUND) ---
with tabs[2]:
    game_mode = st.radio("Pick a Game", ["Snake", "2048", "Memory"], horizontal=True, key="gm_rd")
    
    # Sound Utility + Common Game Logic
    SOUND_JS = """
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function playNote(freq, dur, type="sine") {
        const osc = audioCtx.createOscillator(); const gain = audioCtx.createGain();
        osc.type = type; osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime); gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + dur);
        osc.connect(gain); gain.connect(audioCtx.destination); osc.start(); osc.stop(audioCtx.currentTime + dur);
    }
    """

    if game_mode == "Snake":
        st.components.v1.html(f"<script>{SOUND_JS}</script>" + """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:20px; touch-action:none;">
            <canvas id="sc" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            <h3 style="color:#38BDF8;" id="sn_sc">Score: 0</h3>
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
                if(h.x==food.x&&h.y==food.y) { food={x:Math.floor(Math.random()*19)*box,y:Math.floor(Math.random()*19)*box}; playNote(440, 0.1, "square"); } else if(d) snake.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||(d&&snake.some(s=>s.x==h.x&&s.y==h.y))) { playNote(150, 0.5, "sawtooth"); reset(); }
                if(d) snake.unshift(h); document.getElementById("sn_sc").innerText="Score: "+(snake.length-1);
            }
            reset();
        </script>""", height=450)

    elif game_mode == "2048":
        st.components.v1.html(f"<script>{SOUND_JS}</script>" + """
        <div id="g2k" style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:20px; touch-action:none;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,65px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
        </div>
        <script>
            let board=Array(16).fill(0), tsX, tsY;
            window.addEventListener('keydown', e => {
                let m=false; if(e.key=="ArrowLeft"){mv(0,1,4); m=true;} if(e.key=="ArrowRight"){mv(3,-1,4); m=true;}
                if(e.key=="ArrowUp"){mv(0,4,1); m=true;} if(e.key=="ArrowDown"){mv(12,-4,1); m=true;} if(m){ playNote(300, 0.05); add(); ren(); }
            });
            document.getElementById('g2k').addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            document.getElementById('g2k').addEventListener('touchend', e => {
                let dx=e.changedTouches[0].clientX-tsX, dy=e.changedTouches[0].clientY-tsY;
                if(Math.abs(dx)>40 || Math.abs(dy)>40){
                    if(Math.abs(dx)>Math.abs(dy)) { if(dx>40) mv(3,-1,4); else mv(0,1,4); }
                    else { if(dy>40) mv(12,-4,1); else mv(0,4,1); }
                    playNote(300, 0.05); add(); ren();
                }
            });
            function add(){ let e=board.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) board[e[Math.floor(Math.random()*e.length)]]=2; }
            function ren(){ const g=document.getElementById('grid'); g.innerHTML=''; board.forEach(v=>{ const t=document.createElement('div'); t.style=`width:65px;height:65px;background:${v?'#38BDF8':'#334155'};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }); }
            function mv(s,st,sd){ for(let i=0;i<4;i++){ let l=[]; for(let j=0;j<4;j++) l.push(board[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){ f[j]*=2; playNote(600,0.1); f.splice(j+1,1); } while(f.length<4) f.push(0); for(let j=0;j<4;j++) board[s+i*sd+j*st]=f[j]; } }
            add(); add(); ren();
        </script>""", height=450)

    elif game_mode == "Memory":
        st.components.v1.html(f"<script>{SOUND_JS}</script>" + """
        <div style="display:flex; flex-direction:column; align-items:center; background:#1E293B; border-radius:20px; padding:20px;">
            <h3 id="lvl" style="color:#38BDF8;">Level: 1</h3>
            <div id="m_grid" style="display:grid; grid-template-columns:repeat(3,70px); gap:10px;"></div>
            <button id="st_m" style="margin-top:20px; padding:10px 20px; border-radius:10px; border:none; background:#38BDF8; color:white; font-weight:bold;">Start Round</button>
        </div>
        <script>
            let lvl=1, seq=[], userSeq=[], canClick=false;
            const grid=document.getElementById("m_grid");
            function build(){ grid.innerHTML=""; for(let i=0;i<9;i++){ const d=document.createElement("div"); d.style="width:70px;height:70px;background:#334155;border-radius:10px;cursor:pointer"; d.onclick=()=>click(i); grid.appendChild(d); } }
            async function flash(i, color="#38BDF8"){ const d=grid.children[i]; d.style.background=color; playNote(200+i*50, 0.2); await new Promise(r=>setTimeout(r,400)); d.style.background="#334155"; }
            document.getElementById("st_m").onclick=async()=>{
                seq.push(Math.floor(Math.random()*9)); userSeq=[]; canClick=false;
                for(let s of seq){ await new Promise(r=>setTimeout(r,200)); await flash(s); }
                canClick=true;
            };
            async function click(i){
                if(!canClick) return; await flash(i, "#F472B6"); userSeq.push(i);
                if(userSeq[userSeq.length-1] !== seq[userSeq.length-1]){ playNote(100, 0.5, "sawtooth"); alert("Game Over!"); seq=[]; lvl=1; document.getElementById("lvl").innerText="Level: 1"; }
                else if(userSeq.length === seq.length){ lvl++; document.getElementById("lvl").innerText="Level: "+lvl; canClick=false; playNote(800, 0.2); }
            }
            build();
        </script>""", height=450)

# --- 8. ADMIN ---
if st.session_state.auth['role'] == "admin":
    with tabs[3]:
        logs_df = get_data("ChatLogs")
        if not logs_df.empty:
            c1, c2 = st.columns(2)
            with c1: u_f = st.multiselect("Users", logs_df['memberid'].unique(), key="ad_u")
            with c2: a_f = st.multiselect("Agents", logs_df['agent'].unique(), key="ad_a")
            kw = st.text_input("🔍 Search", key="ad_kw")
            f_df = logs_df.copy()
            if u_f: f_df = f_df[f_df['memberid'].isin(u_f)]
            if a_f: f_df = f_df[f_df['agent'].isin(a_f)]
            if kw: f_df = f_df[f_df['content'].astype(str).str.contains(kw, case=False)]
            st.dataframe(f_df, use_container_width=True, hide_index=True)

if st.sidebar.button("Logout", key="lg_sb"): st.session_state.clear(); st.rerun()
