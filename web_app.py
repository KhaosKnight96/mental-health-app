import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIGURATION & PROFESSIONAL STYLING ---
st.set_page_config(page_title="Health Bridge", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    
    /* Glassmorphism Panels */
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 24px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
    }
    
    /* Animated Avatars */
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

    /* Mobile Responsive Logic */
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; }
    .stButton>button { border-radius: 12px; font-weight: 600; height: 3.5em; width: 100%; }
    .game-box { touch-action: none; overflow: hidden; display: flex; flex-direction: column; align-items: center; }
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
    except:
        return pd.DataFrame()

def save_chat(agent, role, content):
    new_entry = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "memberid": st.session_state.auth['mid'],
        "agent": agent, "role": role, "content": content
    }])
    conn.update(worksheet="ChatLogs", data=pd.concat([get_data("ChatLogs"), new_entry], ignore_index=True))

# --- 3. LOGIN & REGISTRATION GATE ---
if not st.session_state.auth["logged_in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["🔐 Login", "📝 Sign Up"])
    
    with t1:
        u = st.text_input("Member ID", key="l_u").strip().lower()
        p = st.text_input("Password", type="password", key="l_p")
        if st.button("Enter Portal", key="l_b"):
            df_users = get_data("Users")
            if not df_users.empty:
                match = df_users[(df_users['memberid'].astype(str).str.lower() == u) & (df_users['password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.auth.update({"logged_in": True, "mid": u, "role": str(match.iloc[0]['role']).lower()})
                    st.rerun()
                else:
                    st.error("Access Denied: Check ID/Password")

    with t2:
        mid_new = st.text_input("Choose Member ID", key="r_u").strip().lower()
        p_new = st.text_input("Set Password", type="password", key="r_p")
        if st.button("Create Account", key="r_b"):
            df_users = get_data("Users")
            if not df_users.empty and mid_new in df_users['memberid'].astype(str).str.lower().values:
                st.error("This ID is already registered.")
            else:
                new_user = pd.DataFrame([{"memberid": mid_new, "password": p_new, "role": "user"}])
                conn.update(worksheet="Users", data=pd.concat([df_users, new_user], ignore_index=True))
                st.success("Account Ready! Please Login.")
    st.stop()

# --- 4. MAIN NAVIGATION ---
nav_tabs = ["🏠 Cooper's Corner", "🛋️ Clara's Couch", "🎮 Games"]
if st.session_state.auth['role'] == "admin":
    nav_tabs.append("🛡️ Admin")
tabs = st.tabs(nav_tabs)

# --- 5. COOPER'S CORNER ---
with tabs[0]:
    st.markdown("""<div class="glass-card"><div class="avatar-circle" style="background:linear-gradient(135deg,#0ea5e9,#6366f1);">🤖</div><h2 style="text-align:center;margin:0;">Cooper's Corner</h2></div>""", unsafe_allow_html=True)
    
    with st.expander("⚡ Sync Daily Energy Status", expanded=True):
        ev = st.select_slider("Current Level (1-11)", options=list(range(1,12)), value=6, key="e_val")
        if st.button("💾 Log to Cloud", key="s_b"):
            new_row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), "memberid": st.session_state.auth['mid'], "energylog": ev}])
            conn.update(worksheet="Sheet1", data=pd.concat([get_data("Sheet1"), new_row], ignore_index=True))
            st.toast("Data Synced!")

    for msg in st.session_state.cooper_logs:
        st.chat_message(msg["role"]).write(msg["content"])
    
    if prompt_coop := st.chat_input("Talk to Cooper...", key="c_in"):
        st.session_state.cooper_logs.append({"role": "user", "content": prompt_coop})
        save_chat("Cooper", "user", prompt_coop)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Cooper."}]+st.session_state.cooper_logs[-3:]).choices[0].message.content
        st.session_state.cooper_logs.append({"role": "assistant", "content": res})
        save_chat("Cooper", "assistant", res)
        st.rerun()

# --- 6. CLARA'S COUCH ---
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

    for msg in st.session_state.clara_logs:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt_clara := st.chat_input("Analyze with Clara...", key="cl_in"):
        st.session_state.clara_logs.append({"role": "user", "content": prompt_clara})
        save_chat("Clara", "user", prompt_clara)
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":"You are Clara."}]+st.session_state.clara_logs[-3:]).choices[0].message.content
        st.session_state.clara_logs.append({"role": "assistant", "content": res})
        save_chat("Clara", "assistant", res)
        st.rerun()

# --- 7. GAMES ---
with tabs[2]:
    g_choice = st.radio("Activity", ["Snake", "2048"], horizontal=True, key="g_sel")
    
    if g_choice == "Snake":
        S_HTML = """
        <div class="game-box" style="background:#1E293B; border-radius:20px; padding:20px;">
            <canvas id="sc" width="300" height="300" style="background:#0F172A; border:2px solid #38BDF8; border-radius:10px;"></canvas>
            <h3 style="color:#38BDF8;" id="sn_score">Score: 0</h3>
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
                if(d) snake.unshift(h); document.getElementById("sn_score").innerText="Score: "+(snake.length-1);
            }
            reset();
        </script>"""
        st.components.v1.html(S_HTML, height=450)
    else:
        T_HTML = """
        <div id="g2k_box" class="game-box" style="background:#1E293B; border-radius:20px; padding:20px;">
            <div id="grid" style="display:grid; grid-template-columns:repeat(4,65px); gap:8px; background:#0F172A; padding:10px; border-radius:10px;"></div>
        </div>
        <script>
            let board=Array(16).fill(0), tsX, tsY;
            window.addEventListener('keydown', e => {
                if(e.key=="ArrowLeft") mv(0,1,4); if(e.key=="ArrowRight") mv(3,-1,4);
                if(e.key=="ArrowUp") mv(0,4,1); if(e.key=="ArrowDown") mv(12,-4,1); add(); ren();
            });
            document.getElementById('g2k_box').addEventListener('touchstart', e => { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; });
            document.getElementById('g2k_box').addEventListener('touchend', e => {
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
        st.components.v1.html(T_HTML, height=450)

# --- 8. ADMIN PORTAL ---
if st.session_state.auth['role'] == "admin":
    with tabs[3]:
        st.subheader("🛡️ Global Activity Monitor")
        logs_df = get_data("ChatLogs")
        if not logs_df.empty:
            c1, c2 = st.columns(2)
            with c1: 
                u_f = st.multiselect("Users", options=logs_df['memberid'].unique(), key="ad_u")
            with c2: 
                a_f = st.multiselect("Agents", options=logs_df['agent'].unique(), key="ad_a")
            kw = st.text_input("🔍 Keyword Search", key="ad_kw")
            
            final_df = logs_df.copy()
            if u_f: final_df = final_df[final_df['memberid'].isin(u_f)]
            if a_f: final_df = final_df[final_df['agent'].isin(a_f)]
            if kw: final_df = final_df[final_df['content'].astype(str).str.contains(kw, case=False)]
            
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            st.download_button("Export CSV", final_df.to_csv(index=False), "admin_logs.csv", key="ad_dl")

# --- 9. LOGOUT ---
if st.sidebar.button("Logout", key="logout_s"):
    st.session_state.clear()
    st.rerun()
