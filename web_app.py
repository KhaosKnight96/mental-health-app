import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. THEME & UI OVERHAUL ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Main App Background */
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    
    /* Premium Glass Cards */
    .glass-panel {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(15px);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }

    /* Chat Bubble Styling */
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; padding: 10px; }
    [data-testid="stChatMessageUser"] { background-color: #1E3A8A !important; border-bottom-right-radius: 2px !important; }
    [data-testid="stChatMessageAssistant"] { background-color: #334155 !important; border-bottom-left-radius: 2px !important; }

    /* Animated Avatar */
    .bot-avatar {
        width: 60px; height: 60px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 30px; margin: 0 auto 10px;
        background: linear-gradient(135deg, #38BDF8, #6366F1);
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.5);
    }
    
    /* Utility */
    .stButton>button { border-radius: 10px; font-weight: 600; transition: 0.3s; }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
</style>
""", unsafe_allow_html=True)

# --- 2. DATA & API INITIALIZATION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    client = Groq(api_key=st.secrets.get("GROQ_API_KEY", "MISSING_KEY"))
except Exception as e:
    st.error(f"Configuration Error: {e}")

# Persistent Session State
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}

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
    except Exception as e: st.toast(f"Sync Error: {e}")

# --- 3. ACCESS CONTROL ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>Health Bridge</h1>", unsafe_allow_html=True)
    tab_l, tab_r = st.tabs(["Login", "Register"])
    
    with tab_l:
        u = st.text_input("ID", key="login_id")
        p = st.text_input("Pass", type="password", key="login_pw")
        if st.button("Sign In", key="btn_login"):
            users = load_sheet("Users")
            if not users.empty:
                m = users[(users['memberid'].astype(str) == u) & (users['password'].astype(str) == p)]
                if not m.empty:
                    st.session_state.auth.update({"in": True, "mid": u, "role": str(m.iloc[0]['role']).lower()})
                    st.rerun()
                else: st.error("Invalid Credentials")

    with tab_r:
        nu = st.text_input("New ID", key="reg_id")
        np = st.text_input("New Pass", type="password", key="reg_pw")
        if st.button("Create Account", key="btn_reg"):
            log_to_sheet("Users", {"memberid": nu, "password": np, "role": "user"})
            st.success("Registration Complete!")
    st.stop()

# --- 4. MAIN APP LAYOUT ---
tabs = st.tabs(["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games Center", "🛡️ Admin"])

# --- 5. COOPER'S CORNER ---
with tabs[0]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar">🤖</div><h3 style="text-align:center;">Cooper</h3></div>', unsafe_allow_html=True)
    
    with st.expander("📊 Log Energy"):
        val = st.select_slider("How's your energy?", options=list(range(1,12)), value=6, key="sl_eng")
        if st.button("Save Entry", key="btn_save_e"):
            log_to_sheet("Sheet1", {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": val})
            st.toast("Energy Logged!")

    for msg in st.session_state.chats["Cooper"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("Message Cooper...", key="coop_chat"):
        st.session_state.chats["Cooper"].append({"role": "user", "content": prompt})
        log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "role": "user", "content": prompt})
        
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.chats["Cooper"][-3:]).choices[0].message.content
            st.session_state.chats["Cooper"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "role": "assistant", "content": res})
        except: st.error("AI Unavailable: Check API Key")
        st.rerun()

# --- 6. CLARA'S COUCH ---
with tabs[1]:
    st.markdown('<div class="glass-panel"><div class="bot-avatar" style="background:linear-gradient(135deg,#F472B6,#E11D48);">🛋️</div><h3 style="text-align:center;">Clara</h3></div>', unsafe_allow_html=True)
    
    # Visual Analytics
    logs = load_sheet("Sheet1")
    if not logs.empty:
        p_logs = logs[logs['memberid'].astype(str) == st.session_state.auth['mid']]
        if not p_logs.empty:
            fig = go.Figure(go.Scatter(x=pd.to_datetime(p_logs['timestamp']), y=p_logs['energylog'], fill='tozeroy', line=dict(color='#F472B6')))
            fig.update_layout(height=200, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

    for msg in st.session_state.chats["Clara"]:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt_clara := st.chat_input("Analyze with Clara...", key="clara_chat"):
        st.session_state.chats["Clara"].append({"role": "user", "content": prompt_clara})
        log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Clara", "role": "user", "content": prompt_clara})
        try:
            res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara."}]+st.session_state.chats["Clara"][-3:]).choices[0].message.content
            st.session_state.chats["Clara"].append({"role": "assistant", "content": res})
            log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Clara", "role": "assistant", "content": res})
        except: st.error("AI Unavailable")
        st.rerun()

# --- 7. GAMES CENTER (HYBRID + SOUND + MEMORY LEVELING) ---
with tabs[2]:
    g_type = st.radio("Select Activity", ["Snake", "2048", "Memory"], horizontal=True, key="g_type")
    
    SOUND_JS = """
    const actx = new (window.AudioContext || window.webkitAudioContext)();
    function playSfx(f, d, t='sine') {
        const o=actx.createOscillator(); const g=actx.createGain();
        o.type=t; o.frequency.value=f; g.gain.exponentialRampToValueAtTime(0.0001, actx.currentTime+d);
        o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime+d);
    }
    """

    if g_type == "Snake":
        S_CODE = f"<script>{SOUND_JS}</script>" + """
        <div style="background:#1E293B; padding:15px; border-radius:15px; display:flex; flex-direction:column; align-items:center;">
            <canvas id="snk" width="300" height="300" style="background:#0F172A; border-radius:10px;"></canvas>
            <h4 id="sk_sc" style="color:#38BDF8;">Score: 0</h4>
        </div>
        <script>
            const cvs=document.getElementById("snk"); const ctx=cvs.getContext("2d");
            let b=15, snk, fd, d, gm, tsX, tsY;
            window.addEventListener('keydown', e => { 
                if(e.key=="ArrowLeft"&&d!='R') d='L'; if(e.key=="ArrowUp"&&d!='D') d='U';
                if(e.key=="ArrowRight"&&d!='L') d='R'; if(e.key=="ArrowDown"&&d!='U') d='D';
            });
            cvs.addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            cvs.addEventListener('touchend', e => {
                let dx=e.changedTouches[0].clientX-tsX, dy=e.changedTouches[0].clientY-tsY;
                if(Math.abs(dx)>Math.abs(dy)) d=(dx>30&&d!='L')?'R':(dx<-30&&d!='R'?'L':d);
                else d=(dy>30&&d!='U')?'D':(dy<-30&&d!='D'?'U':d);
            });
            function rst(){ snk=[{x:150,y:150}]; fd={x:Math.floor(Math.random()*19)*b,y:Math.floor(Math.random()*19)*b}; d=null; clearInterval(gm); gm=setInterval(drw,120); }
            function drw(){
                ctx.fillStyle="#0F172A"; ctx.fillRect(0,0,300,300); ctx.fillStyle="#F87171"; ctx.fillRect(fd.x,fd.y,b,b);
                snk.forEach((p,i)=>{ ctx.fillStyle=i==0?"#38BDF8":"#334155"; ctx.fillRect(p.x,p.y,b,b); });
                let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
                if(h.x==fd.x&&h.y==fd.y){ fd={x:Math.floor(Math.random()*19)*b,y:Math.floor(Math.random()*19)*b}; playSfx(440,0.1,'square'); } else if(d)snk.pop();
                if(h.x<0||h.x>=300||h.y<0||h.y>=300||(d&&snk.some(s=>s.x==h.x&&s.y==h.y))){ playSfx(100,0.4,'sawtooth'); rst(); }
                if(d)snk.unshift(h); document.getElementById("sk_sc").innerText="Score: "+(snk.length-1);
            }
            rst();
        </script>"""
        st.components.v1.html(S_CODE, height=450)

    elif g_type == "Memory":
        M_CODE = f"<script>{SOUND_JS}</script>" + """
        <div style="background:#1E293B; padding:20px; border-radius:15px; text-align:center;">
            <h3 id="mlvl" style="color:#F472B6;">Level 1</h3>
            <div id="mgrid" style="display:grid; grid-template-columns:repeat(3,75px); gap:10px; margin:20px 0;"></div>
            <button id="mbtn" style="background:#F472B6; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer;">Start Round</button>
        </div>
        <script>
            let l=1, s=[], u=[], wait=false;
            const g=document.getElementById("mgrid");
            function build(){ g.innerHTML=""; for(let i=0;i<9;i++){ let t=document.createElement("div"); t.style="width:75px;height:75px;background:#334155;border-radius:10px;cursor:pointer"; t.onclick=()=>tap(i); g.appendChild(t); } }
            async function flash(i, c="#F472B6"){ g.children[i].style.background=c; playSfx(200+i*50,0.2); await new Promise(r=>setTimeout(r,400)); g.children[i].style.background="#334155"; }
            document.getElementById("mbtn").onclick=async()=>{
                s.push(Math.floor(Math.random()*9)); u=[]; wait=true;
                for(let x of s){ await new Promise(r=>setTimeout(r,200)); await flash(x); }
                wait=false;
            };
            async function tap(i){
                if(wait) return; await flash(i,"#38BDF8"); u.push(i);
                if(u[u.length-1]!==s[u.length-1]){ playSfx(100,0.5,'sawtooth'); alert("Try Again!"); s=[]; l=1; document.getElementById("mlvl").innerText="Level 1"; }
                else if(u.length===s.length){ l++; document.getElementById("mlvl").innerText="Level "+l; wait=true; playSfx(800,0.2); }
            }
            build();
        </script>"""
        st.components.v1.html(M_CODE, height=450)
    
    else: # 2048 Logic
        T_CODE = f"<script>{SOUND_JS}</script>" + """
        <div id="gbox" style="background:#1E293B; padding:20px; border-radius:15px; display:flex; flex-direction:column; align-items:center;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,65px); gap:10px; background:#0F172A; padding:10px; border-radius:10px;"></div>
        </div>
        <script>
            let bd=Array(16).fill(0), tX, tY;
            function add(){ let e=bd.map((v,i)=>v==0?i:null).filter(v=>v!=null); if(e.length) bd[e[Math.floor(Math.random()*e.length)]]=2; }
            function ren(){ const g=document.getElementById('grid'); g.innerHTML=''; bd.forEach(v=>{ const t=document.createElement('div'); t.style=`width:65px;height:65px;background:${v?'#38BDF8':'#334155'};color:white;display:flex;align-items:center;justify-content:center;border-radius:8px;font-weight:bold;`; t.innerText=v||''; g.appendChild(t); }); }
            function mv(s,st,sd){ for(let i=0;i<4;i++){ let l=[]; for(let j=0;j<4;j++) l.push(bd[s+i*sd+j*st]); let f=l.filter(v=>v); for(let j=0;j<f.length-1;j++) if(f[j]==f[j+1]){ f[j]*=2; playSfx(600,0.1); f.splice(j+1,1); } while(f.length<4) f.push(0); for(let j=0;j<4;j++) bd[s+i*sd+j*st]=f[j]; } }
            window.addEventListener('keydown', e => { let k=e.key; if(k.includes("Arrow")){ if(k=="ArrowLeft")mv(0,1,4); if(k=="ArrowRight")mv(3,-1,4); if(k=="ArrowUp")mv(0,4,1); if(k=="ArrowDown")mv(12,-4,1); add(); ren(); playSfx(300,0.05); } });
            add(); add(); ren();
        </script>"""
        st.components.v1.html(T_CODE, height=450)

# --- 8. ADMIN DASHBOARD ---
with tabs[3]:
    if st.session_state.auth['role'] != "admin":
        st.warning("Admin Access Only")
    else:
        st.subheader("🛡️ Global Log Explorer")
        all_logs = load_sheet("ChatLogs")
        if not all_logs.empty:
            c1, c2 = st.columns(2)
            with c1: u_flt = st.multiselect("Users", all_logs['memberid'].unique(), key="ad_u")
            with c2: a_flt = st.multiselect("Agents", all_logs['agent'].unique(), key="ad_a")
            
            f_df = all_logs.copy()
            if u_flt: f_df = f_df[f_df['memberid'].isin(u_flt)]
            if a_flt: f_df = f_df[f_df['agent'].isin(a_flt)]
            st.dataframe(f_df, use_container_width=True, hide_index=True)
            st.download_button("Export Results", f_df.to_csv(index=False), "logs.csv", key="ad_dl")

# --- 9. LOGOUT ---
if st.sidebar.button("Logout", key="btn_logout"):
    st.session_state.clear()
    st.rerun()
