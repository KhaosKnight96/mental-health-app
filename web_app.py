import streamlit as st
import pandas as pd
from groq import Groq
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.graph_objects as go

# --- 1. CONFIG & SYSTEM CORE ---
st.set_page_config(page_title="Health Bridge Pro", layout="wide", initial_sidebar_state="collapsed")

# Injecting CSS for a high-end "Medical Tech" feel
st.markdown("""
<style>
    .stApp { background-color: #0F172A; color: #F8FAFC; }
    .glass-panel {
        background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px);
        border-radius: 18px; padding: 25px; border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); margin-bottom: 20px;
    }
    .stChatMessage { border-radius: 12px; padding: 15px; margin-bottom: 12px; }
    [data-testid="stChatMessageUser"] { background-color: #1E40AF !important; border-left: 5px solid #38BDF8; }
    [data-testid="stChatMessageAssistant"] { background-color: #1E293B !important; border-left: 5px solid #6366F1; }
    .game-container { position: relative; border-radius: 15px; overflow: hidden; border: 2px solid #334155; }
</style>
""", unsafe_allow_html=True)

# --- 2. INITIALIZE SESSION STATE ---
if "auth" not in st.session_state: st.session_state.auth = {"in": False, "mid": None, "role": "user"}
if "chats" not in st.session_state: st.session_state.chats = {"Cooper": [], "Clara": []}
if "active_game" not in st.session_state: st.session_state.active_game = None

# --- 3. HELPER FUNCTIONS ---
def get_ai_client():
    """Ensures a fresh AI client is available."""
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        st.error("⚠️ AI Key Missing: Go to Streamlit Settings > Secrets and add GROQ_API_KEY='your_key'")
        return None
    return Groq(api_key=api_key)

def load_sheet(name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=name, ttl=0)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except: return pd.DataFrame()

def log_to_sheet(sheet, data_dict):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        current_df = load_sheet(sheet)
        new_row = pd.DataFrame([data_dict])
        conn.update(worksheet=sheet, data=pd.concat([current_df, new_row], ignore_index=True))
    except Exception as e: st.toast(f"Sync Error: {e}")

# --- 4. AUTHENTICATION GATE ---
if not st.session_state.auth["in"]:
    st.markdown("<h1 style='text-align:center;'>🧠 Health Bridge</h1>", unsafe_allow_html=True)
    colA, colB = st.tabs(["Member Login", "New Account"])
    
    with colA:
        u_in = st.text_input("Member ID").strip().lower()
        p_in = st.text_input("Password", type="password")
        if st.button("Unlock Dashboard", use_container_width=True):
            users = load_sheet("Users")
            if not users.empty:
                user_match = users[users['memberid'].astype(str).str.lower() == u_in]
                if not user_match.empty and str(user_match.iloc[0]['password']) == p_in:
                    st.session_state.auth.update({"in": True, "mid": u_in, "role": str(user_match.iloc[0]['role']).lower()})
                    st.rerun()
            st.warning("Credential Mismatch")
    st.stop()

# --- 5. INTERFACE TABS ---
tabs = st.tabs(["🏠 Cooper", "🛋️ Clara", "🎮 Activity", "⚙️ System"])

# --- 6. AGENT: COOPER (THE COACH) ---
with tabs[0]:
    st.markdown('<div class="glass-panel"><h3>🤖 Cooper\'s Corner</h3><p>Your daily health & activity navigator.</p></div>', unsafe_allow_html=True)
    
    # Display Chat
    for m in st.session_state.chats["Cooper"]:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_coop := st.chat_input("How's your energy today?", key="c_input"):
        st.session_state.chats["Cooper"].append({"role": "user", "content": p_coop})
        client = get_ai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": "You are Cooper, a concise, encouraging health coach."}] + st.session_state.chats["Cooper"][-4:]
                )
                answer = response.choices[0].message.content
                st.session_state.chats["Cooper"].append({"role": "assistant", "content": answer})
                log_to_sheet("ChatLogs", {"timestamp": datetime.now(), "memberid": st.session_state.auth['mid'], "agent": "Cooper", "content": answer})
                st.rerun()
            except Exception as e: st.error(f"Cooper is resting: {e}")

