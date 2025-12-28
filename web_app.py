import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION & ADVANCED STYLING ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(15px);
        border-radius: 20px; padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    [data-testid="stChatMessageUser"] { background-color: #1E3A8A !important; border: 1px solid #38BDF8; }
    [data-testid="stChatMessageAssistant"] { background-color: #1E293B !important; border: 1px solid #6366F1; }
    .bot-avatar {
        width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; 
        justify-content: center; font-size: 30px; margin: 0 auto 10px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.3);
    }
    .stButton>button { border-radius: 12px; font-weight: 700; text-transform: uppercase; transition: 0.3s; }
</style>
""", unsafe_allow_html=True)

# --- 2. CORE LOGIC & AI DEBUGGER ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}
if "active_game" not in st.session_state: st.session_state.active_game = None

# Sidebar AI Status Check
with st.sidebar:
    st.title("🛠️ System Status")
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        st.success("Sheets: Connected")
    except: st.error("Sheets: Connection Failed")
    
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if api_key:
        try:
            client = Groq(api_key=api_key)
            st.success("AI: Key Loaded")
        except: st.error("AI: Invalid Key")
    else:
        st.warning("AI: Missing Key in Secrets")

def load_sheet(name):
    try:
        df = conn.read(worksheet=name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def log_to_sheet(sheet, data_dict):
    try:
        current_df = load_sheet(sheet)
        new_row = pd.DataFrame([data_dict])
        conn.update(worksheet=sheet, data=pd.concat([current_df, new_row], ignore_index=True))
    except: pass

# --- 3. LOGIN GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u = st.text_input("Member ID", key="l_u").strip().lower()
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Portal", key="l_b"):
            users = load_sheet("Users")
            if not users.empty and u in users['memberid'].astype(str).str.lower().values:
                match = users[users['memberid'].astype(str).str.lower() == u]
                if str(match.iloc[0]['password']) == p:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(match.iloc[0]['role']).lower()})
                    st.rerun()
            st.error("Invalid ID or Password")
    with t2:
        nu = st.text_input("New Member ID", key="r_u")
        np = st.text_input("New Password", type="password", key="r_p")
        if st.button("Register", key="r_b"):
            log_to_sheet("Users", {"memberid": nu, "password": np, "role": "user"})
            st.success("Account created! Log in above.")
    st.stop()

# --- 4. MAIN TABS ---
tabs = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games", "🛡️ Admin"])

# --- 5. COOPER ---
with tabs[0]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar">🤖</div><h3 style="text-align:center;">Cooper\'s Corner</h3></div>', unsafe_allow_html=True)
    with st.expander("📈 Log Energy"):
        val = st.select_slider("Select 1-11", options=list(range(1,12)), value=6, key="e_v")
        if st.button("Sync to Sheets", key="e_b"):
            log_to_sheet("Sheet1", {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": val})
            st.toast("Energy Logged!")
    
    for m in st.session_state.chats["Cooper"]: st.chat_message(m["role"]).write(m["content"])
    if p := st.chat_input("Ask Cooper something...", key="coop_i"):
        st.session_state.chats["Cooper"].append({"role": "user", "content": p})
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper, a helpful health companion."}]+st.session_state.chats["Cooper"][-3:]).choices[0].message.content
            st.session_state.chats["Cooper"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "role": "assistant", "content": res})
        except Exception as e: st.error(f"AI Connectivity Error: {e}")
        st.rerun()

# --- 6. CLARA ---
with tabs[1]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar" style="background:linear-gradient(135deg,#F472B6,#E11D48);">🧘‍♀️</div><h3 style="text-align:center;">Clara\'s Couch</h3></div>', unsafe_allow_html=True)
    df_l = load_sheet("Sheet1")
    if not df_l.empty:
        df_p = df_l[df_l['memberid'].astype(str) == st.session_state.auth['mid']]
        if not df_p.empty:
            fig = go.Figure(go.Scatter(x=pd.to_datetime(df_p['timestamp']), y=df_p['energylog'], fill='tozeroy', line=dict(color='#F472B6', width=3)))
            fig.update_layout(height=150, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

    for m in st.session_state.chats["Clara"]: st.chat_message(m["role"]).write(m["content"])
    if pc := st.chat_input("Speak with Clara...", key="clara_i"):
        st.session_state.chats["Clara"].append({"role": "user", "content": pc})
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara, a data-driven health analyst."}]+st.session_state.chats["Clara"][-3:]).choices[0].message.content
            st.session_state.chats["Clara"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Clara", "role": "assistant", "content": res})
        except Exception as e: st.error(f"AI Connectivity Error: {e}")
        st.rerun()

# --- 7. GAMES CENTER (REPACKAGED WITH UI OVERLAYS) ---
with tabs[2]:
    SOUND_JS = """const actx = new (window.AudioContext || window.webkitAudioContext)();
    function sfx(f, d, t='sine') {
        const o=actx.createOscillator(); const g=actx.createGain();
        o.type=t; o.frequency.value=f; g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime+d);
        o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime+d);
    }"""

    if st.session_state.active_game is None:
        st.subheader("🕹️ Choose an Activity")
        c1, c2, c3 = st.columns(3)
        if c1.button("🐍 Snake"): st.session_state.active_game = "Snake"; st.rerun()
        if c2.button("🧩 2048"): st.session_state.active_game = "2048"; st.rerun()
        if c3.button("🧠 Memory"): st.session_state.active_game = "Memory"; st.rerun()
    else:
        if st.button("⬅️ Back to Menu", key="back_m"): st.session_state.active_game = None; st.rerun()
        
        # UI Overlay Styles
        GAME_UI = """<style>
            #over { position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.9); 
                    display:none; flex-direction:column; align-items:center; justify-content:center; border-radius:15px; z-index:10;}
            .btn { background:#38BDF8; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:bold; margin-top:10px;}
        </style>"""

        if st.session_state.active_game == "Snake":
            st.components.v1.html(f"<script>{SOUND_JS}</script>{GAME_UI}" + """
            <div style="position:relative; background:#1E293B; padding:15px; border-radius:15px; display:flex; flex-direction:column; align-items:center; touch-action:none;">
                <div id="over">
                    <h2 style="color:#F87171;">GAME OVER</h2>
                    <h3 id="fsc" style="color:white;">Score: 0</h3>
                    <button class="btn" onclick="rst()">TRY AGAIN</button>
                </div>
                <canvas id="snk" width="280" height="280" style="background:#0F172A; border-radius:10px;"></canvas>
                <h4 id="sc" style="color:#38BDF8; margin:10px 0 0 0;">Score: 0</h4>
            </div>
            <script>
                const cvs=document.getElementById("snk"), ctx=cvs.getContext("2d"), ov=document.getElementById("over");
                let b=14, snk, fd, d, gm, tX, tY;
                window.addEventListener('keydown', e => { 
                    if(e.key=="ArrowLeft"&&d!='R') d='L'; if(e.key=="ArrowUp"&&d!='D') d='U';
                    if(e.key=="ArrowRight"&&d!='L') d='R'; if(e.key=="ArrowDown"&&d!='U') d='D';
                });
                cvs.addEventListener('touchstart', e => { tX=e.touches[0].clientX; tY=e.touches[0].clientY; });
                cvs.addEventListener('touchend', e => {
                    let dx=e.changedTouches[0].clientX-tX, dy=e.changedTouches[0].clientY-tY;
                    if(Math.abs(dx)>Math.abs(dy)) d=(dx>30&&d!='L')?'R':(dx<-30&&d!='R'?'L':d);
                    else d=(dy>30&&d!='U')?'D':(dy<-30&&d!='D'?'U':d);
                });
                function rst(){ ov.style.display='none'; snk=[{x:140,y:140}]; fd={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; d=null; clearInterval(gm); gm=setInterval(drw,120); }
                function drw(){
                    ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,280,280); ctx.fillStyle="#F87171"; ctx.fillRect(fd.x,fd.y,b,b);
                    snk.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,b,b); });
                    let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
                    if(h.x==fd.x&&h.y==fd.y){ fd={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; sfx(440,0.1,'square'); } else if(d)snk.pop();
                    if(h.x<0||h.x>=280||h.y<0||h.y>=280||(d&&snk.some(s=>s.x==h.x&&s.y==h.y))){ 
                        sfx(100,0.4,'sawtooth'); clearInterval(gm); ov.style.display='flex'; document.getElementById("fsc").innerText="Score: "+(snk.length-1);
                    }
                    if(d)snk.unshift(h); document.getElementById("sc").innerText="Score: "+(snk.length-1);
                }
                rst();
            </script>""", height=440)

        elif st.session_state.active_game == "Memory":
            st.components.v1.html(f"<script>{SOUND_JS}</script>{GAME_UI}" + """
            <div style="position:relative; background:#1E293B; padding:20px; border-radius:15px; text-align:center;">
                <div id="over">
                    <h2 style="color:#F472B6;">MISSED ONE!</h2>
                    <button class="btn" style="background:#F472B6;" onclick="rst()">RESTART</button>
                </div>
                <h3 id="ml" style="color:#F472B6;">Level 1</h3>
                <div id="mg" style="display:grid; grid-template-columns:repeat(3,70px); gap:10px; margin:20px auto; width:230px;"></div>
                <button id="mb" style="background:#F472B6; color:white; border:none; padding:10px 20px; border-radius:8px; width:100%; font-weight:bold;">START ROUND</button>
            </div>
            <script>
                let l=1, s=[], u=[], w=false; const g=document.getElementById("mg"), ov=document.getElementById("over");
                function build(){ g.innerHTML=""; for(let i=0;i<9;i++){ let t=document.createElement("div"); t.style="width:70px;height:70px;background:#334155;border-radius:10px;cursor:pointer"; t.onclick=()=>tap(i); g.appendChild(t); } }
                async function flsh(i, c="#F472B6"){ g.children[i].style.background=c; sfx(200+i*50,0.2); await new Promise(r=>setTimeout(r,400)); g.children[i].style.background="#334155"; }
                document.getElementById("mb").onclick=async()=>{
                    s.push(Math.floor(Math.random()*9)); u=[]; w=true;
                    for(let x of s){ await new Promise(r=>setTimeout(r,200)); await flsh(x); }
                    w=false;
                };
                function rst(){ ov.style.display='none'; s=[]; l=1; document.getElementById("ml").innerText="Level 1"; build(); }
                async function tap(i){
                    if(w) return; await flsh(i,"#38BDF8"); u.push(i);
                    if(u[u.length-1]!==s[u.length-1]){ sfx(100,0.5,'sawtooth'); ov.style.display='flex'; }
                    else if(u.length===s.length){ l++; document.getElementById("ml").innerText="Level "+l; w=true; sfx(800,0.2); }
                }
                build();
            </script>""", height=440)
        
        elif st.session_state.active_game == "2048":
            st.components.v1.html(f"<script>{SOUND_JS}</script>" + """
            <div style="background:#1E293B; padding:15px; border-radius:15px; display:flex; flex-direction:column; align-items:center; touch-action:none;">
                <div id="grid" style="display:grid; grid-template-columns:repeat(4,60px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
                <p style="color:white; margin-top:10px; font-size:12px;">Use Arrows or Swipe</p>
            </div>
            <script>
                let bd=Array(16).fill(0), tX, tY;
                function add(){ let e=bd.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) bd[e[Math.floor(Math.random()*e.length)]]=2; }
                function ren(){ const g=document.getElementById('grid'); g.innerHTML=''; bd.forEach(v=>{ const t=document.createElement('div'); t.style=`width:60px;height:60px;background:${v?'#38BDF8':'#334155'};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }); }
                function mv(s,st,sd){ for(let i=0;i<4;i++){ let l=[]; for(let j=0;j<4;j++) l.push(bd[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){ f[j]*=2; sfx(600,0.1); f.splice(j+1,1); } while(f.length<4) f.push(0); for(let j=0;j<4;j++) bd[s+i*sd+j*st]=f[j]; } }
                window.addEventListener('keydown', e => { if(e.key.includes("Arrow")){ e.preventDefault(); if(e.key=="ArrowLeft")mv(0,1,4); if(e.key=="ArrowRight")mv(3,-1,4); if(e.key=="ArrowUp")mv(0,4,1); if(e.key=="ArrowDown")mv(12,-4,1); add(); ren(); sfx(300,0.05); } });
                add(); add(); ren();
            </script>""", height=440)

# --- 8. ADMIN ---
with tabs[3]:
    if st.session_state.auth['role'] != "admin": st.warning("Access Restricted")
    else:
        log_df = load_sheet("ChatLogs")
        if not log_df.empty:
            sel_u = st.multiselect("Filter Member ID", log_df['memberid'].unique())
            st.dataframe(log_df[log_df['memberid'].isin(sel_u)] if sel_u else log_df, use_container_width=True)

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()