# --- 7. AGENT: CLARA (THE ANALYST) ---
with tabs[1]:
    st.markdown('<div class="glass-panel"><h3>🧘‍♀️ Clara\'s Couch</h3><p>Reflecting on your data and trends.</p></div>', unsafe_allow_html=True)
    
    # Data Visualization for Clara
    df_data = load_sheet("Sheet1")
    if not df_data.empty:
        my_data = df_data[df_data['memberid'].astype(str) == st.session_state.auth['mid']]
        if not my_data.empty:
            fig = go.Figure(go.Bar(x=pd.to_datetime(my_data['timestamp']), y=my_data['energylog'], marker_color='#6366F1'))
            fig.update_layout(height=200, margin=dict(l=0,r=0,t=10,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white"))
            st.plotly_chart(fig, use_container_width=True)

    for m in st.session_state.chats["Clara"]:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p_clara := st.chat_input("Let's look at the numbers...", key="clara_input"):
        st.session_state.chats["Clara"].append({"role": "user", "content": p_clara})
        client = get_ai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": "You are Clara, a calm analyst who uses data to help users understand their health."}] + st.session_state.chats["Clara"][-4:]
                )
                answer = response.choices[0].message.content
                st.session_state.chats["Clara"].append({"role": "assistant", "content": answer})
                st.rerun()
            except Exception as e: st.error(f"Clara is offline: {e}")

# --- 8. GAMES REPACKAGED (SNAKE, 2048, MEMORY) ---
with tabs[2]:
    if st.session_state.active_game is None:
        st.subheader("Select a Mental Recharge Activity")
        c1, c2, c3 = st.columns(3)
        if c1.button("🐍 Snake"): st.session_state.active_game = "Snake"; st.rerun()
        if c2.button("🧩 2048"): st.session_state.active_game = "2048"; st.rerun()
        if c3.button("🧠 Memory"): st.session_state.active_game = "Memory"; st.rerun()
    else:
        st.button("⬅️ Back to Hub", on_click=lambda: st.session_state.update({"active_game": None}))
        
        # Shared CSS for Game Over screens
        OVERLAY_STYLE = """<style>
            #over { position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(15,23,42,0.95); 
                    display:none; flex-direction:column; align-items:center; justify-content:center; border-radius:15px; z-index:100;}
            .btn-reset { background:#6366F1; color:white; border:none; padding:12px 24px; border-radius:8px; cursor:pointer; font-weight:bold; margin-top:15px;}
        </style>"""

        if st.session_state.active_game == "Snake":
            st.components.v1.html(OVERLAY_STYLE + """
            <div style="position:relative; width:300px; margin:auto; background:#1E293B; padding:15px; border-radius:20px; text-align:center;">
                <div id="over">
                    <h2 style="color:#F87171; font-family:sans-serif;">GAME OVER</h2>
                    <button class="btn-reset" onclick="init()">RESTART SESSION</button>
                </div>
                <canvas id="s" width="280" height="280" style="background:#0F172A; border-radius:10px;"></canvas>
                <div style="color:#38BDF8; font-family:sans-serif; margin-top:10px;">Score: <span id="sc">0</span></div>
            </div>
            <script>
                const c=document.getElementById("s"), x=c.getContext("2d"), ov=document.getElementById("over");
                let b=14, snk, fd, d, gm;
                document.onkeydown=e=>{ let k=e.key; if(k=="ArrowLeft"&&d!='R')d='L'; if(k=="ArrowUp"&&d!='D')d='U'; if(k=="ArrowRight"&&d!='L')d='R'; if(k=="ArrowDown"&&d!='U')d='D';};
                function init(){ ov.style.display='none'; snk=[{x:140,y:140}]; fd={x:70,y:70}; d=null; clearInterval(gm); gm=setInterval(upd,120); }
                function upd(){
                    x.fillStyle="#0F172A"; x.fillRect(0,0,280,280); x.fillStyle="#F87171"; x.fillRect(fd.x,fd.y,b,b);
                    snk.forEach((p,i)=>{ x.fillStyle=i==0?"#38BDF8":"#334155"; x.fillRect(p.x,p.y,b,b); });
                    if(!d) return; let h={...snk[0]}; if(d=='L')h.x-=b; if(d=='U')h.y-=b; if(d=='R')h.x+=b; if(d=='D')h.y+=b;
                    if(h.x==fd.x&&h.y==fd.y){ fd={x:Math.floor(Math.random()*20)*b,y:Math.floor(Math.random()*20)*b}; } else snk.pop();
                    if(h.x<0||h.x>=280||h.y<0||h.y>=280||snk.some(s=>s.x==h.x&&s.y==h.y)){ clearInterval(gm); ov.style.display='flex'; }
                    snk.unshift(h); document.getElementById("sc").innerText=snk.length-1;
                }
                init();
            </script>""", height=450)

        elif st.session_state.active_game == "Memory":
            st.components.v1.html(OVERLAY_STYLE + """
            <div style="position:relative; width:300px; margin:auto; background:#1E293B; padding:20px; border-radius:20px; text-align:center;">
                <div id="over">
                    <h2 style="color:#F472B6; font-family:sans-serif;">MISSED ONE</h2>
                    <button class="btn-reset" style="background:#F472B6" onclick="reset()">TRY AGAIN</button>
                </div>
                <h3 id="lv" style="color:#F472B6; font-family:sans-serif;">Level 1</h3>
                <div id="g" style="display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:15px 0;"></div>
                <button id="st" style="width:100%; background:#F472B6; color:white; border:none; padding:10px; border-radius:8px; cursor:pointer;">START ROUND</button>
            </div>
            <script>
                const g=document.getElementById("g"), ov=document.getElementById("over"), lvD=document.getElementById("lv");
                let seq=[], user=[], wait=false, lv=1;
                function build(){ g.innerHTML=""; for(let i=0;i<9;i++){ let d=document.createElement("div"); d.style="height:60px;background:#334155;border-radius:8px;cursor:pointer"; d.onclick=()=>tap(i); g.appendChild(d); } }
                async function flash(i){ g.children[i].style.background="#F472B6"; await new Promise(r=>setTimeout(r,400)); g.children[i].style.background="#334155"; }
                document.getElementById("st").onclick=async()=>{
                    seq.push(Math.floor(Math.random()*9)); user=[]; wait=true;
                    for(let i of seq){ await new Promise(r=>setTimeout(r,300)); await flash(i); }
                    wait=false;
                };
                function reset(){ ov.style.display='none'; seq=[]; lv=1; lvD.innerText="Level 1"; build(); }
                async function tap(i){
                    if(wait) return; g.children[i].style.background="#38BDF8"; setTimeout(()=>g.children[i].style.background="#334155",200);
                    user.push(i);
                    if(user[user.length-1]!==seq[user.length-1]){ ov.style.display='flex'; }
                    else if(user.length===seq.length){ lv++; lvD.innerText="Level "+lv; wait=true; }
                }
                build();
            </script>""", height=450)

# --- 9. ADMIN/LOGOUT ---
with tabs[3]:
    st.button("Force Logout", on_click=lambda: st.session_state.clear())
    if st.session_state.auth['role'] == "admin":
        st.write("Recent Activity Log")
        st.dataframe(load_sheet("ChatLogs"), use_container_width=True)
